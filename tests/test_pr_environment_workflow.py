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
        self.assertIn("set +e\n          output=\"$(python3 infra/scripts/pr_preflight.py", block)
        self.assertIn("--format env 2>&1)\"", block)
        self.assertIn("rc=$?\n          set -e", block)
        self.assertIn("printf '%s\\n' \"$output\"", block)
        self.assertIn("grep -qx 'decision=blocked'", block)
        self.assertIn("printf '%s\\n' \"$output\" >> \"$GITHUB_OUTPUT\"", block)

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
