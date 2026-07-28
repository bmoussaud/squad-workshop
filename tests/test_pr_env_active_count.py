"""Unit tests for open-PR-aware environment counting."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout


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


active_count = _load("pr_env_active_count")


def _group(name: str, pr_number: str) -> dict[str, object]:
    return {"name": name, "tags": {"pr-number": pr_number}}


class ActiveEnvironmentCountTests(unittest.TestCase):
    def test_counts_only_open_pr_environments_and_excludes_current_pr(self) -> None:
        result = active_count.count_active_open_environments(
            [
                _group("rg-pr-58-live", "58"),
                _group("rg-pr-45-closed", "45"),
                _group("rg-pr-64-current", "64"),
                _group("rg-pr-66-closed", "66"),
            ],
            open_pr_numbers=frozenset({58, 64}),
            current_pr_number=64,
        )

        self.assertEqual(result.active_count, 1)
        self.assertEqual(result.active_names, ("rg-pr-58-live",))
        self.assertEqual(result.orphan_count, 2)
        self.assertEqual(result.orphan_names, ("rg-pr-45-closed", "rg-pr-66-closed"))

    def test_closed_pr_leak_does_not_consume_cap_when_no_other_pr_is_open(self) -> None:
        result = active_count.count_active_open_environments(
            [
                _group("rg-pr-45-closed", "45"),
                _group("rg-pr-58-closed", "58"),
                _group("rg-pr-66-closed", "66"),
            ],
            open_pr_numbers=frozenset({64}),
            current_pr_number=64,
        )

        self.assertEqual(result.active_count, 0)
        self.assertEqual(result.orphan_count, 3)

    def test_malformed_candidate_pr_number_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            active_count.count_active_open_environments(
                [_group("rg-pr-bad", "not-a-number")],
                open_pr_numbers=frozenset({64}),
                current_pr_number=64,
            )

    def test_malformed_resource_group_name_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            active_count.count_active_open_environments(
                [_group("rg-pr-45\n::error::bad", "45")],
                open_pr_numbers=frozenset({64}),
                current_pr_number=64,
            )


class ActiveEnvironmentCountCliTests(unittest.TestCase):
    def test_cli_emits_env_fields(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = active_count.main(
                [
                    "--groups-json",
                    json.dumps([_group("rg-pr-58-live", "58")]),
                    "--open-pr-numbers",
                    "58,64",
                    "--current-pr-number",
                    "64",
                ]
            )

        self.assertEqual(code, 0)
        fields = dict(line.split("=", 1) for line in buffer.getvalue().splitlines())
        self.assertEqual(fields["active_count"], "1")
        self.assertEqual(fields["active_names"], "rg-pr-58-live")
        self.assertEqual(fields["orphan_count"], "0")

    def test_cli_rejects_malformed_open_pr_list(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = active_count.main(
                [
                    "--groups-json",
                    "[]",
                    "--open-pr-numbers",
                    "64,not-a-number",
                    "--current-pr-number",
                    "64",
                ]
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error=", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
