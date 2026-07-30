"""Post-deploy smoke test for per-PR ephemeral Azure environments (Phase 3, #15).

Standard-library-only. This script runs in CI *after* ``azd provision`` and
``azd deploy`` for a per-PR Container App, before the workflow posts its PR
comment. It polls the two health endpoints served by ``fantasy_cards.web`` --
``GET /health/live`` (liveness: ``200 {"status": "live"}``) and
``GET /health/ready`` (readiness: ``200 {"status": "ready"}``). When the
public ingress is intentionally protected, it instead verifies that both paths
return the configured Entra Bearer challenge. The Container App's trusted
in-process probes continue to verify the actual health payload in that mode.

Cold-start reality: a freshly deployed Container App has zero warm replicas, so
the first probes routinely fail while a replica boots. Those *transient* early
failures are expected and are retried with bounded exponential backoff against a
hard overall deadline. The script never retries forever. A short, bounded 404
warm-up grace is applied only to health endpoints because ACA ingress can briefly
return 404 during revision/route propagation immediately after deploy; once that
grace is exhausted, 404 fails fast as before.

Retry policy (see ``RETRYABLE_STATUSES`` and ``_classify``):

* RETRY  -- connection errors / timeouts (no replica yet) and HTTP
  ``408, 429, 502, 503, 504`` (ingress warming up, throttling, no healthy
  backend). ``503`` is deliberately retried: it is exactly the "no ready
  replica" signal a cold start produces, and readiness itself answers ``503``
  until the app finishes wiring up. A genuinely misconfigured app stays ``503``
  and is caught by the deadline rather than hanging.
* FAIL FAST -- any other status, including non-404 ``4xx`` config errors and
  ``500`` (an application bug is not transient).
* BOUNDED 404 GRACE -- for health endpoints only, early ``404`` answers are
  retried for a short warm-up window, then treated as fail-fast
  ``unexpected_status``. This keeps true misroutes fail-closed while avoiding
  false negatives during startup propagation.
  A ``200`` whose body is not the expected payload is also a fast failure:
  something is serving, but it is not the app we deployed.

Log safety: the base URL and any response text land in world-readable CI logs on
a public repo. Response bodies are never echoed wholesale -- only a short,
truncated, control-character-stripped excerpt is emitted for diagnostics, and
never on success. Every printed string passes through ``_sanitize_log`` (the
same precedent as ``pr_environment_names._sanitize_log``) so attacker-influenced
bytes cannot inject a log line or a GitHub Actions workflow command. TLS
certificate verification is always on; there is intentionally no flag to disable
it.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

# --- Endpoint contract (from src/fantasy_cards/web.py) ------------------------
LIVE_PATH = "/health/live"
READY_PATH = "/health/ready"
LIVE_EXPECTED_STATUS = "live"
READY_EXPECTED_STATUS = "ready"

# --- Retry classification -----------------------------------------------------
# Statuses worth retrying during a cold start. 502/503/504 are the ingress
# "no healthy/ready replica yet" family; 408 is a request timeout; 429 is
# throttling. Everything else (404, other 4xx, 500) is treated as a stable
# answer and fails fast -- retrying it would only waste the deadline.
RETRYABLE_STATUSES = frozenset({408, 429, 502, 503, 504})
WARMUP_404_MAX_ATTEMPTS = 6
WARMUP_404_GRACE_SECONDS = 45.0

# Defaults tuned for a Container App cold start (single small replica).
DEFAULT_DEADLINE_SECONDS = 180.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_MAX_BACKOFF_SECONDS = 15.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0

# Never read an unbounded body from an untrusted endpoint, and never echo more
# than a short excerpt of it.
_MAX_BODY_BYTES = 64 * 1024
_EXCERPT_MAX = 120

# Same log-injection guard as pr_environment_names: strip every C0 control
# character plus DEL so a crafted response can never open a fresh log line or a
# GitHub Actions workflow command (``::error``, ``::set-output``).
_LOG_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f]")
_GUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
_GUID_RE = re.compile(rf"^{_GUID_PATTERN}$", re.IGNORECASE)
_ENTRA_AUTHORIZATION_URI_RE = re.compile(
    rf"^https://login\.microsoftonline\.com/({_GUID_PATTERN})/oauth2/v2\.0/authorize$",
    re.IGNORECASE,
)
_CHALLENGE_ATTRIBUTE_RE = re.compile(r'([a-z_]+)="([^"]*)"', re.IGNORECASE)


def _sanitize_log(text: str) -> str:
    """Neutralize any control character so printed text cannot inject a log line
    or a GitHub Actions workflow command."""
    return _LOG_UNSAFE_RE.sub(" ", text)


def _sanitize_excerpt(text: str, limit: int = _EXCERPT_MAX) -> str:
    """A short, single-line, control-character-free excerpt safe for CI logs.

    Response bodies are truncated *before* sanitizing so we never echo a body
    wholesale, and the result carries no bytes that could forge a log line.
    """
    if not text:
        return ""
    truncated = text[:limit]
    sanitized = _sanitize_log(truncated).strip()
    if len(text) > limit:
        sanitized = f"{sanitized}...".strip()
    return sanitized


class TransportError(Exception):
    """A network-level failure (no HTTP response) -- always retryable."""


@dataclass(frozen=True)
class HttpResponse:
    """A minimal HTTP response the poller reasons about."""

    status_code: int
    body: str
    headers: dict[str, str] | None = None


# A transport takes a fully-qualified URL and a per-request timeout in seconds
# and returns an HttpResponse, or raises TransportError for a network failure.
Transport = Callable[[str, float], HttpResponse]


@dataclass(frozen=True)
class BackoffPolicy:
    """Bounded exponential backoff: ``min(initial * multiplier**(n-1), max)``."""

    initial_seconds: float = DEFAULT_INITIAL_BACKOFF_SECONDS
    multiplier: float = DEFAULT_BACKOFF_MULTIPLIER
    max_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS

    def __post_init__(self) -> None:
        if self.initial_seconds < 0:
            raise ValueError("initial backoff must be non-negative")
        if self.multiplier < 1:
            raise ValueError("backoff multiplier must be >= 1")
        if self.max_seconds < 0:
            raise ValueError("max backoff must be non-negative")

    def delay_for(self, attempt: int) -> float:
        """Delay to wait *after* the ``attempt``-th failed probe (1-indexed)."""
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        raw = self.initial_seconds * (self.multiplier ** (attempt - 1))
        return min(raw, self.max_seconds)


@dataclass(frozen=True)
class EndpointResult:
    """The outcome of polling a single health endpoint."""

    path: str
    healthy: bool
    status_code: int | None
    attempts: int
    reason_code: str
    detail: str


@dataclass(frozen=True)
class SmokeTestResult:
    """The overall verdict the workflow consumes for its PR comment."""

    passed: bool
    reason_code: str
    message: str
    base_url: str
    elapsed_seconds: float
    total_attempts: int
    live: EndpointResult
    ready: EndpointResult

    def printable_fields(self) -> dict[str, object]:
        """Log-safe projection emitted by the CLI.

        Only status codes, counts, booleans, reason codes and already-sanitized
        strings appear here; no raw response body is ever included.
        """
        return {
            "passed": self.passed,
            "reason_code": self.reason_code,
            "message": _sanitize_log(self.message),
            "base_url": _sanitize_log(self.base_url),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "total_attempts": self.total_attempts,
            "live_healthy": self.live.healthy,
            "live_status": self.live.status_code,
            "live_attempts": self.live.attempts,
            "live_reason": self.live.reason_code,
            "ready_healthy": self.ready.healthy,
            "ready_status": self.ready.status_code,
            "ready_attempts": self.ready.attempts,
            "ready_reason": self.ready.reason_code,
        }


@dataclass(frozen=True)
class _ProbeOutcome:
    healthy: bool
    retryable: bool
    status_code: int | None
    reason_code: str
    detail: str


def _default_transport(url: str, timeout: float) -> HttpResponse:
    """Real transport: an HTTPS GET with certificate verification always on.

    An HTTP error response (4xx/5xx) is returned as an ``HttpResponse`` so the
    status-based classifier can decide retry-vs-fail. A network-level failure
    (DNS, connection refused, TLS handshake, timeout) is raised as
    ``TransportError`` -- an inherently retryable "no replica yet" condition.
    """
    request = urllib.request.Request(url, method="GET")
    context = ssl.create_default_context()  # verification stays ON, always.
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read(_MAX_BODY_BYTES)
            return HttpResponse(
                int(response.status), _decode(body), _response_headers(response.headers)
            )
    except urllib.error.HTTPError as error:
        try:
            body = error.read(_MAX_BODY_BYTES)
        except Exception:  # noqa: BLE001 - body is best-effort diagnostics only
            body = b""
        return HttpResponse(
            int(error.code), _decode(body), _response_headers(error.headers)
        )
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", None)
        raise TransportError(str(reason) if reason is not None else str(error)) from error


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _response_headers(headers: object) -> dict[str, str]:
    if headers is None or not hasattr(headers, "items"):
        return {}
    return {
        str(name).lower(): str(value)
        for name, value in headers.items()  # type: ignore[union-attr]
    }


def _classify(
    outcome: HttpResponse,
    expected_status: str,
    *,
    expected_entra_tenant_id: str | None = None,
    expected_realm: str | None = None,
) -> _ProbeOutcome:
    """Turn one HTTP response into a healthy / retry / fail-fast decision."""
    status = outcome.status_code
    if expected_entra_tenant_id is not None:
        return _classify_entra_challenge(
            outcome, expected_entra_tenant_id, expected_realm
        )
    if status == 200:
        if _body_matches(outcome.body, expected_status):
            return _ProbeOutcome(True, False, 200, "ok", "")
        # Something is serving, but not the payload we deployed: not transient.
        return _ProbeOutcome(
            False,
            False,
            200,
            "unexpected_body",
            f"expected status {expected_status!r}; got {_sanitize_excerpt(outcome.body)!r}",
        )
    if status in RETRYABLE_STATUSES:
        return _ProbeOutcome(False, True, status, "service_unavailable", f"HTTP {status}")
    return _ProbeOutcome(False, False, status, "unexpected_status", f"HTTP {status}")


def _classify_entra_challenge(
    outcome: HttpResponse, expected_tenant_id: str, expected_realm: str | None
) -> _ProbeOutcome:
    if outcome.status_code != 401:
        return _ProbeOutcome(
            False,
            False,
            outcome.status_code,
            "unexpected_status",
            f"expected HTTP 401; got HTTP {outcome.status_code}",
        )
    challenge = (outcome.headers or {}).get("www-authenticate", "")
    if not challenge.lower().startswith("bearer "):
        return _ProbeOutcome(
            False, False, 401, "missing_entra_challenge", "missing Bearer challenge"
        )
    attributes = {
        key.lower(): value
        for key, value in _CHALLENGE_ATTRIBUTE_RE.findall(challenge)
    }
    authorization_uri = attributes.get("authorization_uri", "")
    authority_match = _ENTRA_AUTHORIZATION_URI_RE.fullmatch(authorization_uri)
    if (
        authority_match is None
        or authority_match.group(1).lower() != expected_tenant_id.lower()
    ):
        return _ProbeOutcome(
            False,
            False,
            401,
            "invalid_entra_challenge",
            "authorization_uri is not the configured Entra tenant",
        )
    if expected_realm is not None and attributes.get("realm") != expected_realm:
        return _ProbeOutcome(
            False,
            False,
            401,
            "invalid_entra_challenge",
            "realm does not match the probed endpoint",
        )
    if not _GUID_RE.fullmatch(attributes.get("resource_id", "")):
        return _ProbeOutcome(
            False,
            False,
            401,
            "invalid_entra_challenge",
            "resource_id is missing or invalid",
        )
    return _ProbeOutcome(True, False, 401, "entra_challenge", "")


def _body_matches(body: str, expected_status: str) -> bool:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("status") == expected_status


def _probe(
    url: str,
    expected_status: str,
    transport: Transport,
    request_timeout: float,
    expected_entra_tenant_id: str | None,
    expected_realm: str | None,
) -> _ProbeOutcome:
    try:
        response = transport(url, request_timeout)
    except TransportError as error:
        return _ProbeOutcome(False, True, None, "connection_error", _sanitize_excerpt(str(error)))
    return _classify(
        response,
        expected_status,
        expected_entra_tenant_id=expected_entra_tenant_id,
        expected_realm=expected_realm,
    )


def _poll_endpoint(
    url: str,
    path: str,
    expected_status: str,
    *,
    transport: Transport,
    deadline: float,
    warmup_404_deadline: float,
    request_timeout: float,
    backoff: BackoffPolicy,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    expected_entra_tenant_id: str | None = None,
    expected_realm: str | None = None,
) -> EndpointResult:
    """Poll one endpoint until it is healthy, fails fast, or the deadline hits."""
    attempt = 0
    while True:
        attempt += 1
        outcome = _probe(
            url,
            expected_status,
            transport,
            request_timeout,
            expected_entra_tenant_id,
            expected_realm,
        )
        if outcome.healthy:
            return EndpointResult(
                path, True, outcome.status_code, attempt, outcome.reason_code, ""
            )
        if (
            outcome.status_code == 404
            and not outcome.retryable
            and attempt <= WARMUP_404_MAX_ATTEMPTS
            and monotonic() < warmup_404_deadline
        ):
            outcome = _ProbeOutcome(
                False,
                True,
                404,
                "transient_not_found",
                "HTTP 404 during warm-up window",
            )
        if not outcome.retryable:
            return EndpointResult(
                path, False, outcome.status_code, attempt, outcome.reason_code, outcome.detail
            )
        # Transient failure: retry only if a full backoff fits before the
        # deadline. We never sleep past the deadline, so the run stops promptly.
        delay = backoff.delay_for(attempt)
        if monotonic() + delay >= deadline:
            return EndpointResult(
                path,
                False,
                outcome.status_code,
                attempt,
                "deadline_exceeded",
                outcome.detail or "transient failures persisted until the deadline",
            )
        sleep(delay)


def run_smoke_test(
    base_url: str,
    *,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    backoff: BackoffPolicy | None = None,
    transport: Transport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    expected_entra_tenant_id: str | None = None,
) -> SmokeTestResult:
    """Run the liveness+readiness smoke test and return a single verdict.

    ``transport``, ``sleep`` and ``monotonic`` are injectable so tests stay
    hermetic (no real network, no real wall-clock sleeps).
    """
    base = _validate_base_url(base_url)
    if deadline_seconds <= 0:
        raise ValueError("deadline-seconds must be positive")
    if request_timeout_seconds <= 0:
        raise ValueError("request-timeout-seconds must be positive")
    policy = backoff if backoff is not None else BackoffPolicy()
    active_transport = transport if transport is not None else _default_transport
    tenant_id = (
        _validate_entra_tenant_id(expected_entra_tenant_id)
        if expected_entra_tenant_id is not None
        else None
    )
    expected_realm = urlsplit(base).netloc if tenant_id is not None else None

    start = monotonic()
    deadline = start + deadline_seconds

    live = _poll_endpoint(
        base + LIVE_PATH,
        LIVE_PATH,
        LIVE_EXPECTED_STATUS,
        transport=active_transport,
        deadline=deadline,
        warmup_404_deadline=start + WARMUP_404_GRACE_SECONDS,
        request_timeout=request_timeout_seconds,
        backoff=policy,
        sleep=sleep,
        monotonic=monotonic,
        expected_entra_tenant_id=tenant_id,
        expected_realm=expected_realm,
    )
    if live.healthy:
        ready = _poll_endpoint(
            base + READY_PATH,
            READY_PATH,
            READY_EXPECTED_STATUS,
            transport=active_transport,
            deadline=deadline,
            warmup_404_deadline=start + WARMUP_404_GRACE_SECONDS,
            request_timeout=request_timeout_seconds,
            backoff=policy,
            sleep=sleep,
            monotonic=monotonic,
            expected_entra_tenant_id=tenant_id,
            expected_realm=expected_realm,
        )
    else:
        # Short-circuit: no point probing readiness if liveness never came up.
        ready = EndpointResult(
            READY_PATH, False, None, 0, "not_probed", "skipped: /health/live did not pass"
        )

    elapsed = monotonic() - start
    passed = live.healthy and ready.healthy
    total_attempts = live.attempts + ready.attempts

    if passed:
        reason_code = "ok"
        message = (
            "Smoke test passed: /health/live and /health/ready are healthy."
            if tenant_id is None
            else "Smoke test passed: public health paths enforce the expected Entra challenge."
        )
    else:
        failing = live if not live.healthy else ready
        reason_code = f"{_endpoint_label(failing.path)}_{failing.reason_code}"
        message = (
            f"Smoke test failed on {failing.path} "
            f"({failing.reason_code}): {failing.detail}".strip()
        )

    return SmokeTestResult(
        passed=passed,
        reason_code=reason_code,
        message=_sanitize_log(message),
        base_url=base,
        elapsed_seconds=elapsed,
        total_attempts=total_attempts,
        live=live,
        ready=ready,
    )


def _endpoint_label(path: str) -> str:
    return "live" if path == LIVE_PATH else "ready" if path == READY_PATH else "endpoint"


def _validate_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base-url must be a non-empty string")
    trimmed = base_url.strip()
    if not (trimmed.startswith("https://") or trimmed.startswith("http://")):
        raise ValueError("base-url must start with http:// or https://")
    return trimmed.rstrip("/")


def _validate_entra_tenant_id(tenant_id: str) -> str:
    if not _GUID_RE.fullmatch(tenant_id):
        raise ValueError("entra-tenant-id must be a GUID")
    return tenant_id


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr_smoke_test",
        description=(
            "Smoke-test a deployed per-PR Container App by polling /health/live "
            "and /health/ready with bounded exponential backoff. Emits key=value "
            "(GITHUB_OUTPUT-friendly) or JSON and exits non-zero on failure."
        ),
    )
    parser.add_argument("--base-url", required=True, help="deployed Container App base URL")
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=DEFAULT_DEADLINE_SECONDS,
        help="hard overall deadline for both endpoints to become healthy",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        help="per-request HTTP timeout",
    )
    parser.add_argument(
        "--initial-backoff-seconds",
        type=float,
        default=DEFAULT_INITIAL_BACKOFF_SECONDS,
        help="delay after the first transient failure",
    )
    parser.add_argument(
        "--max-backoff-seconds",
        type=float,
        default=DEFAULT_MAX_BACKOFF_SECONDS,
        help="ceiling for the exponential backoff delay",
    )
    parser.add_argument(
        "--backoff-multiplier",
        type=float,
        default=DEFAULT_BACKOFF_MULTIPLIER,
        help="exponential growth factor between retries",
    )
    parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="env",
        help="output format: env (key=value lines) or json",
    )
    parser.add_argument(
        "--entra-tenant-id",
        help=(
            "expect an anonymous HTTP 401 Bearer challenge from this Entra tenant "
            "instead of an anonymous health payload"
        ),
    )
    return parser.parse_args(argv)


def _render_env(fields: dict[str, object]) -> str:
    return "\n".join(f"{key}={_render_value(value)}" for key, value in fields.items())


def _render_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        policy = BackoffPolicy(
            initial_seconds=args.initial_backoff_seconds,
            multiplier=args.backoff_multiplier,
            max_seconds=args.max_backoff_seconds,
        )
        result = run_smoke_test(
            args.base_url,
            deadline_seconds=args.deadline_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            backoff=policy,
            expected_entra_tenant_id=args.entra_tenant_id,
        )
    except ValueError as error:
        # Configuration/usage error (bad URL or knob). base-url can be
        # attacker-influenced on fork PRs, so sanitize before printing.
        print(f"pr_smoke_test: {_sanitize_log(str(error))}", file=sys.stderr)
        return 2

    fields = result.printable_fields()
    if args.format == "json":
        print(json.dumps(fields, sort_keys=True))
    else:
        print(_render_env(fields))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
