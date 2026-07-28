"""Unit tests for the PR Foundry-scope detector (Phase 6, #17)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


scope = _load("pr_foundry_scope")


def _write_case(
    root: Path,
    name: str,
    *,
    changed_paths: str,
    labels_json: str,
) -> tuple[Path, Path]:
    case_dir = root / name
    case_dir.mkdir(parents=True, exist_ok=True)
    paths_file = case_dir / "changed-paths.txt"
    labels_file = case_dir / "labels.json"
    paths_file.write_text(changed_paths, encoding="utf-8")
    labels_file.write_text(labels_json, encoding="utf-8")
    return paths_file, labels_file


def _run(
    name: str,
    *,
    changed_paths: str = "",
    labels: list[str] | None = None,
    labels_json: str | None = None,
    output_format: str = "json",
    repo_files: dict[str, str] | None = None,
) -> tuple[int, str]:
    if labels_json is None:
        labels_json = json.dumps([] if labels is None else labels)
    with tempfile.TemporaryDirectory(prefix="pr-foundry-scope-") as tmp:
        root = Path(tmp)
        paths_file, labels_file = _write_case(
            root, name, changed_paths=changed_paths, labels_json=labels_json
        )
        if repo_files is not None:
            for relative_path, content in repo_files.items():
                target = root / Path(*relative_path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        argv = [
            "--changed-paths-file",
            str(paths_file),
            "--labels-file",
            str(labels_file),
            "--format",
            output_format,
        ]
        if repo_files is not None:
            argv.extend(["--repo-root", str(root)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = scope.main(argv)
        return code, buffer.getvalue()


SAFE_MAIN_BICEPPARAM = (
    "using './main.bicep'\n\n"
    "param location = 'swedencentral'\n"
    "param deployFoundry = bool(readEnvironmentVariable('DEPLOY_FOUNDRY', 'true'))\n"
    "param logAnalyticsWorkspaceName = readEnvironmentVariable('LOG_ANALYTICS_WORKSPACE_NAME', '')\n"
)

SAFE_MAIN_BICEP = (
    "targetScope = 'resourceGroup'\n\n"
    "param deployFoundry bool = true\n"
    "param environmentName string\n\n"
    "module foundry 'foundry.bicep' = {\n"
    "  name: 'foundry-${environmentName}'\n"
    "  params: {\n"
    "    deployFoundry: deployFoundry\n"
    "  }\n"
    "}\n"
)


class FoundryScopePathTests(unittest.TestCase):

    def test_foundry_provisioning_path_requires_foundry(self) -> None:
        code, output = _run(
            "foundry-provisioning",
            changed_paths="infra/foundry.bicep\n",
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], True)
        self.assertEqual(
            payload["reasons"]["requires_foundry"]["paths"][0]["path"],
            "infra/foundry.bicep",
        )

    def test_foundry_rbac_path_requires_foundry(self) -> None:
        code, output = _run(
            "foundry-rbac",
            changed_paths="infra/modules/shared-foundry-rbac.bicep\n",
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], True)
        self.assertEqual(
            payload["reasons"]["requires_foundry"]["paths"][0]["category"],
            "foundry_rbac",
        )

    def test_root_foundry_parameter_surface_is_too_ambiguous_for_path_only(self) -> None:
        for path in ("infra/main.bicep", "infra/main.bicepparam"):
            with self.subTest(path=path):
                code, output = _run(
                    f"root-{path.replace('/', '-')}",
                    changed_paths=f"{path}\n",
                    repo_files={
                        "infra/main.bicep": SAFE_MAIN_BICEP,
                        "infra/main.bicepparam": SAFE_MAIN_BICEPPARAM,
                    },
                )
                self.assertEqual(code, 0)
                payload = json.loads(output)
                self.assertIs(payload["requires_foundry"], False)
                self.assertEqual(payload["reasons"]["requires_foundry"]["paths"], [])
                self.assertEqual(
                    payload["reasons"]["requires_foundry"]["switch_integrity"], []
                )

    def test_provider_contract_path_prefers_shared_foundry_validation_not_provisioning(self) -> None:
        code, output = _run(
            "provider-contract",
            changed_paths="src/fantasy_cards/adapters.py\n",
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], False)
        self.assertEqual(payload["reasons"]["requires_foundry"]["paths"], [])

    def test_pure_app_tier_pr_does_not_require_foundry(self) -> None:
        code, output = _run(
            "app-tier",
            changed_paths="src/fantasy_cards/web.py\nsrc/fantasy_cards/domain.py\n",
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], False)
        self.assertEqual(payload["reasons"]["requires_foundry"]["paths"], [])

    def test_app_infra_that_only_consumes_foundry_endpoint_is_not_overmatched(self) -> None:
        code, output = _run("web-bicep", changed_paths="infra/web.bicep\n")

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], False)

    def test_foundry_path_matching_is_case_sensitive_and_exact(self) -> None:
        for name, path in (
            ("uppercase", "INFRA/FOUNDRY.BICEP"),
            ("substring", "docs/examples/infra/foundry.bicep"),
            ("child", "infra/foundry.bicep/readme.md"),
        ):
            with self.subTest(name=name):
                code, output = _run(name, changed_paths=f"{path}\n")
                self.assertEqual(code, 0)
                payload = json.loads(output)
                self.assertIs(payload["requires_foundry"], False)
                self.assertEqual(payload["reasons"]["requires_foundry"]["paths"], [])

    def test_phase5_style_root_tag_budget_observability_pr_is_not_overmatched(self) -> None:
        code, output = _run(
            "phase5-shape",
            changed_paths=(
                "docs/design/pr-ephemeral-environments.md\n"
                "docs/runbooks/pr-environment-azure-setup.md\n"
                "infra/main.bicep\n"
                "infra/main.bicepparam\n"
                "infra/scripts/pr_environment_names.py\n"
                "tests/test_deployment_contract.py\n"
                "tests/test_pr_environment_names.py\n"
            ),
            repo_files={
                "infra/main.bicep": SAFE_MAIN_BICEP,
                "infra/main.bicepparam": SAFE_MAIN_BICEPPARAM,
            },
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], False)
        self.assertEqual(payload["reasons"]["requires_foundry"]["paths"], [])
        self.assertEqual(payload["reasons"]["requires_foundry"]["switch_integrity"], [])

    def test_hardcoded_deploy_foundry_in_main_bicepparam_requires_foundry(self) -> None:
        code, output = _run(
            "hardcoded-switch",
            changed_paths="infra/main.bicepparam\n",
            repo_files={
                "infra/main.bicepparam": (
                    "using './main.bicep'\n"
                    "param deployFoundry = true\n"
                )
            },
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], True)
        switch = payload["reasons"]["requires_foundry"]["switch_integrity"]
        self.assertEqual(switch[0]["path"], "infra/main.bicepparam")
        self.assertEqual(switch[0]["check"], "deployFoundry_sources_DEPLOY_FOUNDRY")
        self.assertIn("param deployFoundry = true", switch[0]["observed"])

    def test_main_bicep_hardcoded_module_switch_requires_foundry(self) -> None:
        code, output = _run(
            "main-module-hardcoded",
            changed_paths="infra/main.bicep\n",
            repo_files={
                "infra/main.bicep": SAFE_MAIN_BICEP.replace(
                    "deployFoundry: deployFoundry",
                    "deployFoundry: true",
                )
            },
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], True)
        switch = payload["reasons"]["requires_foundry"]["switch_integrity"]
        self.assertEqual(switch[0]["path"], "infra/main.bicep")
        self.assertEqual(switch[0]["check"], "deployFoundry_module_wiring")

    def test_switch_integrity_inspection_failure_exits_3_without_false_success(self) -> None:
        code, output = _run(
            "missing-switch-file",
            changed_paths="infra/main.bicepparam\n",
            repo_files={},
            output_format="github",
        )

        self.assertEqual(code, scope.MALFORMED_INPUT_EXIT_CODE)
        self.assertNotIn("requires_foundry=false", output)

    def test_empty_changed_paths_file_does_not_crash(self) -> None:
        code, output = _run("empty-paths", changed_paths="", labels=[])

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], False)
        self.assertIs(payload["live_validation_requested"], False)


class FoundryScopeLabelTests(unittest.TestCase):
    def test_label_based_opt_in_requires_foundry(self) -> None:
        code, output = _run(
            "requires-label",
            changed_paths="src/fantasy_cards/domain.py\n",
            labels=["requires:foundry"],
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["requires_foundry"], True)
        self.assertEqual(
            payload["reasons"]["requires_foundry"]["labels"],
            ["requires:foundry"],
        )

    def test_requires_foundry_label_matching_is_exact(self) -> None:
        for label in ("requires_foundry", "Requires:Foundry", "requires:foundry-extra"):
            with self.subTest(label=label):
                code, output = _run(
                    "requires-label-near-miss",
                    changed_paths="src/fantasy_cards/domain.py\n",
                    labels=[label],
                )
                self.assertEqual(code, 0)
                payload = json.loads(output)
                self.assertIs(payload["requires_foundry"], False)
                self.assertEqual(payload["reasons"]["requires_foundry"]["labels"], [])

    def test_live_validation_label_present_requests_live_validation(self) -> None:
        code, output = _run(
            "live-label",
            changed_paths="src/fantasy_cards/domain.py\n",
            labels=[scope.LIVE_VALIDATION_LABEL],
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["live_validation_requested"], True)
        self.assertEqual(
            payload["reasons"]["live_validation_requested"]["labels"],
            ["validate:live-foundry"],
        )

    def test_live_validation_label_absent_does_not_request_live_validation(self) -> None:
        code, output = _run(
            "live-absent",
            changed_paths="infra/foundry.bicep\n",
            labels=[],
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIs(payload["live_validation_requested"], False)

    def test_requires_foundry_and_live_validation_are_independent(self) -> None:
        cases = (
            ("neither", "src/fantasy_cards/domain.py\n", [], False, False),
            ("requires-only", "infra/foundry.bicep\n", [], True, False),
            (
                "live-only",
                "src/fantasy_cards/domain.py\n",
                [scope.LIVE_VALIDATION_LABEL],
                False,
                True,
            ),
            (
                "both",
                "infra/foundry.bicep\n",
                [scope.LIVE_VALIDATION_LABEL],
                True,
                True,
            ),
        )

        for name, changed_paths, labels, expected_requires, expected_live in cases:
            with self.subTest(name=name):
                code, output = _run(name, changed_paths=changed_paths, labels=labels)
                self.assertEqual(code, 0)
                payload = json.loads(output)
                self.assertIs(payload["requires_foundry"], expected_requires)
                self.assertIs(payload["live_validation_requested"], expected_live)


class FoundryScopeCliTests(unittest.TestCase):
    def test_malformed_input_exit_code_is_concrete_three(self) -> None:
        self.assertEqual(scope.MALFORMED_INPUT_EXIT_CODE, 3)

    def test_github_format_emits_exact_two_success_lines(self) -> None:
        code, output = _run(
            "github-output",
            changed_paths="infra/foundry.bicep\n",
            labels=[scope.LIVE_VALIDATION_LABEL],
            output_format="github",
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            output.splitlines(),
            [
                "requires_foundry=true",
                "live_validation_requested=true",
            ],
        )

    def test_json_format_includes_auditable_reasons(self) -> None:
        code, output = _run(
            "json-reasons",
            changed_paths="infra/modules/shared-foundry-rbac.bicep\n",
            labels=[scope.REQUIRES_FOUNDRY_LABEL, scope.LIVE_VALIDATION_LABEL],
        )

        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIn("reasons", payload)
        self.assertEqual(
            payload["reasons"]["requires_foundry"]["paths"][0]["category"],
            "foundry_rbac",
        )
        self.assertEqual(
            payload["reasons"]["requires_foundry"]["labels"],
            [scope.REQUIRES_FOUNDRY_LABEL],
        )

    def test_invalid_labels_json_exits_3_without_false_success(self) -> None:
        code, output = _run(
            "bad-json",
            changed_paths="infra/foundry.bicep\n",
            labels_json="{not json",
            output_format="github",
        )

        self.assertEqual(code, scope.MALFORMED_INPUT_EXIT_CODE)
        self.assertNotIn("requires_foundry=false", output)
        self.assertNotIn("live_validation_requested=false", output)

    def test_labels_json_must_be_array_of_strings(self) -> None:
        for name, labels_json in (
            ("object-labels", '{"name": "requires:foundry"}'),
            ("numeric-label", '["requires:foundry", 3]'),
        ):
            with self.subTest(name=name):
                code, output = _run(
                    name,
                    changed_paths="infra/foundry.bicep\n",
                    labels_json=labels_json,
                )
                self.assertEqual(code, scope.MALFORMED_INPUT_EXIT_CODE)
                self.assertIn("error", json.loads(output))

    def test_missing_changed_paths_file_exits_3_without_success_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pr-foundry-scope-missing-") as tmp:
            paths_file = Path(tmp) / "missing" / "changed-paths.txt"
            labels_file = Path(tmp) / "missing" / "labels.json"
            labels_file.parent.mkdir(parents=True, exist_ok=True)
            labels_file.write_text("[]", encoding="utf-8")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = scope.main(
                    [
                        "--changed-paths-file",
                        str(paths_file),
                        "--labels-file",
                        str(labels_file),
                        "--format",
                        "github",
                    ]
                )

            output = buffer.getvalue()
        self.assertEqual(code, scope.MALFORMED_INPUT_EXIT_CODE)
        self.assertNotIn("requires_foundry=false", output)


if __name__ == "__main__":
    unittest.main()
