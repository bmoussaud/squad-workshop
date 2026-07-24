from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "infra/scripts/retire_legacy_storage_blob_role.py"
)
SPEC = spec_from_file_location("retire_legacy_storage_blob_role", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
migration = module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class RunAzureCliTests(unittest.TestCase):
    @patch.object(migration.subprocess, "run")
    @patch.object(migration.shutil, "which")
    def test_uses_resolved_azure_cli_executable(
        self, which: Mock, run: Mock
    ) -> None:
        which.return_value = "/usr/local/bin/az"
        run.return_value = SimpleNamespace(stdout='["assignment-id"]')

        result = migration.run_az("role", "assignment", "list")

        self.assertEqual(result, '["assignment-id"]')
        which.assert_called_once_with("az")
        run.assert_called_once_with(
            ["/usr/local/bin/az", "role", "assignment", "list"],
            check=True,
            capture_output=True,
            text=True,
        )

    @patch.object(migration.subprocess, "run")
    @patch.object(migration.shutil, "which")
    def test_falls_back_to_windows_azure_cli_command_file(
        self, which: Mock, run: Mock
    ) -> None:
        which.side_effect = [
            None,
            r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        ]
        run.return_value = SimpleNamespace(stdout="")

        migration.run_az("account", "show")

        self.assertEqual(which.call_args_list, [call("az"), call("az.cmd")])
        run.assert_called_once_with(
            [
                r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
                "account",
                "show",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    @patch.object(migration.subprocess, "run")
    @patch.object(migration.shutil, "which", return_value=None)
    def test_fails_closed_when_azure_cli_is_missing(
        self, which: Mock, run: Mock
    ) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "requires Azure CLI to verify and retire the legacy Blob RBAC assignment",
        ):
            migration.run_az("role", "assignment", "list")

        self.assertEqual(which.call_args_list, [call("az"), call("az.cmd")])
        run.assert_not_called()
