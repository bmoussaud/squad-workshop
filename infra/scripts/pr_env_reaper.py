"""TTL reaper decision engine for per-PR ephemeral Azure environments (Phase 4).

Pure, standard-library-only decision logic. It performs NO Azure calls and
mutates NOTHING -- the raw ``az group list`` JSON and the evaluation timestamp
are passed in as inputs, and the caller (Tank's scheduled workflow) performs the
actual ``az group delete`` for whatever this engine selects.

Why this is Python and not inline bash: the janitor is a scheduled job that
holds Azure *delete* permission and runs with no human watching. A logic bug
here does not fail a build -- it destroys someone's environment, or a shared /
production resource group. The blast radius is exactly why the selection logic
must be unit-testable in isolation, hermetically, with the clock injected.

## Reaping is strictly ALLOWLIST-based

A group is NEVER reaped by exclusion. A group becomes a reap candidate ONLY when
it positively proves it is a per-PR ephemeral environment. ALL of these must
hold, or the verdict is ``keep``:

* ``tags`` is present AND is an object (not ``null``, not a list), AND
* ``tags.ephemeral`` is exactly the lowercase string ``"true"``, AND
* ``tags["environment-type"]`` is exactly ``"pr-app"``, AND
* it carries a valid numeric ``pr-number`` tag, AND
* EITHER its ``expires-at`` is a well-formed, timezone-aware timestamp strictly
  in the past, OR its PR number appears in ``--closed-pr-numbers``.

Anything ambiguous fails toward ``keep``. A malformed tag is NEVER treated as
"expired long ago": a naive/garbage/empty ``expires-at`` is ``malformed_expiry``
(keep), not ``expired`` (reap). Naive-vs-aware datetime comparison raises
``TypeError`` in Python; that is handled deliberately by rejecting naive
timestamps before any comparison, so the reaper never crashes on hostile input.

## Reason codes

Reap verdicts:

* ``expired``             -- valid ephemeral pr-app group whose ``expires-at`` is
  strictly before ``--now``.
* ``orphaned_closed_pr``  -- valid ephemeral pr-app group whose PR number is in
  ``--closed-pr-numbers`` (a failed close-time teardown -- the exact case the
  janitor exists to catch). Reaped regardless of expiry.

Keep verdicts (every one is a distinct, asserted reason -- see the tests):

* ``malformed_group``      -- the group entry is not an object, or has no usable
  ``name``.
* ``no_tags``              -- ``tags`` is absent, ``null``, or not an object.
* ``not_ephemeral``        -- ``ephemeral`` tag missing or not exactly ``"true"``.
* ``wrong_environment_type`` -- ``environment-type`` missing or not ``"pr-app"``.
* ``missing_pr_number``    -- ``pr-number`` tag missing/empty.
* ``malformed_pr_number``  -- ``pr-number`` present but not ASCII digits.
* ``malformed_expiry``     -- ``expires-at`` missing, empty, unparseable, or
  timezone-naive (and the PR is not closed).
* ``not_yet_expired``      -- ``expires-at`` is valid and at/after ``--now`` (and
  the PR is not closed).

The product decision (already made): a past-``expires-at`` group is deleted
immediately -- there is NO mark-then-delete grace period.
"""

from __future__ import annotations

import argparse
import enum
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Allow importing the sibling naming module whether this file is imported as a
# package member or loaded by path from CI / tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_environment_names import _sanitize_log  # noqa: E402

# Exit code for malformed / unreadable input (bad JSON, non-array payload, or an
# unparseable ``--now``). Distinct from an argparse usage error (2) so a caller
# can tell "called wrong" from "the data handed to me was garbage", and mirrors
# the spirit of ``pr_preflight.BLOCKED_EXIT_CODE = 3``: never exit 0 on garbage.
MALFORMED_INPUT_EXIT_CODE = 3

# The immutable tag contract stamped by the Phase 3 deploy workflow.
EPHEMERAL_TAG = "ephemeral"
ENVIRONMENT_TYPE_TAG = "environment-type"
PR_NUMBER_TAG = "pr-number"
EXPIRES_AT_TAG = "expires-at"

EPHEMERAL_TRUE = "true"
PR_APP_ENVIRONMENT_TYPE = "pr-app"


class Action(enum.Enum):
    REAP = "reap"
    KEEP = "keep"


