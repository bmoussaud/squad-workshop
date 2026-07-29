"""Unit tests for the per-PR post-deploy smoke-test script.

The script lives under ``infra/scripts`` (CI/platform tooling, not application
domain logic), so it is loaded by path -- matching the existing
``tests/test_pr_environment_names.py`` convention.

Every test is hermetic: no real network (an injected scripted transport stands
in for ``urllib.request.urlopen``) and no real wall-clock sleeps (sleep and the
monotonic clock are injected, and the tests assert on the backoff *schedule*
rather than on elapsed wall time).
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "infra/scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(module_name: str):
    spec = spec_from_file_location(module_name, SCRIPTS_DIR / f"{module_name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load("pr_smoke_test")

BASE_URL = "https://ca-fc-pr14-rcl-4c32c628.example.azurecontainerapps.io"


def _live_ok() -> "smoke.HttpResponse":
    return smoke.HttpResponse(200, json.dumps({"status": "live"}))


def _ready_ok() -> "smoke.HttpResponse":
    return smoke.HttpResponse(200, json.dumps({"status": "ready"}))


def _resp(status: int, body: str = "") -> "smoke.HttpResponse":
    return smoke.HttpResponse(status, body)


class ScriptedTransport:
    """Injectable transport driven by per-endpoint queues.

    Each queue element is either an ``HttpResponse`` to return or an exception
    instance to raise. When a queue is exhausted its last element repeats, so a
    "persistent" condition needs only a single trailing element.
    """

    def __init__(
        self,
        live: list[object],
        ready: list[object] | None = None,
    ) -> None:
        self._queues = {
            smoke.LIVE_PATH: list(live),
            smoke.READY_PATH: list(ready or []),
        }
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> "smoke.HttpResponse":
        self.calls.append(url)
        path = smoke.LIVE_PATH if url.endswith(smoke.LIVE_PATH) else smoke.READY_PATH
        queue = self._queues[path]
        if not queue:
            raise AssertionError(f"no scripted response for {path}")
        element = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(element, Exception):
            raise element
        return element


class FakeClock:
    """Deterministic monotonic clock: returns start, start+step, start+2*step..."""

    def __init__(self, step: float = 0.0, start: float = 0.0) -> None:
        self.t = start
        self.step = step

    def __call__(self) -> float:
        value = self.t
        self.t += self.step
        return value


class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class SmokeTestHappyPathTests(unittest.TestCase):
    def test_both_endpoints_healthy_on_first_attempt_passes(self) -> None:
        transport = ScriptedTransport(live=[_live_ok()], ready=[_ready_ok()])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.reason_code, "ok")
        self.assertEqual(result.live.attempts, 1)
        self.assertEqual(result.ready.attempts, 1)
        self.assertEqual(result.total_attempts, 2)
        self.assertEqual(result.live.status_code, 200)
        self.assertEqual(result.ready.status_code, 200)
        self.assertEqual(sleep.delays, [])

    def test_ready_flaky_until_attempt_n_then_healthy(self) -> None:
        # /health/live healthy immediately; /health/ready 503s twice (cold
        # start) then becomes ready on the 3rd attempt.
        transport = ScriptedTransport(
            live=[_live_ok()],
            ready=[_resp(503), _resp(503), _ready_ok()],
        )
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=1000.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
            backoff=smoke.BackoffPolicy(initial_seconds=1.0, multiplier=2.0, max_seconds=15.0),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.live.attempts, 1)
        self.assertEqual(result.ready.attempts, 3)
        self.assertEqual(result.total_attempts, 4)
        # Backoff schedule after ready attempts 1 and 2: 1s then 2s.
        self.assertEqual(sleep.delays, [1.0, 2.0])

    def test_connection_error_is_retried_then_recovers(self) -> None:
        transport = ScriptedTransport(
            live=[smoke.TransportError("connection refused"), _live_ok()],
            ready=[_ready_ok()],
        )
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=1000.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.live.attempts, 2)
        self.assertEqual(sleep.delays, [1.0])


class SmokeTestFailureTests(unittest.TestCase):
    def test_persistent_transient_failure_hits_deadline_and_fails(self) -> None:
        # Every probe is a network failure; the clock advances so the deadline
        # is reached and the run stops instead of retrying forever.
        transport = ScriptedTransport(live=[smoke.TransportError("no route to host")])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=10.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=5.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.live.reason_code, "deadline_exceeded")
        self.assertTrue(result.reason_code.startswith("live_"))
        # Readiness is never probed once liveness fails.
        self.assertEqual(result.ready.reason_code, "not_probed")
        self.assertEqual(result.ready.attempts, 0)

    def test_deadline_stops_promptly_and_bounds_attempts(self) -> None:
        # start=0; deadline=10. clock steps by 5 each call.
        #  attempt1 fail -> now=5, delay=1, 5+1<10 -> sleep(1)
        #  attempt2 fail -> now=10, delay=2, 10+2>=10 -> stop.
        transport = ScriptedTransport(live=[smoke.TransportError("warming up")])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=10.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=5.0),
            backoff=smoke.BackoffPolicy(initial_seconds=1.0, multiplier=2.0, max_seconds=15.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.live.attempts, 2)
        # Only one backoff was slept before the deadline halted the loop; the
        # loop did NOT run long past the deadline.
        self.assertEqual(sleep.delays, [1.0])
        self.assertEqual(len(transport.calls), 2)

    def test_early_404_is_retried_then_recovers(self) -> None:
        # ACA ingress can briefly answer 404 while a fresh revision and its route
        # table propagate; health 404s inside the warm-up window should retry.
        transport = ScriptedTransport(live=[_resp(404), _resp(404), _live_ok()], ready=[_ready_ok()])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=1000.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.live.attempts, 3)
        self.assertEqual(sleep.delays, [1.0, 2.0])

    def test_persistent_404_still_fails_closed_after_bounded_grace(self) -> None:
        transport = ScriptedTransport(live=[_resp(404)])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=100000.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.live.reason_code, "unexpected_status")
        self.assertEqual(result.live.status_code, 404)
        self.assertEqual(result.live.attempts, smoke.WARMUP_404_MAX_ATTEMPTS + 1)
        self.assertEqual(len(sleep.delays), smoke.WARMUP_404_MAX_ATTEMPTS)

    def test_500_is_not_retried(self) -> None:
        transport = ScriptedTransport(live=[_resp(500)])
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            deadline_seconds=100000.0,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.live.reason_code, "unexpected_status")
        self.assertEqual(result.live.attempts, 1)
        self.assertEqual(sleep.delays, [])

    def test_each_retryable_status_is_retried_then_recovers(self) -> None:
        # Per-status coverage: 408/429/502/503/504 must each be retried (one
        # transient answer, then healthy => two attempts, one backoff sleep).
        # A single representative case would let a regression silently drop one
        # of these from the retryable set (mutation-confirmed) while CI stays
        # green, so assert every member of RETRYABLE_STATUSES individually.
        self.assertEqual(smoke.RETRYABLE_STATUSES, frozenset({408, 429, 502, 503, 504}))
        for status in sorted(smoke.RETRYABLE_STATUSES):
            with self.subTest(status=status):
                transport = ScriptedTransport(
                    live=[_resp(status), _live_ok()], ready=[_ready_ok()]
                )
                sleep = RecordingSleep()
                result = smoke.run_smoke_test(
                    BASE_URL,
                    deadline_seconds=1000.0,
                    transport=transport,
                    sleep=sleep,
                    monotonic=FakeClock(step=0.0),
                )
                self.assertTrue(result.passed, status)
                self.assertEqual(result.live.attempts, 2, status)
                self.assertEqual(sleep.delays, [1.0], status)

    def test_each_non_retryable_status_fails_fast(self) -> None:
        # The fail-fast side is only pinned by 404/500 in the base suite; assert
        # a spread of other 4xx/5xx answers also fail on the first attempt with
        # no backoff, so none of them can silently drift into the retryable set.
        for status in (400, 401, 403, 405, 409, 418, 451, 500, 501, 505):
            with self.subTest(status=status):
                transport = ScriptedTransport(live=[_resp(status)])
                sleep = RecordingSleep()
                result = smoke.run_smoke_test(
                    BASE_URL,
                    deadline_seconds=100000.0,
                    transport=transport,
                    sleep=sleep,
                    monotonic=FakeClock(step=0.0),
                )
                self.assertFalse(result.passed, status)
                self.assertEqual(result.live.reason_code, "unexpected_status", status)
                self.assertEqual(result.live.attempts, 1, status)
                self.assertEqual(sleep.delays, [], status)

    def test_200_with_wrong_body_fails_fast(self) -> None:
        transport = ScriptedTransport(
            live=[smoke.HttpResponse(200, json.dumps({"status": "not-what-we-deployed"}))]
        )
        sleep = RecordingSleep()

        result = smoke.run_smoke_test(
            BASE_URL,
            transport=transport,
            sleep=sleep,
            monotonic=FakeClock(step=0.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.live.reason_code, "unexpected_body")
        self.assertEqual(result.live.attempts, 1)


class SmokeTestLogSafetyTests(unittest.TestCase):
    def test_control_characters_and_ansi_in_body_are_sanitized(self) -> None:
        malicious = (
            "\x1b[31m{\"status\": \"pwn\"}\x00\n"
            "::error::injected\r"
            "\x1b]0;title\x07"
        )
        transport = ScriptedTransport(
            live=[_live_ok()],
            ready=[smoke.HttpResponse(200, malicious)],
        )

        result = smoke.run_smoke_test(
            BASE_URL,
            transport=transport,
            sleep=RecordingSleep(),
            monotonic=FakeClock(step=0.0),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.ready.reason_code, "unexpected_body")

        # Nothing that gets printed may carry a control character -- that is the
        # invariant that neutralizes log/workflow-command injection, because a
        # ::error:: marker is inert unless it can start a fresh line.
        fields = result.printable_fields()
        for bad in ("\x1b", "\x00", "\n", "\r", "\x07"):
            self.assertNotIn(bad, result.message)
            self.assertNotIn(bad, str(fields["message"]))
            self.assertNotIn(bad, result.ready.detail)

    def test_oversized_body_is_truncated_not_echoed_wholesale(self) -> None:
        huge = json.dumps({"status": "x" * 5000})
        transport = ScriptedTransport(
            live=[_live_ok()],
            ready=[smoke.HttpResponse(200, huge)],
        )
        result = smoke.run_smoke_test(
            BASE_URL,
            transport=transport,
            sleep=RecordingSleep(),
            monotonic=FakeClock(step=0.0),
        )
        self.assertEqual(result.ready.reason_code, "unexpected_body")
        # Only a short excerpt is retained, never the whole body.
        self.assertLess(len(result.ready.detail), 200)

    def test_env_render_never_emits_a_control_character(self) -> None:
        transport = ScriptedTransport(
            live=[_live_ok()],
            ready=[smoke.HttpResponse(200, "garbage\nline\x00two")],
        )
        result = smoke.run_smoke_test(
            BASE_URL,
            transport=transport,
            sleep=RecordingSleep(),
            monotonic=FakeClock(step=0.0),
        )
        rendered = smoke._render_env(result.printable_fields())
        # One key=value per line: the count of newlines equals keys-1.
        self.assertEqual(rendered.count("\n"), len(result.printable_fields()) - 1)
        self.assertNotIn("\x00", rendered)


class SmokeTestCliTests(unittest.TestCase):
    def _run_main(self, argv: list[str], transport) -> tuple[int, str, str]:
        original = smoke._default_transport
        smoke._default_transport = transport  # type: ignore[assignment]
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = smoke.main(argv)
        finally:
            smoke._default_transport = original  # type: ignore[assignment]
        return code, out.getvalue(), err.getvalue()

    def test_main_passes_with_zero_exit_and_env_output(self) -> None:
        transport = ScriptedTransport(live=[_live_ok()], ready=[_ready_ok()])
        code, stdout, _ = self._run_main(["--base-url", BASE_URL], transport)
        self.assertEqual(code, 0)
        self.assertIn("passed=true", stdout)
        self.assertIn("reason_code=ok", stdout)
        self.assertIn("live_status=200", stdout)
        self.assertIn("ready_status=200", stdout)

    def test_main_fails_with_nonzero_exit_on_bad_deploy(self) -> None:
        transport = ScriptedTransport(live=[_resp(404)])
        code, stdout, _ = self._run_main(
            ["--base-url", BASE_URL, "--format", "json"], transport
        )
        self.assertEqual(code, 1)
        payload = json.loads(stdout)
        self.assertFalse(payload["passed"])
        self.assertEqual(payload["live_reason"], "unexpected_status")

    def test_main_rejects_invalid_base_url_with_exit_2(self) -> None:
        transport = ScriptedTransport(live=[_live_ok()])
        code, _stdout, stderr = self._run_main(["--base-url", "ftp://nope"], transport)
        self.assertEqual(code, 2)
        self.assertIn("base-url", stderr)

    def test_cli_has_no_flag_to_disable_tls_verification(self) -> None:
        # Security invariant: certificate verification must never be optional.
        for insecure in ("--insecure", "--no-verify", "--no-check-certificate"):
            with self.assertRaises(SystemExit):
                with redirect_stderr(io.StringIO()):
                    smoke._parse_args(["--base-url", BASE_URL, insecure])


class BackoffPolicyTests(unittest.TestCase):
    def test_delay_grows_exponentially_and_is_capped(self) -> None:
        policy = smoke.BackoffPolicy(initial_seconds=1.0, multiplier=2.0, max_seconds=10.0)
        self.assertEqual(
            [policy.delay_for(n) for n in range(1, 7)],
            [1.0, 2.0, 4.0, 8.0, 10.0, 10.0],
        )

    def test_invalid_policy_raises(self) -> None:
        with self.assertRaises(ValueError):
            smoke.BackoffPolicy(multiplier=0.5)
        with self.assertRaises(ValueError):
            smoke.BackoffPolicy(initial_seconds=-1.0)


if __name__ == "__main__":
    unittest.main()
