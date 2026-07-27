"""Unit tests for the ``pr_preflight`` command-line interface (Phase 3, #15).

The preflight module lives under ``infra/scripts`` (CI/platform tooling, not
application domain logic), so it is loaded by path -- matching the existing
``tests/test_pr_environment_names.py`` convention. These tests cover the CLI the
PR-environment workflow consumes: the tri-state verdict, the exit-code contract
(``0`` for PROCEED/SKIP, non-zero for BLOCKED), the strict-boolean fail-closed
parsing of attacker-controlled trust signals, and log safety of the output.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import io
import json
import sys
import unittest
from contextlib import redirect_stdout


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


preflight = _load("pr_preflight")

REPO = "bmoussaud/squad-workshop"
BRANCH = "squad/14-render-card-layout"
ACR = "sharedacrfantasycards"


def _run(**overrides) -> tuple[int, dict[str, str]]:
    """Invoke the CLI with sensible same-repo defaults and return (exit, fields)."""
    args = {
        "--repo": REPO,
        "--pr-number": "14",
        "--branch": BRANCH,
        "--is-fork": "false",
        "--is-draft": "false",
        "--base-repo": REPO,
        "--head-repo": REPO,
        "--referenced-acr-name": ACR,
        "--active-app-env-count": "0",
    }
    args.update(overrides)
    argv = ["--format", "json"]
    for key, value in args.items():
        argv.extend([key, value])
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = preflight.main(argv)
    return code, json.loads(buffer.getvalue())


class PreflightCliDecisionTests(unittest.TestCase):
    def test_same_repo_non_draft_proceeds(self) -> None:
        code, fields = _run()
        self.assertEqual(code, 0)
        self.assertEqual(fields["decision"], "proceed")
        self.assertEqual(fields["reason_code"], "ok")

    def test_draft_skips_without_failing(self) -> None:
        code, fields = _run(**{"--is-draft": "true"})
        self.assertEqual(code, 0)
        self.assertEqual(fields["decision"], "skip")
        self.assertEqual(fields["reason_code"], "draft_pr")

    def test_fork_is_blocked_and_fails_the_run(self) -> None:
        code, fields = _run(**{"--is-fork": "true", "--head-repo": "attacker/squad-workshop"})
        self.assertNotEqual(code, 0)
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["decision"], "blocked")
        self.assertEqual(fields["reason_code"], "fork_pr")

    def test_concurrency_cap_blocks(self) -> None:
        code, fields = _run(**{"--active-app-env-count": "3"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["decision"], "blocked")
        self.assertEqual(fields["reason_code"], "app_concurrency_cap")

    def test_untrusted_head_repo_blocks(self) -> None:
        code, fields = _run(**{"--head-repo": "someoneelse/squad-workshop"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["reason_code"], "untrusted_repo")

    def test_non_conforming_branch_blocks(self) -> None:
        code, fields = _run(**{"--branch": "bmoussaud-musical-spork"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["reason_code"], "invalid_names")


class PreflightCliFailClosedTests(unittest.TestCase):
    """A malformed trust signal must never be coerced to a permissive answer."""

    def test_empty_fork_signal_fails_closed(self) -> None:
        code, fields = _run(**{"--is-fork": ""})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["reason_code"], "invalid_trust_signal")

    def test_garbage_fork_signal_fails_closed(self) -> None:
        # A non-"true"/"false" string (e.g. an unrendered Actions context) must
        # NOT be read as truthy/falsey -- it is a malformed signal, so BLOCKED.
        code, fields = _run(**{"--is-fork": "yes"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["reason_code"], "invalid_trust_signal")

    def test_true_string_is_the_only_truthy_fork_value(self) -> None:
        self.assertIs(preflight._parse_tristate_bool("true"), True)
        self.assertIs(preflight._parse_tristate_bool("TRUE"), True)
        self.assertIs(preflight._parse_tristate_bool("false"), False)
        self.assertIsNone(preflight._parse_tristate_bool("1"))
        self.assertIsNone(preflight._parse_tristate_bool(""))

    def test_unknown_count_fails_closed(self) -> None:
        code, fields = _run(**{"--active-app-env-count": "not-a-number"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertEqual(fields["reason_code"], "app_concurrency_cap")

    def test_parse_count_maps_non_numeric_to_negative_sentinel(self) -> None:
        self.assertEqual(preflight._parse_count("5"), 5)
        self.assertEqual(preflight._parse_count(""), -1)
        self.assertEqual(preflight._parse_count("-3"), -1)
        self.assertEqual(preflight._parse_count("x"), -1)


class PreflightCliOutputSafetyTests(unittest.TestCase):
    def test_env_format_emits_three_known_keys(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = preflight.main(
                [
                    "--repo", REPO,
                    "--pr-number", "14",
                    "--branch", BRANCH,
                    "--is-fork", "false",
                    "--is-draft", "false",
                    "--base-repo", REPO,
                    "--head-repo", REPO,
                    "--referenced-acr-name", ACR,
                    "--active-app-env-count", "0",
                ]
            )
        self.assertEqual(code, 0)
        lines = [line for line in buffer.getvalue().splitlines() if line]
        keys = {line.split("=", 1)[0] for line in lines}
        self.assertEqual(keys, {"decision", "reason_code", "message"})

    def test_crafted_branch_cannot_inject_a_log_line(self) -> None:
        # A branch carrying a real newline/CR must never survive into the
        # emitted message as a control character that could open a fresh log
        # line or a forged GitHub Actions workflow command.
        code, fields = _run(**{"--branch": "squad/1-x\n\r::error::pwn"})
        self.assertEqual(code, preflight.BLOCKED_EXIT_CODE)
        self.assertNotIn("\n", fields["message"])
        self.assertNotIn("\r", fields["message"])


if __name__ == "__main__":
    unittest.main()
