"""Unit tests for the per-PR environment naming and preflight modules.

The modules live under ``infra/scripts`` (CI/platform tooling, not application
domain logic), so they are loaded by path -- matching the existing
``tests/test_retire_legacy_storage_blob_role.py`` convention.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import re
import sys
import unittest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "infra/scripts"
REPOSITORY_ROOT = SCRIPTS_DIR.parents[1]
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

    def test_path_traversal_and_separators_are_neutralized(self) -> None:
        # Slashes/dots from a traversal-style branch must collapse to safe
        # hyphen-delimited tokens, never leak '.' or '/' into a resource name.
        slug = naming.slug_from_branch("squad/14-../../etc/passwd")
        self.assertEqual(slug, "etc-passwd")
        self.assertRegex(slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_unicode_and_uppercase_are_sanitized_to_ascii_slug(self) -> None:
        slug = naming.slug_from_branch("squad/14-Caf\u00e9-Draft")
        self.assertEqual(slug, "caf-draft")
        self.assertRegex(slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")


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

    def test_virtual_network(self) -> None:
        # Anchored to the compacted managed_environment token, not the raw azd
        # env name, so it stays within the 64-char VNet limit.
        self.assertEqual(
            self.names.virtual_network,
            f"vnet-{self.names.managed_environment}-private",
        )


class EnvironmentNameLimitTests(unittest.TestCase):
    def test_long_branch_slug_is_truncated_but_keeps_pr_number_and_hash(self) -> None:
        names = naming.compute_names(
            REPO, 45, "squad/41-change-application-background-color-to-green"
        )
        self.assertEqual(
            names.environment_name,
            f"pr-45-change-application-backgr-{names.hash8}",
        )
        self.assertEqual(len(names.environment_name), naming.AZD_ENVIRONMENT_MAX)
        self.assertTrue(names.environment_name.startswith("pr-45-"))
        self.assertTrue(names.environment_name.endswith(names.hash8))
        self.assertEqual(
            names.hash8,
            naming.hash8(REPO, 45, "change-application-background-color-to-green"),
        )

    def test_every_project_module_deployment_name_fits_worst_case_environment_name(self) -> None:
        module_name_patterns: list[tuple[str, str]] = []
        for template in (REPOSITORY_ROOT / "infra").rglob("*.bicep"):
            lines = template.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if not re.match(r"\s*module\s+\w+\s+", line):
                    continue
                nearby = "\n".join(lines[index : index + 8])
                match = re.search(r"name:\s*'([^']*)'", nearby)
                if match is not None:
                    module_name_patterns.append(
                        (template.relative_to(REPOSITORY_ROOT).as_posix(), match.group(1))
                    )

        self.assertTrue(module_name_patterns)
        longest = max(
            module_name_patterns,
            key=lambda item: len(re.sub(r"\$\{[^}]+\}", "", item[1])),
        )
        prefix_budget = naming.ARM_DEPLOYMENT_MAX - naming.AZD_ENVIRONMENT_MAX
        self.assertEqual(prefix_budget, 24)
        for path, pattern in module_name_patterns:
            literal_prefix = re.sub(r"\$\{[^}]+\}", "", pattern)
            worst_case_length = len(literal_prefix) + naming.AZD_ENVIRONMENT_MAX
            self.assertLessEqual(
                worst_case_length,
                naming.ARM_DEPLOYMENT_MAX,
                f"{path}: {pattern} can reach {worst_case_length} chars; "
                f"longest observed prefix is {longest}",
            )


class VirtualNetworkTests(unittest.TestCase):
    SLUGS = [
        "render-card-layout",
        "relax-ci-ownership-gate",
        "-".join(["seg"] * 25),
        "verylongsinglewordwithnoseparatorsatallhere",
    ]
    PRS = [1, 14, 26, 999999]

    def test_never_overflows_64_and_is_vnet_safe(self) -> None:
        for pr in self.PRS:
            for slug in self.SLUGS:
                names = naming.compute_names(REPO, pr, f"squad/{pr}-{slug}")
                vnet = names.virtual_network
                self.assertLessEqual(len(vnet), 64, vnet)
                self.assertGreaterEqual(len(vnet), 2, vnet)
                # start alphanumeric, only [a-z0-9-]
                self.assertRegex(vnet, r"^[a-z][a-z0-9-]*[a-z0-9]$", vnet)

    def test_real_pr_example_would_have_overflowed_legacy_name(self) -> None:
        # The legacy web.bicep name overflowed; the new one must not.
        names = naming.compute_names(
            REPO, 26, "squad/26-relax-ci-ownership-gate"
        )
        legacy = f"vnet-fantasy-cards-{names.environment_name}-private"
        self.assertGreater(len(legacy), 64)
        self.assertLessEqual(len(names.virtual_network), 64)

    def test_generator_rejects_empty_managed_environment(self) -> None:
        with self.assertRaises(ValueError):
            naming.virtual_network_name("")


class BicepparamContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.names = naming.compute_names(REPO, 26, "squad/26-relax-ci-ownership-gate")

    def test_mapping_keys_are_all_printable_fields(self) -> None:
        printable = self.names.printable_fields()
        for key in naming.BICEPPARAM_ENV_VARS:
            self.assertIn(key, printable, key)

    def test_mapping_targets_expected_bicepparam_env_vars(self) -> None:
        self.assertEqual(
            naming.BICEPPARAM_ENV_VARS,
            {
                "environment_name": "AZURE_ENV_NAME",
                "storage_account": "STORAGE_ACCOUNT_NAME",
                "container_app": "CONTAINER_APP_NAME",
                "managed_environment": "CONTAINER_APPS_ENVIRONMENT_NAME",
                "virtual_network": "VIRTUAL_NETWORK_NAME",
                "application_insights": "APPLICATION_INSIGHTS_NAME",
                "log_analytics": "LOG_ANALYTICS_WORKSPACE_NAME",
            },
        )

    def test_every_env_var_is_read_by_main_bicepparam(self) -> None:
        # The workflow's authoritative "Compute names" step exports exactly the
        # BICEPPARAM_ENV_VARS values via ``--format envvars``; the dedicated
        # "Export per-PR observability names" step was removed (commit 6cba275)
        # precisely because this envvars contract is the single path. That makes
        # the dict<->bicepparam wiring load-bearing: if main.bicepparam stops
        # reading one of these names, the PR-safe value silently never reaches
        # Bicep and the resource falls back to the hardcoded dev default (a
        # cross-PR collision). Nothing else pins this, so pin it here against the
        # real file with a literal read expression per env-var name.
        bicepparam = (SCRIPTS_DIR.parent / "main.bicepparam").read_text(
            encoding="utf-8"
        )
        for field, env_var in naming.BICEPPARAM_ENV_VARS.items():
            self.assertIn(
                f"readEnvironmentVariable('{env_var}'",
                bicepparam,
                f"{field} -> {env_var} is exported by the naming step but never "
                "read by infra/main.bicepparam; the PR-safe name will not reach "
                "Bicep and the dev default will be used",
            )

    def test_envvars_format_emits_bicepparam_names(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = naming.main(
                [
                    "--repo",
                    REPO,
                    "--pr-number",
                    "26",
                    "--branch",
                    "squad/26-relax-ci-ownership-gate",
                    "--format",
                    "envvars",
                ]
            )
        self.assertEqual(code, 0)
        lines = {
            line.split("=", 1)[0]: line.split("=", 1)[1]
            for line in buffer.getvalue().splitlines()
            if line
        }
        self.assertEqual(set(lines), set(naming.BICEPPARAM_ENV_VARS.values()))
        self.assertEqual(lines["CONTAINER_APP_NAME"], self.names.container_app)
        self.assertEqual(
            lines["CONTAINER_APPS_ENVIRONMENT_NAME"], self.names.managed_environment
        )
        self.assertEqual(lines["STORAGE_ACCOUNT_NAME"], self.names.storage_account)
        self.assertEqual(lines["VIRTUAL_NETWORK_NAME"], self.names.virtual_network)
        self.assertEqual(lines["AZURE_ENV_NAME"], self.names.environment_name)

    def test_envvars_values_carry_no_injection_primitives(self) -> None:
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            naming.main(
                [
                    "--repo",
                    REPO,
                    "--pr-number",
                    "26",
                    "--branch",
                    "squad/26-foo%0A::error::x",
                    "--format",
                    "envvars",
                ]
            )
        for line in buffer.getvalue().splitlines():
            if not line:
                continue
            _var, _, value = line.partition("=")
            self.assertNotRegex(value, r"[\x00-\x1f\x7f]")
            self.assertRegex(value, r"^[a-z0-9-]+$")


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
                self.assertLessEqual(len(names.virtual_network), 64, names.virtual_network)
                self.assertRegex(names.virtual_network, r"^[a-z][a-z0-9-]*[a-z0-9]$")
                self.assertLessEqual(len(names.resource_group), 90)
                self.assertLessEqual(
                    len(names.environment_name), naming.AZD_ENVIRONMENT_MAX
                )
                self.assertTrue(names.environment_name.startswith(f"pr-{pr}-"))
                self.assertTrue(names.environment_name.endswith(names.hash8))


class ManagedEnvironmentCompactionTests(unittest.TestCase):
    def test_long_env_name_compacts_to_pr_token_plus_hash(self) -> None:
        # pr-14-render-card-layout-<hash> is 33 chars (> defensive 32), so the
        # managed environment must fall back to the pr{n}-{hash8} compaction and
        # still start with a letter / end alphanumeric.
        names = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        self.assertGreater(len(names.environment_name), 32)
        self.assertEqual(names.managed_environment, f"pr14-{names.hash8}")
        self.assertRegex(names.managed_environment, r"^[a-z][a-z0-9-]*[a-z0-9]$")

    def test_short_env_name_used_verbatim(self) -> None:
        # A short slug keeps the full env name (fits within 32).
        names = naming.compute_names(REPO, 5, "squad/5-x")
        self.assertLessEqual(len(names.environment_name), 32)
        self.assertEqual(names.managed_environment, names.environment_name)


class LogAnalyticsTests(unittest.TestCase):
    """The deterministic Log Analytics workspace name (Phase 5).

    Azure rule: length 4-63, alphanumerics and hyphens only, must start and end
    with an alphanumeric character. Since AZURE_ENV_NAME is bounded to 40 chars,
    the Log Analytics workspace can use it directly for all PR environments.
    """

    _NAME_RE = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"

    def test_short_env_name_used_verbatim(self) -> None:
        # pr-14-render-card-layout-<hash> is 33 chars (<= 63), so the workspace
        # name is the full env name verbatim -- asserted against a literal.
        names = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        self.assertEqual(
            names.log_analytics,
            f"pr-14-render-card-layout-{EXPECTED_PR14_HASH8}",
        )
        self.assertEqual(names.log_analytics, names.environment_name)

    def test_is_deterministic(self) -> None:
        first = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        second = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        self.assertEqual(first.log_analytics, second.log_analytics)

    def test_long_raw_slug_is_truncated_before_log_analytics_receives_it(self) -> None:
        slug = "a" * 48
        names = naming.compute_names(REPO, 14, f"squad/14-{slug}")
        self.assertEqual(len(names.environment_name), naming.AZD_ENVIRONMENT_MAX)
        self.assertEqual(names.log_analytics, names.environment_name)
        self.assertEqual(len(names.log_analytics), naming.AZD_ENVIRONMENT_MAX)
        self.assertTrue(names.log_analytics.startswith("pr-14-aaaaaaaaaaaaaaaaaaaaaaaaa-"))
        self.assertRegex(names.log_analytics, self._NAME_RE)

    def test_pathological_slug_still_uses_bounded_environment_name(self) -> None:
        slug = "a" * 49
        names = naming.compute_names(REPO, 14, f"squad/14-{slug}")
        self.assertEqual(len(names.environment_name), naming.AZD_ENVIRONMENT_MAX)
        self.assertEqual(names.log_analytics, names.environment_name)
        self.assertLessEqual(len(names.log_analytics), 63)
        self.assertRegex(names.log_analytics, self._NAME_RE)

    def test_pathological_long_slug_never_overflows_63(self) -> None:
        slugs = ["-".join(["seg"] * 25), "x" * 200]
        for pr in (1, 14, 999999):
            for slug in slugs:
                names = naming.compute_names(REPO, pr, f"squad/{pr}-{slug}")
                self.assertLessEqual(len(names.log_analytics), 63, names.log_analytics)
                self.assertGreaterEqual(len(names.log_analytics), 4, names.log_analytics)
                self.assertEqual(names.log_analytics, names.environment_name)
                self.assertRegex(names.log_analytics, self._NAME_RE)

    def test_appears_in_printable_and_envvars_output(self) -> None:
        names = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        self.assertEqual(
            names.printable_fields()["log_analytics"], names.log_analytics
        )
        self.assertEqual(
            naming.BICEPPARAM_ENV_VARS["log_analytics"],
            "LOG_ANALYTICS_WORKSPACE_NAME",
        )


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
        result = _evaluate(
            requires_foundry=True, foundry_authorized=True, active_foundry_env_count=1
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_concurrency_cap")

    def test_foundry_cap_not_applied_when_not_required(self) -> None:
        result = _evaluate(requires_foundry=False, active_foundry_env_count=5)
        self.assertIs(result.decision, preflight.Decision.PROCEED)

    def test_foundry_first_environment_proceeds(self) -> None:
        result = _evaluate(
            requires_foundry=True, foundry_authorized=True, active_foundry_env_count=0
        )
        self.assertIs(result.decision, preflight.Decision.PROCEED)

    def test_app_cap_above_three_stays_blocked(self) -> None:
        # Boundary above the cap: a count of 4 must remain BLOCKED (>= semantics,
        # not an exact-equality check that could fail open past the cap).
        result = _evaluate(active_app_env_count=4)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "app_concurrency_cap")

    def test_foundry_cap_above_one_stays_blocked(self) -> None:
        result = _evaluate(
            requires_foundry=True, foundry_authorized=True, active_foundry_env_count=2
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_concurrency_cap")

    def test_bool_app_count_fails_closed(self) -> None:
        # A bool is not a valid count; it must fail closed rather than be
        # treated as 0/1 via int coercion.
        result = _evaluate(active_app_env_count=True)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "app_concurrency_cap")


# --- Rai RED remediation: trust-boundary integrity (finding 1) ----------------


class ForkTrustIntegrityTests(unittest.TestCase):
    """The fork flag gates Azure credential exposure; it must never be coerced.

    ``${{ github.event.pull_request.head.repo.fork }}`` rendering empty is a
    realistic production failure, so ``None``/``0``/``""``/non-bool must fail
    closed instead of proceeding.
    """

    def test_fork_none_does_not_proceed(self) -> None:
        result = _evaluate(is_fork=None)
        self.assertIsNot(result.decision, preflight.Decision.PROCEED)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_fork_empty_string_does_not_proceed(self) -> None:
        result = _evaluate(is_fork="")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_fork_zero_does_not_proceed(self) -> None:
        result = _evaluate(is_fork=0)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_fork_truthy_string_does_not_proceed(self) -> None:
        # A non-empty string like "false" is truthy; coercion would BLOCK as a
        # fork here, but the point is it must never be silently interpreted.
        result = _evaluate(is_fork="false")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_fork_evaluated_before_draft(self) -> None:
        # An invalid fork signal must fail closed even for a draft PR: the trust
        # gate cannot be short-circuited by a later check.
        result = _evaluate(is_fork=None, is_draft=True)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_missing_base_repo_fails_closed(self) -> None:
        result = _evaluate(base_repo="")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "untrusted_repo")

    def test_none_head_repo_fails_closed(self) -> None:
        result = _evaluate(head_repo=None)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "untrusted_repo")

    def test_whitespace_repo_fails_closed(self) -> None:
        result = _evaluate(base_repo="   ", head_repo="   ")
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "untrusted_repo")

    def test_invalid_draft_signal_fails_closed(self) -> None:
        result = _evaluate(is_draft=None)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")


# --- Rai RED remediation: Foundry approval gate (finding 2) --------------------


class FoundryAuthorizationTests(unittest.TestCase):
    """Foundry-per-PR creates model capacity/RBAC/safety paths; it is capped at
    one and requires explicit approval. The cap and gate must not be bypassable
    by caller intent."""

    def test_foundry_required_without_authorization_blocks(self) -> None:
        # Even with a free slot, the Foundry path must NOT proceed unless the
        # explicit approval signal is present.
        result = _evaluate(
            requires_foundry=True, foundry_authorized=False, active_foundry_env_count=0
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_unauthorized")

    def test_foundry_authorization_unknown_fails_closed(self) -> None:
        result = _evaluate(
            requires_foundry=True, foundry_authorized=None, active_foundry_env_count=0
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_unauthorized")

    def test_foundry_authorization_truthy_nonbool_fails_closed(self) -> None:
        # A truthy non-bool ("yes") must not be accepted as approval.
        result = _evaluate(
            requires_foundry=True, foundry_authorized="yes", active_foundry_env_count=0
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_unauthorized")

    def test_foundry_requirement_signal_must_be_bool(self) -> None:
        result = _evaluate(requires_foundry=None)
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "invalid_trust_signal")

    def test_foundry_authorized_over_cap_still_blocks(self) -> None:
        # Authorization does not waive the cap.
        result = _evaluate(
            requires_foundry=True, foundry_authorized=True, active_foundry_env_count=1
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_concurrency_cap")

    def test_foundry_authorized_unknown_count_fails_closed(self) -> None:
        result = _evaluate(
            requires_foundry=True, foundry_authorized=True, active_foundry_env_count=-1
        )
        self.assertIs(result.decision, preflight.Decision.BLOCKED)
        self.assertEqual(result.reason_code, "foundry_concurrency_cap")


# --- Rai RED remediation: log-injection / output sanitization (finding 3) ------


class InvalidServiceNameMessageTests(unittest.TestCase):
    def test_message_does_not_echo_raw_value(self) -> None:
        result = _evaluate(referenced_acr_name="bad-name!!$$")
        self.assertEqual(result.reason_code, "invalid_service_name")
        # The offending raw value must NOT appear in the printable message; only
        # the opaque field name is emitted.
        self.assertNotIn("bad-name", result.message)
        self.assertIn("referenced_acr", result.message)


class LogInjectionTests(unittest.TestCase):
    """Branch names are attacker-controlled on fork PRs. No branch may inject a
    newline, ANSI escape, or GitHub Actions workflow command into stdout
    (``$GITHUB_OUTPUT``) or stderr."""

    # Branches carrying a real newline, or that fail the convention, are
    # REJECTED outright (exit 1) -- a newline can never survive into a name.
    _REJECTED_BRANCHES = [
        "squad/14-foo\n::set-output name=x::y",
        "squad/14-foo\r\n::error::pwned",
        "::error::not-even-a-branch",
        "squad/14-\n",
    ]
    # Branches with no real newline PARSE, but every unsafe character is stripped
    # by the allowlist, so the emitted slug/name is safe.
    _SANITIZED_BRANCHES = [
        "squad/14-foo\x1b[31mred",
        "squad/14-foo%0A::error::pwned",
        "squad/14-Foo Bar::Baz",
    ]

    def test_slug_is_allowlisted_and_carries_no_control_chars(self) -> None:
        for branch in self._SANITIZED_BRANCHES:
            slug = naming.slug_from_branch(branch)
            self.assertRegex(slug, r"^[a-z0-9-]+$", msg=f"unsafe slug from {branch!r}")
            for bad in ("\n", "\r", "\x1b", ":", "%"):
                self.assertNotIn(bad, slug)

    def test_env_output_values_are_single_line_and_safe(self) -> None:
        names = naming.compute_names(REPO, 14, "squad/14-render-card-layout")
        for key, value in names.printable_fields().items():
            self.assertRegex(value, r"^[a-z0-9-]+$", msg=f"unsafe value for {key}")

    def test_cli_env_output_has_no_injected_lines(self) -> None:
        import io
        from contextlib import redirect_stdout

        # A branch that parses but embeds injection primitives must still yield
        # only safe key=value lines.
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = naming.main(
                ["--repo", REPO, "--pr-number", "14", "--branch", "squad/14-foo%0A::error::x"]
            )
        self.assertEqual(code, 0)
        for line in buffer.getvalue().splitlines():
            if not line:
                continue
            _key, _, value = line.partition("=")
            self.assertFalse(value.startswith("::"))
            self.assertNotRegex(value, r"[\x00-\x1f\x7f]")

    def test_cli_output_never_contains_repo(self) -> None:
        import io
        import json
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            naming.main(
                ["--repo", REPO, "--pr-number", "14", "--branch", "squad/14-x", "--format", "json"]
            )
        payload = json.loads(buffer.getvalue())
        self.assertNotIn("repo", payload)
        self.assertNotIn(REPO, buffer.getvalue())

    def test_rejected_branch_cannot_inject_into_stderr(self) -> None:
        import io
        from contextlib import redirect_stderr

        for branch in self._REJECTED_BRANCHES:
            buffer = io.StringIO()
            with redirect_stderr(buffer):
                code = naming.main(["--repo", REPO, "--pr-number", "14", "--branch", branch])
            self.assertEqual(code, 1, msg=f"branch should be rejected: {branch!r}")
            err = buffer.getvalue()
            # Sanitized error is confined to a single physical line (only the
            # trailing newline from print), so no attacker content can start a
            # fresh line or a workflow command.
            self.assertEqual(err.count("\n"), 1, msg=f"multi-line stderr for {branch!r}")
            self.assertNotIn("\x1b", err)
            self.assertNotIn("\r", err)
            self.assertFalse(err.lstrip().startswith("::"))


if __name__ == "__main__":
    unittest.main()