@dataclass(frozen=True)
class ReapDecision:
    name: str
    location: str
    action: Action
    reason_code: str
    pr_number: str | None = None

    @property
    def reap(self) -> bool:
        return self.action is Action.REAP

    def printable_fields(self) -> dict[str, object]:
        return {
            "name": _sanitize_log(self.name),
            "location": _sanitize_log(self.location),
            "action": self.action.value,
            "reason_code": self.reason_code,
            "pr_number": self.pr_number,
        }


def _keep(name: str, location: str, reason_code: str, pr_number: str | None = None) -> ReapDecision:
    return ReapDecision(name, location, Action.KEEP, reason_code, pr_number)


def _reap(name: str, location: str, reason_code: str, pr_number: str) -> ReapDecision:
    return ReapDecision(name, location, Action.REAP, reason_code, pr_number)


def _tag_str(tags: dict, key: str) -> str | None:
    """Return the tag value only when it is a genuine string.

    A tag whose value is a bool/number/object/``None`` is treated as absent --
    the contract stamps plain strings, so anything else is malformed and must
    not be coerced (mirrors ``pr_preflight._is_bool`` refusing truthiness).
    """
    value = tags.get(key)
    return value if isinstance(value, str) else None


def _is_ascii_digits(value: str) -> bool:
    stripped = value.strip()
    # ``str.isdigit()`` is True for exotic non-ASCII code points (Arabic-Indic,
    # superscripts) that then mis-parse or crash in ``int()``. Restrict to ASCII
    # digits so a malformed pr-number fails closed to KEEP instead.
    return stripped.isascii() and stripped.isdigit()


