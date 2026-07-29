from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment.yml"
JANITOR_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment-janitor.yml"


def _step_block(source: str, step_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^      - name: {re.escape(step_name)}\n(?P<body>.*?)(?=^      - name: |^  [a-zA-Z_]+:|\Z)"
    )
    match = pattern.search(source)
    if match is None:
        raise AssertionError(f"Missing workflow step {step_name!r}")
    return match.group("body")


class PrEnvironmentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.janitor_workflow = JANITOR_WORKFLOW.read_text(encoding="utf-8")

    def test_preflight_policy_blocks_are_printed_before_enforcement(self) -> None:
        block = _step_block(self.workflow, "Evaluate deploy preflight")
        self.assertIn(
            "set +e\n          output=\"$(python3 .trusted-policy/infra/scripts/pr_preflight.py",
            block,
        )
        self.assertIn("--format env 2>&1)\"", block)
        self.assertIn("rc=$?\n          set -e", block)
        self.assertIn("printf '%s\\n' \"$output\"", block)
        self.assertIn("grep -qx 'decision=blocked'", block)
        self.assertIn("printf '%s\\n' \"$output\" >> \"$GITHUB_OUTPUT\"", block)

    def test_preflight_runs_from_trusted_base_context(
        self,
    ) -> None:
        self.assertIn("pull_request_target:", self.workflow)
        self.assertNotIn("\n  pull_request:\n", self.workflow)
        self.assertIn(
            "ref: ${{ github.event.pull_request.base.sha }}\n"
            "          path: .trusted-policy\n"
            "          persist-credentials: false",
            self.workflow,
        )
        self.assertIn(
            "ref: ${{ github.event.pull_request.head.sha }}\n"
            "          path: .pr-content\n"
            "          persist-credentials: false",
            self.workflow,
        )
        self.assertIn(
            'test "$(git -C .trusted-policy rev-parse HEAD)" = "$BASE_SHA"',
            self.workflow,
        )
        self.assertIn(
            'test "$(git -C .pr-content rev-parse HEAD)" = "$HEAD_SHA"',
            self.workflow,
        )

        scope = _step_block(self.workflow, "Detect Foundry scope and live validation label")
        self.assertIn(
            "python3 .trusted-policy/infra/scripts/pr_foundry_scope.py", scope
        )
        self.assertIn("--repo-root .pr-content", scope)

    def test_credential_bearing_deploy_has_trusted_event_context_gate(self) -> None:
        deploy = re.search(
            r"(?ms)^  deploy:\n(?P<body>.*?)(?=^  [a-zA-Z_]+:|\Z)", self.workflow
        )
        self.assertIsNotNone(deploy)
        assert deploy is not None
        body = deploy.group("body")
        self.assertIn("environment: azure-pr-app", body)
        self.assertIn("id-token: write", body)
        self.assertIn("github.event.pull_request.head.repo.fork == false", body)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            body,
        )
        self.assertIn("github.event.pull_request.draft == false", body)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", body)
        self.assertIn("persist-credentials: false", body)

    def test_deploy_diagnostics_survive_nonzero_helper_exits(self) -> None:
        for step_name, helper in (
            ("Enforce app-tier concurrency cap", "pr_preflight.py"),
            ("Smoke test (/health/live + /health/ready)", "pr_smoke_test.py"),
        ):
            with self.subTest(step=step_name):
                block = _step_block(self.workflow, step_name)
                self.assertIn(f"set +e\n          output=\"$(python3 infra/scripts/{helper}", block)
                self.assertIn("--format env 2>&1)\"", block)
                self.assertIn("rc=$?\n          set -e", block)
                self.assertIn("printf '%s\\n' \"$output\"", block)

    def test_resource_group_is_tagged_before_azd_provision(self) -> None:
        create_block = _step_block(self.workflow, "Create and atomically tag PR resource group")
        self.assertIn('rg="rg-${AZURE_ENV_NAME}"', create_block)
        self.assertIn("az group create --name", create_block)
        self.assertIn("ephemeral=true", create_block)
        self.assertIn('azd env set AZURE_RESOURCE_GROUP "$rg"', create_block)
        self.assertLess(
            self.workflow.index("Create and atomically tag PR resource group"),
            self.workflow.index("- name: azd provision"),
        )

    def test_live_foundry_validation_is_explicitly_gated_and_verifies_binding(self) -> None:
        live = re.search(
            r"(?ms)^  live_foundry_validation:\n(?P<body>.*?)(?=^  [a-zA-Z_]+:|\Z)",
            self.workflow,
        )
        self.assertIsNotNone(live)
        assert live is not None
        body = live.group("body")
        self.assertIn(
            "needs.preflight.outputs.live_validation_requested == 'true'", body
        )
        self.assertIn("environment: azure-pr-app", body)
        self.assertIn("id-token: write", body)
        self.assertIn("Azure CLI login for read-only binding evidence", body)
        self.assertIn("Verify live versioned RAI policy binding", body)
        self.assertIn("az cognitiveservices account deployment show", body)
        self.assertNotIn("github.event.pull_request.head.sha", body)
        self.assertNotIn("infra/scripts/verify_foundry_rai_binding.py", body)
        self.assertIn(
            'deployment_properties.get("raiPolicyName") == expected',
            body,
        )
        self.assertIn(
            'policy_properties.get("basePolicyName") == "Microsoft.DefaultV2"',
            body,
        )
        self.assertIn('policy_properties.get("mode") == "Blocking"', body)
        self.assertLess(
            body.index("Verify live versioned RAI policy binding"),
            body.index("Exercise sanitized gpt-image-2 card-generation path"),
        )
        self.assertIn(
            '"description": "adult original fantasy knight made of living flame"',
            body,
        )

    def test_janitor_requires_explicit_opt_in_for_untagged_orphan_deletion(self) -> None:
        self.assertIn("default: true", self.janitor_workflow)
        self.assertIn("reap_untagged_orphans:", self.janitor_workflow)
        self.assertIn("default: false", self.janitor_workflow)
        self.assertIn("az group list -o json", self.janitor_workflow)
        self.assertIn("--active-pr-numbers", self.janitor_workflow)
        self.assertIn("--closed-prs-json", self.janitor_workflow)
        self.assertIn("Report verified untagged orphan candidates", self.janitor_workflow)
        self.assertIn("Delete verified untagged orphan groups", self.janitor_workflow)
        self.assertIn("inputs.reap_untagged_orphans == true", self.janitor_workflow)


if __name__ == "__main__":
    unittest.main()
