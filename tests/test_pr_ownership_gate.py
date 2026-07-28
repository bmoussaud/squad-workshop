import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_references(body: str) -> list[str]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    parser = re.search(
        r"(?ms)python3 - <<'PY'\n(?P<script>.*?)(?=^          PY$)",
        workflow,
    )
    if parser is None:
        raise AssertionError("The ownership gate's Markdown-aware parser is missing.")
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(parser.group("script"))],
        check=True,
        capture_output=True,
        env={**os.environ, "BODY": body},
        text=True,
    )
    return completed.stdout.splitlines()


class PullRequestOwnershipGateTests(unittest.TestCase):
    def assert_references(self, body: str, expected: list[str]) -> None:
        self.assertEqual(_workflow_references(body), expected)

    def test_ignores_inline_code_span(self) -> None:
        self.assert_references("Document `Closes #99`.\n\nCloses #27", ["27"])

    def test_ignores_fenced_code_block(self) -> None:
        self.assert_references("```\nCloses #99\n```\n\nCloses #27", ["27"])

    def test_ignores_tilde_fenced_code_block(self) -> None:
        self.assert_references("~~~markdown\nCloses #99\n~~~\n\nCloses #27", ["27"])

    def test_ignores_indented_code_block(self) -> None:
        self.assert_references("    Closes #99\n\nCloses #27", ["27"])

    def test_ignores_markdown_table_cell(self) -> None:
        self.assert_references(
            "| Scenario | Syntax |\n| --- | --- |\n| Example | Closes #99 |\n\nCloses #27",
            ["27"],
        )

    def test_ignores_blockquote(self) -> None:
        self.assert_references("> Documented syntax: Closes #99\n\nCloses #27", ["27"])

    def test_ignores_code_span_with_nested_backticks(self) -> None:
        self.assert_references("``Document `Closes #99` here``\n\nCloses #27", ["27"])

    def test_unbalanced_backticks_do_not_hide_top_level_text(self) -> None:
        self.assert_references("Unbalanced ` syntax: Closes #99\n\nCloses #27", ["99", "27"])

    def test_detects_top_level_closing_reference(self) -> None:
        self.assert_references("This resolves the request: Closes #27.", ["27"])

    def test_deduplicates_a_repeated_closing_reference(self) -> None:
        self.assert_references("Closes #27\n\nChecklist: fixes #27", ["27"])

    def test_rejects_zero_issue_references(self) -> None:
        self.assertFalse(_workflow_references("Implements documentation only."))

    def test_rejects_two_distinct_issue_references(self) -> None:
        self.assertEqual(_workflow_references("Closes #27 and resolves #28"), ["27", "28"])


if __name__ == "__main__":
    unittest.main()
