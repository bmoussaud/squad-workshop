"""Safety preflight for per-PR ephemeral Azure environments (Phase 1).

Pure, standard-library-only decision logic. It performs NO Azure calls and
queries NO live state -- the current active-environment counts are passed in as
inputs. Every ambiguous or unsafe condition fails closed (``BLOCKED``).

The outcome is an explicit tri-state:

* ``PROCEED`` -- safe to deploy the ephemeral environment.
* ``SKIP``    -- deliberately not deployed, and NOT an error (draft PRs).
* ``BLOCKED`` -- refused for a safety/cost reason (fork, untrusted head repo,
  invalid service name, or an exceeded concurrency cap).

Each result carries a machine-readable ``reason_code`` and a human ``message``
that is always safe to print in CI logs or PR comments (no credentials,
endpoints, prompts, or signed URLs).
"""

from __future__ import annotations

import enum
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow importing the sibling naming module whether this file is imported as a
# package member or loaded by path from CI / tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_environment_names import (  # noqa: E402
    CONTAINER_APP_MAX,
    CONTAINER_APP_MIN,
    MANAGED_ENVIRONMENT_DEFENSIVE_MAX,
    PrEnvironmentNames,
    _CONTAINER_APP_RE,
    is_valid_acr_name,
)

# --- Concurrency caps (security AND cost controls) ----------------------------
APP_TIER_CONCURRENCY_CAP = 3
FOUNDRY_CONCURRENCY_CAP = 1


class Decision(enum.Enum):
    PROCEED = "proceed"
    SKIP = "skip"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PreflightResult:
    decision: Decision
    reason_code: str
    message: str

    @property
    def proceed(self) -> bool:
        return self.decision is Decision.PROCEED


def _blocked(reason_code: str, message: str) -> PreflightResult:
    return PreflightResult(Decision.BLOCKED, reason_code, message)


def _is_bool(value: object) -> bool:
    """True only for a real ``bool``.

    This is the trust-boundary guard: it never treats ``None``, ``0``, ``""`` or
    any other value as a boolean. Truthiness coercion is exactly the fail-open
    defect this replaces, so a missing or malformed signal is rejected rather
    than silently interpreted.
    """
    return value is True or value is False


