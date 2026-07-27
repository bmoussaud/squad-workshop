"""Unit tests for the per-PR environment naming and preflight modules.

The modules live under ``infra/scripts`` (CI/platform tooling, not application
domain logic), so they are loaded by path -- matching the existing
``tests/test_retire_legacy_storage_blob_role.py`` convention.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import sys
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "infra/scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(module_name: str):
    spec = spec_from_file_location(module_name, SCRIPTS_DIR / f"{module_name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    # Register before exec so dataclasses (with future annotations) can resolve
    # the owning module while processing fields.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


naming = _load("pr_environment_names")
preflight = _load("pr_preflight")

REPO = "bmoussaud/squad-workshop"

# The design doc's worked example claims hash8 == "4717e5bb", but the *stated*
# rule sha256("bmoussaud/squad-workshop|14|render-card-layout") actually yields
# "4c32c628". We implement the rule as written and assert the computed value.
# See .squad/decisions/inbox for the adjudication note.
EXPECTED_PR14_HASH8 = "4c32c628"


class SlugExtractionTests(unittest.TestCase):
    def test_extracts_slug_from_conforming_branch(self) -> None:
        self.assertEqual(
            naming.slug_from_branch("squad/14-render-card-layout"),
            "render-card-layout",
        )

    def test_sanitizes_uppercase_and_separators(self) -> None:
        self.assertEqual(
            naming.slug_from_branch("squad/7-Fix__Login  Validation--Now"),
            "fix-login-validation-now",
        )

    def test_rejects_non_squad_branch(self) -> None:
        for branch in ("main", "feature/x", "squad/render-card", "squad/0-x"):
            with self.assertRaises(ValueError):
                naming.slug_from_branch(branch)

    def test_rejects_empty_slug_after_sanitization(self) -> None:
        with self.assertRaises(ValueError):
            naming.slug_from_branch("squad/3-___")

    def test_rejects_blank_branch(self) -> None:
        with self.assertRaises(ValueError):
            naming.slug_from_branch("   ")


class Hash8Tests(unittest.TestCase):
    def test_exact_input_format_repo_pipe_number_pipe_slug(self) -> None:
        expected = hashlib.sha256(
            b"bmoussaud/squad-workshop|14|render-card-layout"
        ).hexdigest()[:8]
        self.assertEqual(naming.hash8(REPO, 14, "render-card-layout"), expected)
        self.assertEqual(expected, EXPECTED_PR14_HASH8)

    def test_is_deterministic(self) -> None:
        a = naming.hash8(REPO, 14, "render-card-layout")
        b = naming.hash8(REPO, 14, "render-card-layout")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in a))

    def test_differs_by_number_and_slug_and_repo(self) -> None:
        base = naming.hash8(REPO, 14, "render-card-layout")
        self.assertNotEqual(base, naming.hash8(REPO, 15, "render-card-layout"))
        self.assertNotEqual(base, naming.hash8(REPO, 14, "render-card"))
        self.assertNotEqual(base, naming.hash8("other/repo", 14, "render-card-layout"))

    def test_rejects_bad_pr_number(self) -> None:
        for bad in (0, -1, True, "14"):
            with self.assertRaises(ValueError):
                naming.hash8(REPO, bad, "slug")  # type: ignore[arg-type]


class WorkedExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.names = naming.compute_names(REPO, 14, "squad/14-render-card-layout")

    def test_environment_name(self) -> None:
        self.assertEqual(
            self.names.environment_name,
            f"pr-14-render-card-layout-{EXPECTED_PR14_HASH8}",
        )

    def test_storage_account(self) -> None:
        # Design doc example: "stfcpr144717e5bb" -- hash8 corrected to computed value.
        self.assertEqual(self.names.storage_account, f"stfcpr14{EXPECTED_PR14_HASH8}")

    def test_container_app(self) -> None:
        # Design doc example: "ca-fc-pr14-rcl-4717e5bb" -- hash8 corrected.
        self.assertEqual(self.names.container_app, f"ca-fc-pr14-rcl-{EXPECTED_PR14_HASH8}")


class StorageInvariantTests(unittest.TestCase):
    def test_lowercase_alnum_and_length(self) -> None:
        for pr in (1, 14, 99, 123456):
            digest = naming.hash8(REPO, pr, "slug")
            name = naming.storage_account_name(pr, digest)
            self.assertTrue(name.isalnum(), name)
            self.assertTrue(name.islower(), name)
            self.assertLessEqual(len(name), naming.STORAGE_MAX, name)
            self.assertGreaterEqual(len(name), naming.STORAGE_MIN, name)

    def test_truncates_only_pr_token_preserving_hash8(self) -> None:
        huge = 10**20  # 21 digits, far beyond the 24-char budget
        digest = naming.hash8(REPO, huge, "slug")
        name = naming.storage_account_name(huge, digest)
        self.assertLessEqual(len(name), naming.STORAGE_MAX)
        self.assertTrue(name.endswith(digest))


class ContainerAppInvariantTests(unittest.TestCase):
    def test_within_32_for_normal_slug(self) -> None:
        digest = naming.hash8(REPO, 14, "render-card-layout")
        name = naming.container_app_name(14, "render-card-layout", digest)
        self.assertLessEqual(len(name), naming.CONTAINER_APP_MAX)

    def test_pathological_long_slug_still_within_32(self) -> None:
        slug = "-".join(f"word{i}" for i in range(40))
        digest = naming.hash8(REPO, 987654, slug)
        name = naming.container_app_name(987654, slug, digest)
        self.assertLessEqual(len(name), naming.CONTAINER_APP_MAX)
        self.assertTrue(name.startswith("ca-fc-pr987654-"))
        self.assertTrue(name.endswith(digest))

    def test_starts_with_letter_and_ends_alphanumeric(self) -> None:
        for pr, slug in ((14, "render-card-layout"), (5, "x"), (99, "a-b-c-d")):
            digest = naming.hash8(REPO, pr, slug)
            name = naming.container_app_name(pr, slug, digest)
            self.assertTrue(name[0].isalpha() and name[0].islower(), name)
            self.assertTrue(name[-1].isalnum(), name)
            self.assertFalse(name.endswith("-"), name)
            self.assertGreaterEqual(len(name), naming.CONTAINER_APP_MIN, name)
            self.assertRegex(name, r"^[a-z][a-z0-9-]*[a-z0-9]$")

    def test_degenerate_single_char_slug_produces_valid_name(self) -> None:
        # slug -> single-char compact token: must not yield a trailing hyphen or
        # a hyphen-adjacent truncation artifact.
        names = naming.compute_names(REPO, 5, "squad/5-x")
        name = names.container_app
        self.assertEqual(name, f"ca-fc-pr5-x-{names.hash8}")
        self.assertRegex(name, r"^[a-z][a-z0-9-]*[a-z0-9]$")

    def test_pathological_long_slug_never_ends_with_hyphen(self) -> None:
        # Force truncation of slug_compact against a large PR token so the tail
        # of the acronym is trimmed; the name must still end at hash8, not '-'.
        slug = "-".join(f"seg{i}" for i in range(30))
        digest = naming.hash8(REPO, 999999, slug)
        name = naming.container_app_name(999999, slug, digest)
        self.assertFalse(name.endswith("-"), name)
        self.assertRegex(name, r"^[a-z][a-z0-9-]*[a-z0-9]$")


class AcrReferenceValidationTests(unittest.TestCase):
    def test_valid_names(self) -> None:
        self.assertTrue(naming.is_valid_acr_name("acrfantasycards"))
        self.assertTrue(naming.is_valid_acr_name("abc12"))
        self.assertTrue(naming.is_valid_acr_name("a" * 50))

    def test_invalid_names(self) -> None:
        self.assertFalse(naming.is_valid_acr_name("abcd"))  # too short (<5)
        self.assertFalse(naming.is_valid_acr_name("a" * 51))  # too long (>50)
        self.assertFalse(naming.is_valid_acr_name("has-hyphen"))
        self.assertFalse(naming.is_valid_acr_name("has_underscore"))
        self.assertFalse(naming.is_valid_acr_name(""))
        self.assertFalse(naming.is_valid_acr_name(None))  # type: ignore[arg-type]


class ComputeNamesValidationTests(unittest.TestCase):
    def test_rejects_non_conforming_branch(self) -> None:
        with self.assertRaises(ValueError):
            naming.compute_names(REPO, 14, "main")

    def test_rejects_bad_pr_number(self) -> None:
        with self.assertRaises(ValueError):
            naming.compute_names(REPO, 0, "squad/14-x")


class PropertySweepTests(unittest.TestCase):
    SLUGS = [
        "a",
        "render-card-layout",
        "fix-login",
        "-".join(["seg"] * 25),
        "a-b-c-d-e-f-g-h-i-j-k-l-m-n-o-p",
        "verylongsinglewordwithnoseparatorsatallhere",
    ]
    PRS = [1, 9, 14, 99, 1000, 999999]

    def test_every_generated_name_respects_limits(self) -> None:
        for pr in self.PRS:
            for slug in self.SLUGS:
                names = naming.compute_names(REPO, pr, f"squad/{pr}-{slug}")
                st = names.storage_account
                self.assertTrue(3 <= len(st) <= 24 and st.isalnum() and st.islower(), st)
                self.assertLessEqual(len(names.container_app), 32, names.container_app)
                self.assertRegex(names.container_app, r"^[a-z][a-z0-9-]*[a-z0-9]$")
                self.assertGreaterEqual(len(names.container_app), 2, names.container_app)
                self.assertLessEqual(
                    len(names.managed_environment), 32, names.managed_environment
                )
                self.assertLessEqual(len(names.resource_group), 90)
                self.assertTrue(names.environment_name.startswith(f"pr-{pr}-"))
                self.assertTrue(names.environment_name.endswith(names.hash8))


class CliTests(unittest.TestCase):
    def test_env_format_emits_key_values(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = naming.main(
                [
                    "--repo",
                    REPO,
                    "--pr-number",
                    "14",
                    "--branch",
                    "squad/14-render-card-layout",
                ]
            )
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertIn(f"environment_name=pr-14-render-card-layout-{EXPECTED_PR14_HASH8}", out)
        self.assertIn(f"storage_account=stfcpr14{EXPECTED_PR14_HASH8}", out)

    def test_json_format_is_parseable(self) -> None:
        import io
        import json
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = naming.main(
                [
                    "--repo",
                    REPO,
                    "--pr-number",
                    "14",
                    "--branch",
                    "squad/14-render-card-layout",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["hash8"], EXPECTED_PR14_HASH8)

    def test_invalid_branch_exits_nonzero(self) -> None:
        import io
        from contextlib import redirect_stderr

        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code = naming.main(
                ["--repo", REPO, "--pr-number", "14", "--branch", "main"]
            )
        self.assertEqual(code, 1)


# --- Preflight tests ----------------------------------------------------------

VALID_ACR = "acrfantasycards"


def _names():
    return naming.compute_names(REPO, 14, "squad/14-render-card-layout")


def _evaluate(**overrides):
    kwargs = dict(
        is_fork=False,
        is_draft=False,
        base_repo=REPO,
        head_repo=REPO,
        names=_names(),
        referenced_acr_name=VALID_ACR,
        active_app_env_count=0,
        requires_foundry=False,
        active_foundry_env_count=0,
    )
    kwargs.update(overrides)
    return preflight.evaluate(**kwargs)


class PreflightTests(unittest.TestCase):
    def test_happy_path_proceeds(self) -> None:
        result = _evaluate()
        self.assertIs(result.decision, preflight.Decision.PROCEED)
        self.assertEqual(result.reason_code, "ok")
        self.assertTrue(result.proceed)

    def test_fork_pr_blocked(self) -> None:
        result = _evaluate(is_fork=True)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "fork_pr")

    def test_fork_is_blocked_even_when_draft(self) -> None:
        result = _evaluate(is_fork=True, is_draft=True)
        self.assertEqual(result.reason_code, "fork_pr")

    def test_untrusted_head_repo_blocked(self) -> None:
        result = _evaluate(head_repo="attacker/squad-workshop")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "untrusted_repo")

    def test_draft_pr_skipped(self) -> None:
        result = _evaluate(is_draft=True)
        self.assertIs(result.decision, preflight.Decision.SKIP)
        self.assertEqual(result.reason_code, "draft_pr")
        self.assertFalse(result.proceed)

    def test_invalid_referenced_acr_blocked(self) -> None:
        result = _evaluate(referenced_acr_name="bad-name")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_service_name")

    def test_app_cap_at_three_blocked(self) -> None:
        result = _evaluate(active_app_env_count=3)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "app_concurrency_cap")

    def test_app_cap_below_three_proceeds(self) -> None:
        self.assertIs(_evaluate(active_app_env_count=2).decision, preflight.Decision.PROCEED)

    def test_app_cap_unknown_count_fails_closed(self) -> None:
        result = _evaluate(active_app_env_count=-1)
        self.assertEqual(result.reason_code, "app_concurrency_cap")

    def test_foundry_cap_at_one_blocked(self) -> None:
        result = _evaluate(requires_foundry=True, active_foundry_env_count=1)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_concurrency_cap")

    def test_foundry_cap_not_applied_when_not_required(self) -> None:
        result = _evaluate(requires_foundry=False, active_foundry_env_count=5)
        self.assertIs(result.decision, preflight.Decision.PROCEED)

    def test_foundry_first_environment_proceeds(self) -> None:
        result = _evaluate(requires_foundry=True, active_foundry_env_count=0)
        self.assertIs(result.decision, preflight.Decision.PROCEED)


if __name__ == "__main__":
    unittest.main()
