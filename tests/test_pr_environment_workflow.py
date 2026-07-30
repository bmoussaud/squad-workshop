from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment.yml"
JANITOR_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment-janitor.yml"
TEARDOWN_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment-teardown.yml"
)


def _step_block(source: str, step_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^      - name: {re.escape(step_name)}\n(?P<body>.*?)(?=^      - name: |^  [a-zA-Z_]+:|\Z)"
    )
    match = pattern.search(source)
    if match is None:
        raise AssertionError(f"Missing workflow step {step_name!r}")
    return match.group("body")


def _job_block(source: str, job_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-zA-Z_]+:|\Z)"
    )
    match = pattern.search(source)
    if match is None:
        raise AssertionError(f"Missing workflow job {job_name!r}")
    return match.group("body")


def _normalized_job_if(job_block: str) -> str:
    match = re.search(
        r"(?m)^    if: >-\n(?P<expression>(?:      .*(?:\n|\Z))+)",
        job_block,
    )
    if match is None:
        raise AssertionError("Missing folded job-level if expression")
    return " ".join(match.group("expression").split())


class PrEnvironmentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.janitor_workflow = JANITOR_WORKFLOW.read_text(encoding="utf-8")
        cls.teardown_workflow = TEARDOWN_WORKFLOW.read_text(encoding="utf-8")

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

    def test_smoke_test_runs_only_after_trusted_auth_is_configured(self) -> None:
        # Smoke must not fire before configure_auth opens ingress and installs real OIDC
        # credentials. pull_request_target runs the base-branch (main) workflow, which
        # previously had smoke inside the deploy job. This assertion ensures the step is
        # absent from deploy and present only in configure_auth.
        deploy_job = _job_block(self.workflow, "deploy")
        self.assertNotIn("Smoke test (/health/live + /health/ready)", deploy_job)
        configure_auth_job = _job_block(self.workflow, "configure_auth")
        self.assertIn("Smoke test (/health/live + /health/ready)", configure_auth_job)
        # configure_auth must depend on deploy completing successfully
        self.assertIn("needs: [preflight, deploy]", configure_auth_job)
        configure_auth_if = _normalized_job_if(configure_auth_job)
        self.assertNotIn(
            "||",
            configure_auth_if,
            "configure_auth must not let any trusted-context guard bypass the others",
        )
        self.assertEqual(
            configure_auth_if,
            "always() && "
            "github.event.pull_request.head.repo.fork == false && "
            "github.event.pull_request.head.repo.full_name == github.repository && "
            "github.event.pull_request.draft == false && "
            "needs.deploy.result == 'success'",
        )
        self.assertNotIn("needs.preflight.outputs.eligible", configure_auth_job)

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

    def test_shared_platform_dependencies_are_validated_before_provisioning(self) -> None:
        validate = _step_block(self.workflow, "Validate shared platform dependencies")
        self.assertIn("SHARED_CONTAINER_REGISTRY_RESOURCE_GROUP_NAME", validate)
        self.assertIn("SHARED_FOUNDRY_RESOURCE_GROUP_NAME", validate)
        self.assertIn("az group exists", validate)
        self.assertIn("az acr show", validate)
        self.assertIn("az cognitiveservices account show", validate)
        self.assertIn("/projects/${SHARED_FOUNDRY_PROJECT_NAME}", validate)
        self.assertIn("az cognitiveservices account deployment show", validate)
        self.assertIn('if [ "$DEPLOY_FOUNDRY" = "false" ]', validate)
        self.assertLess(
            self.workflow.index("- name: Validate shared platform dependencies"),
            self.workflow.index("- name: Create and atomically tag PR resource group"),
        )
        self.assertLess(
            self.workflow.index("- name: Validate shared platform dependencies"),
            self.workflow.index("- name: azd provision"),
        )

    def test_pr_oidc_registration_runs_on_fresh_trusted_runner(self) -> None:
        deploy = _job_block(self.workflow, "deploy")
        configure = _job_block(self.workflow, "configure_auth")
        self.assertNotIn("ENTRA_AUTOMATION_CREDENTIALS", deploy)
        self.assertNotIn("graph.microsoft.com", deploy)
        self.assertIn("runs-on: ubuntu-latest", configure)
        self.assertIn(
            "ref: ${{ github.event.pull_request.base.sha }}\n"
            "          persist-credentials: false",
            configure,
        )
        self.assertNotIn("github.event.pull_request.head.sha", configure)
        self.assertIn("secrets.ENTRA_AUTOMATION_CREDENTIALS", configure)

        create = _step_block(self.workflow, "Create or rotate the PR OIDC application")
        self.assertIn("OIDC_MARKER", create)
        self.assertIn("OIDC_TAG", create)
        self.assertIn("graph.microsoft.com/v1.0/servicePrincipals", create)
        self.assertIn("/addPassword", create)
        self.assertIn('echo "::add-mask::$client_secret"', create)
        self.assertIn('echo "::add-mask::$session_current"', create)
        self.assertIn("PR_OIDC_CLIENT_SECRET=${client_secret}", create)
        self.assertIn('${APP_URL}/auth/callback', create)
        self.assertNotIn("local-anonymous", self.workflow)
        self.assertNotIn("FANTASY_CARD_AUTH_MODE", self.workflow)
        directory_login = _step_block(self.workflow, "Directory automation login")
        self.assertIn("secrets.ENTRA_AUTOMATION_CREDENTIALS", directory_login)
        self.assertNotIn("id-token", directory_login)
        self.assertLess(
            self.workflow.index("- name: Clear directory automation session"),
            self.workflow.index("- name: Azure resource login", self.workflow.index("configure_auth:")),
        )
        self.assertIn("Remove superseded PR OIDC credentials", self.workflow)

        configure_runtime = _step_block(
            self.workflow,
            "Install trusted authentication configuration and open ingress",
        )
        self.assertIn("az containerapp secret set", configure_runtime)
        self.assertIn("az containerapp ingress enable", configure_runtime)
        self.assertLess(
            configure_runtime.index("az containerapp secret set"),
            configure_runtime.index("az containerapp ingress enable"),
        )

    def test_pr_app_is_provisioned_closed_before_trusted_auth_configuration(
        self,
    ) -> None:
        inputs = _step_block(
            self.workflow, "Configure shared bindings and required infra inputs"
        )
        self.assertIn("FANTASY_CARD_EXTERNAL_INGRESS=false", inputs)
        self.assertIn("provisioning-placeholder-only", inputs)
        self.assertIn("ENABLE_CONTAINER_APPS_AUTH=false", inputs)
        self.assertIn(
            "trusted per-PR application OIDC is installed after provisioning", inputs
        )
        deploy_job = _job_block(self.workflow, "deploy")
        self.assertNotIn("ENTRA_AUTH_CLIENT_ID", deploy_job)
        self.assertNotIn("Validate Entra auth app wiring", deploy_job)
        configure_index = self.workflow.index("  configure_auth:")
        self.assertLess(
            self.workflow.index("- name: azd provision"),
            configure_index,
        )

    def test_teardown_deletes_only_the_marked_pr_oidc_registration(self) -> None:
        delete = _step_block(
            self.teardown_workflow, "Delete the isolated PR OIDC application"
        )
        self.assertIn("squad-workshop-pr-${PR_NUMBER}", delete)
        self.assertIn("squad-workshop-pr-auth", delete)
        self.assertIn("graph.microsoft.com/v1.0/applications", delete)
        self.assertIn("graph.microsoft.com/v1.0/servicePrincipals", delete)
        self.assertIn("--method DELETE", delete)

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