def _is_nonempty_str(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _non_negative_count(value: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def evaluate(
    *,
    is_fork: bool,
    is_draft: bool,
    base_repo: str,
    head_repo: str,
    names: PrEnvironmentNames,
    referenced_acr_name: str,
    active_app_env_count: int,
    requires_foundry: bool,
    foundry_authorized: bool = False,
    active_foundry_env_count: int = 0,
) -> PreflightResult:
    """Run the Phase-1 preflight checks and return a single decision.

    Checks are ordered so the strongest security gates run first and any
    ambiguity fails closed:

    0. Trust-signal integrity: ``is_fork`` MUST be an explicit boolean;
       ``None``/``0``/``""``/non-bool -> BLOCKED (never coerced).
    1. Fork PRs -> BLOCKED, evaluated FIRST and unconditionally (no credentials).
    2. Head repo must equal base repo, both explicit non-empty strings ->
       BLOCKED otherwise.
    3. Draft signal must be an explicit boolean; draft PRs -> SKIP (not an error).
    4. Every generated service name must satisfy its Azure limit -> BLOCKED
       (opaque field name only; raw values are never echoed).
    5. App-tier concurrency cap (max 3 active) -> BLOCKED when at/over cap.
    6. Foundry exception: ``requires_foundry`` is a required strict boolean so it
       cannot be silently omitted to skip the control. When set, the Foundry path
       additionally REQUIRES an explicit approved ``foundry_authorized`` signal
       (absent/unapproved/unknown fails closed) AND stays under the cap (max 1).
    """
    # 0. Trust-signal integrity for the fork flag -- it decides credential
    #    exposure, so an unrendered/empty/mistyped signal must fail closed.
    if not _is_bool(is_fork):
        return _blocked(
            "invalid_trust_signal",
            "Fork trust signal is missing or not an explicit boolean; failing closed.",
        )

    # 1. Fork PRs never receive credentials -- hard security block, evaluated
    #    first so no later check can short-circuit it.
    if is_fork:
        return _blocked(
            "fork_pr",
            "Fork pull requests receive no Azure credentials; build and test only.",
        )

    # 2. Same-repo trust. Both identifiers must be explicit non-empty strings; a
    #    blank/absent value (e.g. an unrendered Actions context field) fails
    #    closed rather than being treated as trusted.
    if not _is_nonempty_str(base_repo) or not _is_nonempty_str(head_repo):
        return _blocked(
            "untrusted_repo",
            "Repository trust signal is missing or malformed; refusing to deploy.",
        )
    if head_repo != base_repo:
        return _blocked(
            "untrusted_repo",
            "Head repository does not match the base repository; refusing to deploy.",
        )

    # 3. Draft integrity + skip. A malformed draft signal fails closed; a genuine
    #    draft is a deliberate SKIP, not an error.
    if not _is_bool(is_draft):
        return _blocked(
            "invalid_trust_signal",
            "Draft signal is not an explicit boolean; failing closed.",
        )
    if is_draft:
        return PreflightResult(
            Decision.SKIP,
            "draft_pr",
            "Draft pull request; skipping ephemeral deployment until ready for review.",
        )

    # 4. Service-name limit validation. Emit only the opaque field name -- never
    #    the raw generated value, which lands in world-readable CI logs.
    invalid = _invalid_service_name(names, referenced_acr_name)
    if invalid is not None:
        field, _value = invalid
        return _blocked(
            "invalid_service_name",
            f"Generated name for field {field!r} violates its Azure service "
            "limit; failing closed.",
        )

    # 5. App-tier concurrency cap.
    if not _non_negative_count(active_app_env_count):
        return _blocked(
            "app_concurrency_cap",
            "Active app-tier environment count is unknown; failing closed.",
        )
    if active_app_env_count >= APP_TIER_CONCURRENCY_CAP:
        return _blocked(
            "app_concurrency_cap",
            f"App-tier ephemeral concurrency cap reached "
            f"({active_app_env_count}/{APP_TIER_CONCURRENCY_CAP}); failing closed.",
        )

    # 6. Foundry exception. ``requires_foundry`` is mandatory and strictly typed
    #    so it cannot be omitted to bypass the cap. The Foundry path is
    #    cost/RBAC/safety-bearing, so it requires an explicit approved
    #    authorization signal AND must stay under the exception cap; anything
    #    ambiguous fails closed.
    if not _is_bool(requires_foundry):
        return _blocked(
            "invalid_trust_signal",
            "Foundry requirement signal is not an explicit boolean; failing closed.",
        )
    if requires_foundry:
        if not _is_bool(foundry_authorized) or not foundry_authorized:
            return _blocked(
                "foundry_unauthorized",
                "Foundry-per-PR requires explicit approval via the Foundry "
                "provisioning gate; authorization is absent or unapproved. "
                "Failing closed.",
            )
        if not _non_negative_count(active_foundry_env_count):
            return _blocked(
                "foundry_concurrency_cap",
                "Active Foundry environment count is unknown; failing closed.",
            )
        if active_foundry_env_count >= FOUNDRY_CONCURRENCY_CAP:
            return _blocked(
                "foundry_concurrency_cap",
                f"Foundry ephemeral concurrency cap reached "
                f"({active_foundry_env_count}/{FOUNDRY_CONCURRENCY_CAP}); "
                "failing closed.",
            )

    return PreflightResult(
        Decision.PROCEED,
        "ok",
        "Preflight passed; proceeding with the ephemeral environment.",
    )


def _invalid_service_name(
    names: PrEnvironmentNames, referenced_acr_name: str
) -> tuple[str, str] | None:
    """Return ``(field, value)`` for the first name that violates its Azure
    limit, or ``None`` when all names are valid."""
    checks: list[tuple[str, bool, str]] = [
        (
            "storage_account",
            3 <= len(names.storage_account) <= 24
            and names.storage_account.isalnum()
            and names.storage_account.islower(),
            names.storage_account,
        ),
        (
            "container_app",
            CONTAINER_APP_MIN <= len(names.container_app) <= CONTAINER_APP_MAX
            and _CONTAINER_APP_RE.match(names.container_app) is not None,
            names.container_app,
        ),
        (
            # Defensive self-check only: the managed-environment max length is
            # UNVERIFIED (undocumented by Azure). We confirm our own defensive
            # compaction ceiling held, not an authoritative Azure limit.
            "managed_environment",
            1 <= len(names.managed_environment) <= MANAGED_ENVIRONMENT_DEFENSIVE_MAX,
            names.managed_environment,
        ),
        (
            "resource_group",
            1 <= len(names.resource_group) <= 90,
            names.resource_group,
        ),
        (
            "referenced_acr",
            is_valid_acr_name(referenced_acr_name),
            referenced_acr_name,
        ),
    ]
    for field, ok, value in checks:
        if not ok:
            return field, value
    return None