def parse_iso8601_utc(raw: object) -> datetime | None:
    """Parse a strict ISO-8601 timestamp into a timezone-AWARE datetime.

    Returns ``None`` for anything that is not a well-formed, timezone-aware
    instant: non-strings, empty strings, garbage, and -- critically --
    timezone-NAIVE timestamps. Returning ``None`` for naive input is what keeps
    the later comparison from raising ``TypeError`` (naive vs aware) and what
    stops a malformed ``expires-at`` from being read as "expired long ago".
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    # ``datetime.fromisoformat`` only learned to accept a trailing ``Z`` in
    # 3.11; normalize it so behavior is identical on older interpreters.
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def parse_closed_pr_numbers(raw: str | None) -> frozenset[int]:
    """Parse ``"12,34"`` into ``{12, 34}``.

    Non-numeric tokens are dropped rather than trusted: a garbage entry must not
    be able to cause a reap, so it simply fails to match any environment.
    """
    if not raw:
        return frozenset()
    numbers: set[int] = set()
    for token in raw.split(","):
        stripped = token.strip()
        if _is_ascii_digits(stripped):
            numbers.add(int(stripped))
    return frozenset(numbers)


def evaluate_group(
    group: object,
    *,
    now: datetime,
    closed_pr_numbers: frozenset[int],
) -> ReapDecision:
    """Evaluate ONE ``az group list`` entry against the allowlist.

    The checks run in allowlist order: each gate must positively pass before the
    next is consulted, and any failure short-circuits to a specific ``keep``
    reason. Only after every identity gate passes is the reap trigger
    (closed-PR, then expiry) considered.
    """
    if not isinstance(group, dict):
        return _keep("", "", "malformed_group")

    name_raw = group.get("name")
    name = name_raw if isinstance(name_raw, str) and name_raw.strip() else ""
    location_raw = group.get("location")
    location = location_raw if isinstance(location_raw, str) else ""
    if not name:
        return _keep("", location, "malformed_group")

    # Gate 1: tags must be a real object. ``null`` or a list is NOT an object.
    tags = group.get("tags")
    if not isinstance(tags, dict):
        return _keep(name, location, "no_tags")

    # Gate 2: ephemeral must be EXACTLY the lowercase string "true".
    if _tag_str(tags, EPHEMERAL_TAG) != EPHEMERAL_TRUE:
        return _keep(name, location, "not_ephemeral")

    # Gate 3: environment-type must be EXACTLY "pr-app". This is the gate that
    # protects the shared ACR / Foundry / production groups in the same
    # subscription -- they never carry this value.
    if _tag_str(tags, ENVIRONMENT_TYPE_TAG) != PR_APP_ENVIRONMENT_TYPE:
        return _keep(name, location, "wrong_environment_type")

    # Gate 4: a valid, numeric pr-number.
    pr_number_raw = _tag_str(tags, PR_NUMBER_TAG)
    if pr_number_raw is None or not pr_number_raw.strip():
        return _keep(name, location, "missing_pr_number")
    if not _is_ascii_digits(pr_number_raw):
        return _keep(name, location, "malformed_pr_number", pr_number_raw)
    pr_number = pr_number_raw.strip()

    # Trigger A: a closed PR is reaped regardless of expiry -- a failed
    # close-time teardown is exactly what the janitor exists to catch. Checked
    # BEFORE expiry so a closed PR with a malformed expires-at is still reaped.
    if int(pr_number) in closed_pr_numbers:
        return _reap(name, location, "orphaned_closed_pr", pr_number)

    # Trigger B: a well-formed, timezone-aware expiry strictly in the past.
    expires_at = parse_iso8601_utc(tags.get(EXPIRES_AT_TAG))
    if expires_at is None:
        return _keep(name, location, "malformed_expiry", pr_number)
    if now > expires_at:
        return _reap(name, location, "expired", pr_number)
    return _keep(name, location, "not_yet_expired", pr_number)


def evaluate_groups(
    groups: list,
    *,
    now: datetime,
    closed_pr_numbers: frozenset[int],
) -> list[ReapDecision]:
    return [
        evaluate_group(group, now=now, closed_pr_numbers=closed_pr_numbers)
        for group in groups
    ]


# --- CLI ----------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr_env_reaper",
        description=(
            "Decide which per-PR ephemeral Azure resource groups to reap, from a "
            "raw 'az group list' JSON payload and an injected evaluation time. "
            "Strictly allowlist-based: a group is reaped only when it positively "
            "proves it is a per-PR ephemeral environment. Performs no Azure "
            "calls. Exits non-zero only on malformed/unreadable input."
        ),
    )
    parser.add_argument(
        "--groups-json",
        required=True,
        help="path to the 'az group list' JSON array, or '-' to read stdin",
    )
    parser.add_argument(
        "--now",
        required=True,
        help="ISO-8601 UTC evaluation timestamp (injected; never the wall clock)",
    )
    parser.add_argument(
        "--closed-pr-numbers",
        default="",
        help="optional comma-separated PR numbers to reap as orphans (e.g. '12,34')",
    )
    parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="env",
        help="output format: env (GITHUB_OUTPUT lines) or json (full decision list)",
    )
    return parser.parse_args(argv)


def _read_groups_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def _fail_malformed(message: str, output_format: str) -> int:
    safe = _sanitize_log(message)
    if output_format == "json":
        print(json.dumps({"error": safe}, sort_keys=True))
    else:
        print(f"error={safe}")
    return MALFORMED_INPUT_EXIT_CODE


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    now = parse_iso8601_utc(args.now)
    if now is None:
        return _fail_malformed(
            "--now is not a well-formed timezone-aware ISO-8601 timestamp",
            args.format,
        )

    try:
        raw_text = _read_groups_text(args.groups_json)
    except OSError as error:
        return _fail_malformed(f"could not read --groups-json: {error}", args.format)

    try:
        groups = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as error:
        return _fail_malformed(f"--groups-json is not valid JSON: {error}", args.format)

    if not isinstance(groups, list):
        return _fail_malformed(
            "--groups-json must be a JSON array of resource groups", args.format
        )

    closed = parse_closed_pr_numbers(args.closed_pr_numbers)
    decisions = evaluate_groups(groups, now=now, closed_pr_numbers=closed)
    _emit(decisions, args.format)
    return 0


def _emit(decisions: list[ReapDecision], output_format: str) -> None:
    reap_names = [_sanitize_log(d.name) for d in decisions if d.reap]
    if output_format == "json":
        payload = {
            "reap_count": len(reap_names),
            "reap_names": reap_names,
            "decisions": [d.printable_fields() for d in decisions],
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        # ``reap_names`` is a space-separated list (Azure RG names never contain
        # spaces) suitable for a $GITHUB_OUTPUT line the workflow reads back.
        print(f"reap_count={len(reap_names)}")
        print(f"reap_names={' '.join(reap_names)}")


if __name__ == "__main__":
    raise SystemExit(main())
