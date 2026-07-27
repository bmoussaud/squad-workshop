"""Unit tests for the ``pr_env_reaper`` TTL decision engine (Phase 4, #20).

The reaper lives under ``infra/scripts`` (CI/platform tooling, not application
domain logic), so it is loaded by path -- matching the existing
``tests/test_pr_preflight_cli.py`` / ``tests/test_pr_environment_names.py``
convention.

Every test is hermetic: the evaluation clock is always injected via ``--now``
(or the ``now=`` keyword) and never read from the wall clock, no network is
touched, and no real sleeps occur.

The suite is written to survive mutation testing. In particular EACH individual
condition of the allowlist is pinned by its own test that flips exactly that one
condition and asserts the specific ``reason_code`` -- a suite that only ever
exercised "perfectly valid group" vs "totally empty group" would let someone
delete a single allowlist condition without any test failing.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


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


reaper = _load("pr_env_reaper")

NOW = datetime(2026, 7, 27, 21, 0, 0, tzinfo=timezone.utc)
PAST = "2026-07-20T21:00:00Z"          # 7 days before NOW
FUTURE = "2026-08-03T21:00:00Z"        # 7 days after NOW


def _group(
    name: str = "rg-pr-14-render-card-layout-4c32c628",
    *,
    location: str = "eastus2",
    ephemeral: str | None = "true",
    environment_type: str | None = "pr-app",
    pr_number: str | None = "14",
    expires_at: str | None = PAST,
    author: str = "octocat",
    tags: object = "__default__",
) -> dict:
    """Build a realistically-shaped ``az group list`` entry.

    Pass ``tags=<value>`` to override the whole tag object (e.g. ``None`` or a
    list). Otherwise individual tag keys are omitted when their argument is
    ``None``, so a single missing tag can be modeled precisely.
    """
    if tags != "__default__":
        return {"name": name, "location": location, "tags": tags}
    built: dict[str, str] = {}
    if ephemeral is not None:
        built["ephemeral"] = ephemeral
    if environment_type is not None:
        built["environment-type"] = environment_type
    if pr_number is not None:
        built["pr-number"] = pr_number
    if expires_at is not None:
        built["expires-at"] = expires_at
    built["author"] = author
    built["created-at"] = "2026-07-13T21:00:00Z"
    built["repo"] = "bmoussaud/squad-workshop"
    built["branch"] = "squad/14-render-card-layout"
    return {"name": name, "location": location, "tags": built}


def _decide(group: dict, *, closed: frozenset[int] = frozenset()) -> "reaper.ReapDecision":
    return reaper.evaluate_group(group, now=NOW, closed_pr_numbers=closed)


class ReapPositivePathTests(unittest.TestCase):
    """The two ways a group legitimately becomes a reap candidate."""

    def test_expired_ephemeral_pr_app_is_reaped(self) -> None:
        decision = _decide(_group(expires_at=PAST))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.action, reaper.Action.REAP)
        self.assertEqual(decision.reason_code, "expired")
        self.assertEqual(decision.pr_number, "14")

    def test_closed_pr_is_reaped_as_orphan_even_when_not_expired(self) -> None:
        # Not expired (future expiry) but the PR is closed -> orphaned teardown.
        decision = _decide(_group(expires_at=FUTURE), closed=frozenset({14}))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "orphaned_closed_pr")

    def test_closed_pr_is_reaped_even_when_expiry_is_malformed(self) -> None:
        # The closed-PR trigger must be checked BEFORE expiry parsing, so a
        # failed-teardown env with a garbage expires-at is still reaped.
        decision = _decide(_group(expires_at="not-a-date"), closed=frozenset({14}))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "orphaned_closed_pr")


class AllowlistConditionTests(unittest.TestCase):
    """Flip exactly ONE allowlist condition at a time; assert the exact reason.

    A default ``_group()`` is a valid reap candidate, so each test below changes
    a single field and proves that removing/loosening that one gate flips the
    verdict to KEEP with a *specific* reason -- which is what catches a mutation
    that deletes an individual condition.
    """

    def test_default_group_is_the_positive_control(self) -> None:
        self.assertTrue(_decide(_group()).reap)

    def test_tags_missing_entirely_is_kept(self) -> None:
        group = {"name": "rg-pr-14-x", "location": "eastus2"}
        decision = _decide(group)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "no_tags")

    def test_tags_null_is_kept(self) -> None:
        decision = _decide(_group(tags=None))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "no_tags")

    def test_tags_as_list_is_kept(self) -> None:
        decision = _decide(_group(tags=["ephemeral=true"]))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "no_tags")

    def test_missing_ephemeral_tag_is_kept(self) -> None:
        decision = _decide(_group(ephemeral=None))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_ephemeral")

    def test_ephemeral_wrong_casing_is_kept(self) -> None:
        for value in ("TRUE", "True", "1", "yes"):
            with self.subTest(value=value):
                decision = _decide(_group(ephemeral=value))
                self.assertFalse(decision.reap)
                self.assertEqual(decision.reason_code, "not_ephemeral")

    def test_ephemeral_with_whitespace_is_kept(self) -> None:
        decision = _decide(_group(ephemeral=" true "))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_ephemeral")

    def test_missing_environment_type_is_kept(self) -> None:
        decision = _decide(_group(environment_type=None))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "wrong_environment_type")

    def test_wrong_environment_type_is_kept(self) -> None:
        for value in ("pr-foundry", "prod", "shared", "PR-APP"):
            with self.subTest(value=value):
                decision = _decide(_group(environment_type=value))
                self.assertFalse(decision.reap)
                self.assertEqual(decision.reason_code, "wrong_environment_type")

    def test_missing_pr_number_is_kept(self) -> None:
        decision = _decide(_group(pr_number=None))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "missing_pr_number")

    def test_empty_pr_number_is_kept(self) -> None:
        decision = _decide(_group(pr_number="   "))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "missing_pr_number")

    def test_non_numeric_pr_number_is_kept(self) -> None:
        for value in ("abc", "14a", "1.0", "-3", "\u0665"):
            with self.subTest(value=value):
                decision = _decide(_group(pr_number=value))
                self.assertFalse(decision.reap)
                self.assertEqual(decision.reason_code, "malformed_pr_number")

    def test_not_yet_expired_is_kept(self) -> None:
        decision = _decide(_group(expires_at=FUTURE))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_yet_expired")

    def test_expiry_exactly_now_is_kept_not_reaped(self) -> None:
        # Strictly-in-the-past means expires-at == now is NOT yet expired.
        decision = _decide(_group(expires_at="2026-07-27T21:00:00Z"))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_yet_expired")

    def test_one_second_past_expiry_is_reaped(self) -> None:
        decision = _decide(_group(expires_at="2026-07-27T20:59:59Z"))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "expired")


class MalformedExpiryTests(unittest.TestCase):
    """A malformed expiry must be KEPT, never read as 'expired long ago'."""

    def test_missing_expires_at_is_kept_as_malformed(self) -> None:
        decision = _decide(_group(expires_at=None))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_expiry")

    def test_empty_expires_at_is_kept_as_malformed(self) -> None:
        decision = _decide(_group(expires_at=""))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_expiry")

    def test_garbage_expires_at_is_kept_as_malformed(self) -> None:
        decision = _decide(_group(expires_at="not-a-date"))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_expiry")

    def test_naive_expires_at_is_kept_not_crashed(self) -> None:
        # A timezone-naive timestamp would raise TypeError if compared to the
        # aware ``now``. It must be rejected as malformed BEFORE any comparison.
        decision = _decide(_group(expires_at="2026-07-20T21:00:00"))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_expiry")

    def test_far_future_expiry_is_kept(self) -> None:
        decision = _decide(_group(expires_at="2999-01-01T00:00:00Z"))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_yet_expired")

    def test_far_past_expiry_is_reaped(self) -> None:
        decision = _decide(_group(expires_at="2000-01-01T00:00:00Z"))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "expired")

    def test_expires_at_non_string_is_kept_as_malformed(self) -> None:
        # A JSON number/bool for expires-at is not a valid timestamp.
        group = _group()
        group["tags"]["expires-at"] = 1234567890
        decision = _decide(group)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_expiry")

    def test_plus_offset_expiry_is_supported(self) -> None:
        # A non-Z but aware offset is still a valid instant.
        decision = _decide(_group(expires_at="2026-07-20T21:00:00+00:00"))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "expired")


class SharedAndProductionSafetyTests(unittest.TestCase):
    """The catastrophe guard: shared/production groups must NEVER be reaped."""

    def test_shared_acr_group_is_never_reaped(self) -> None:
        shared_acr = {
            "name": "rg-shared-acr-fantasycards",
            "location": "eastus2",
            "tags": {
                "purpose": "shared-container-registry",
                "owner": "platform",
                "cost-center": "shared",
            },
        }
        decision = _decide(shared_acr)
        self.assertFalse(decision.reap)
        # Carries none of the pr-app allowlist tags, so it is rejected at the
        # first gate it fails -- proving a refactor that loosens the filter and
        # lets this shared group through would break this test.
        self.assertEqual(decision.reason_code, "not_ephemeral")

    def test_shared_foundry_group_is_never_reaped(self) -> None:
        shared_foundry = {
            "name": "rg-shared-foundry-prod",
            "location": "swedencentral",
            "tags": {
                "environment-type": "shared-foundry",
                "ephemeral": "false",
                "expires-at": "2000-01-01T00:00:00Z",  # long past, but NOT pr-app
            },
        }
        decision = _decide(shared_foundry)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_ephemeral")

    def test_production_group_with_no_tags_is_never_reaped(self) -> None:
        prod = {"name": "rg-fantasy-cards-prod", "location": "eastus2"}
        decision = _decide(prod)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "no_tags")

    def test_group_named_like_a_pr_env_but_untagged_is_kept(self) -> None:
        # Reaping is allowlist-based, NEVER name-based: a group whose NAME looks
        # like a PR env but carries no tags must be kept.
        look_alike = {"name": "rg-pr-14-render-card-layout-deadbeef", "tags": None}
        decision = _decide(look_alike)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "no_tags")


class MalformedGroupShapeTests(unittest.TestCase):
    def test_non_object_group_is_kept(self) -> None:
        for junk in ("a string", 123, None, ["list"]):
            with self.subTest(junk=junk):
                decision = _decide(junk)  # type: ignore[arg-type]
                self.assertFalse(decision.reap)
                self.assertEqual(decision.reason_code, "malformed_group")

    def test_group_without_name_is_kept(self) -> None:
        no_name = {"location": "eastus2", "tags": _group()["tags"]}
        decision = _decide(no_name)
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "malformed_group")


class ClosedPrParsingTests(unittest.TestCase):
    def test_parse_closed_pr_numbers_basic(self) -> None:
        self.assertEqual(reaper.parse_closed_pr_numbers("12,34"), frozenset({12, 34}))

    def test_parse_closed_pr_numbers_tolerates_spaces_and_blanks(self) -> None:
        self.assertEqual(
            reaper.parse_closed_pr_numbers(" 12 , ,34,"), frozenset({12, 34})
        )

    def test_parse_closed_pr_numbers_drops_garbage_tokens(self) -> None:
        # Garbage must not be trusted into a reap trigger.
        self.assertEqual(reaper.parse_closed_pr_numbers("12,abc,-3,1.0"), frozenset({12}))

    def test_parse_closed_pr_numbers_empty(self) -> None:
        self.assertEqual(reaper.parse_closed_pr_numbers(""), frozenset())
        self.assertEqual(reaper.parse_closed_pr_numbers(None), frozenset())

    def test_closed_pr_number_normalizes_leading_zeros(self) -> None:
        # tag "014" and closed list "14" refer to the same PR.
        decision = _decide(_group(pr_number="014", expires_at=FUTURE), closed=frozenset({14}))
        self.assertTrue(decision.reap)
        self.assertEqual(decision.reason_code, "orphaned_closed_pr")

    def test_unrelated_closed_pr_does_not_reap_a_live_env(self) -> None:
        decision = _decide(_group(expires_at=FUTURE), closed=frozenset({999}))
        self.assertFalse(decision.reap)
        self.assertEqual(decision.reason_code, "not_yet_expired")


class Iso8601ParserTests(unittest.TestCase):
    def test_valid_z_form_is_aware(self) -> None:
        parsed = reaper.parse_iso8601_utc("2026-07-20T21:00:00Z")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertIsNotNone(parsed.utcoffset())

    def test_naive_returns_none(self) -> None:
        self.assertIsNone(reaper.parse_iso8601_utc("2026-07-20T21:00:00"))

    def test_hostile_inputs_return_none(self) -> None:
        for hostile in ("", "   ", "not-a-date", None, 12345, "2026-13-01T00:00:00Z"):
            with self.subTest(hostile=hostile):
                self.assertIsNone(reaper.parse_iso8601_utc(hostile))


# --- CLI ----------------------------------------------------------------------


def _run(groups: object, *, now: str = "2026-07-27T21:00:00Z",
         closed: str | None = None, fmt: str = "json") -> tuple[int, str]:
    """Invoke the CLI with groups piped via stdin; return (exit_code, stdout)."""
    argv = ["--groups-json", "-", "--now", now, "--format", fmt]
    if closed is not None:
        argv += ["--closed-pr-numbers", closed]
    stdin_backup = sys.stdin
    sys.stdin = io.StringIO(json.dumps(groups) if not isinstance(groups, str) else groups)
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            code = reaper.main(argv)
    finally:
        sys.stdin = stdin_backup
    return code, out.getvalue()


class ReaperCliTests(unittest.TestCase):
    def test_json_output_lists_every_decision_and_reap_names(self) -> None:
        groups = [
            _group(name="rg-pr-14-expired", pr_number="14", expires_at=PAST),
            _group(name="rg-pr-20-live", pr_number="20", expires_at=FUTURE),
            {"name": "rg-shared-acr", "tags": None},
        ]
        code, stdout = _run(groups)
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["reap_count"], 1)
        self.assertEqual(payload["reap_names"], ["rg-pr-14-expired"])
        self.assertEqual(len(payload["decisions"]), 3)
        by_name = {d["name"]: d for d in payload["decisions"]}
        self.assertEqual(by_name["rg-pr-14-expired"]["action"], "reap")
        self.assertEqual(by_name["rg-pr-20-live"]["reason_code"], "not_yet_expired")
        self.assertEqual(by_name["rg-shared-acr"]["reason_code"], "no_tags")

    def test_env_output_emits_reap_names_and_count_lines(self) -> None:
        groups = [
            _group(name="rg-pr-14-expired", pr_number="14", expires_at=PAST),
            _group(name="rg-pr-20-live", pr_number="20", expires_at=FUTURE),
        ]
        code, stdout = _run(groups, fmt="env")
        self.assertEqual(code, 0)
        lines = [ln for ln in stdout.splitlines() if ln]
        self.assertIn("reap_count=1", lines)
        self.assertIn("reap_names=rg-pr-14-expired", lines)

    def test_closed_pr_numbers_flag_drives_orphan_reaping(self) -> None:
        groups = [_group(name="rg-pr-34-live", pr_number="34", expires_at=FUTURE)]
        code, stdout = _run(groups, closed="34", fmt="json")
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["reap_count"], 1)
        self.assertEqual(payload["decisions"][0]["reason_code"], "orphaned_closed_pr")

    def test_empty_group_list_is_success_with_no_reaps(self) -> None:
        code, stdout = _run([])
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["reap_count"], 0)
        self.assertEqual(payload["reap_names"], [])
        self.assertEqual(payload["decisions"], [])

    def test_malformed_json_exits_nonzero_distinct_from_usage(self) -> None:
        code, stdout = _run("{not json", fmt="json")
        self.assertEqual(code, reaper.MALFORMED_INPUT_EXIT_CODE)
        self.assertIn("error", json.loads(stdout))

    def test_non_array_payload_is_malformed_input(self) -> None:
        code, _ = _run({"name": "not-a-list"}, fmt="json")
        self.assertEqual(code, reaper.MALFORMED_INPUT_EXIT_CODE)

    def test_malformed_now_is_malformed_input_not_a_crash(self) -> None:
        code, stdout = _run([], now="not-a-date", fmt="json")
        self.assertEqual(code, reaper.MALFORMED_INPUT_EXIT_CODE)
        self.assertIn("error", json.loads(stdout))

    def test_naive_now_is_rejected(self) -> None:
        code, _ = _run([], now="2026-07-27T21:00:00", fmt="json")
        self.assertEqual(code, reaper.MALFORMED_INPUT_EXIT_CODE)

    def test_missing_required_arg_is_usage_error_exit_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            reaper._parse_args([])
        self.assertEqual(ctx.exception.code, 2)

    def test_reader_reads_from_file_path(self) -> None:
        payload = [_group(name="rg-pr-14-expired", expires_at=PAST)]
        tmp = Path(__file__).resolve().parent / "_reaper_fixture.json"
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = reaper.main(
                    ["--groups-json", str(tmp), "--now", "2026-07-27T21:00:00Z",
                     "--format", "json"]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())["reap_count"], 1)
        finally:
            tmp.unlink()


class OutputSafetyTests(unittest.TestCase):
    def test_control_characters_in_group_name_are_sanitized(self) -> None:
        # A tag value or name that smuggles a newline / workflow command must
        # never survive into the emitted output as a control character.
        groups = [_group(name="rg-pr-14-x\n::error::pwn\r", expires_at=PAST)]
        code, stdout = _run(groups, fmt="env")
        self.assertEqual(code, 0)
        # reap_count + reap_names => exactly two lines; injection would add more.
        self.assertEqual(len([ln for ln in stdout.splitlines() if ln]), 2)
        self.assertNotIn("::error::pwn", stdout.split("reap_names=", 1)[0])

    def test_json_output_has_no_raw_control_characters(self) -> None:
        groups = [_group(name="rg\x00pr\n14", expires_at=PAST)]
        code, stdout = _run(groups, fmt="json")
        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        for name in payload["reap_names"]:
            self.assertNotIn("\x00", name)
            self.assertNotIn("\n", name)


if __name__ == "__main__":
    unittest.main()
