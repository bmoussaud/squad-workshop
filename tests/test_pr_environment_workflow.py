from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "pr-environment.yml"


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


if __name__ == "__main__":
    unittest.main()
