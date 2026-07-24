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

    @patch.object(migration.subprocess, "run")
    @patch.object(migration.shutil, "which", return_value="/usr/local/bin/az")
    def test_includes_redacted_azure_cli_failure_diagnostics(
        self, which: Mock, run: Mock
    ) -> None:
        run.side_effect = migration.subprocess.CalledProcessError(
            2,
            ["az", "role", "assignment", "list"],
            output='{"access_token":"should-not-appear"}',
            stderr=(
                "ERROR: unrecognized arguments: --assignee-object-id "
                "Authorization: should-not-appear"
            ),
        )

        with self.assertRaises(RuntimeError) as raised:
            migration.run_az("role", "assignment", "list")

        message = str(raised.exception)
        self.assertIn("exit 2", message)
        self.assertIn(
            "stderr: ERROR: unrecognized arguments: --assignee-object-id",
            message,
        )
        self.assertIn('stdout: {"access_token":[REDACTED]}', message)
        self.assertNotIn("should-not-appear", message)
        which.assert_called_once_with("az")
        run.assert_called_once()


class RoleAssignmentIdsTests(unittest.TestCase):
    @patch.object(migration, "run_az", return_value='["assignment-id"]')
    def test_uses_supported_assignee_flag_at_the_exact_scope(
        self, run_az: Mock
    ) -> None:
        assignment_ids = migration.role_assignment_ids(
            "/storage-account/blobServices/default/containers/artifacts",
            "principal-id",
        )

        self.assertEqual(assignment_ids, ["assignment-id"])
        run_az.assert_called_once_with(
            "role",
            "assignment",
            "list",
            "--scope",
            "/storage-account/blobServices/default/containers/artifacts",
            "--assignee",
            "principal-id",
            "--role",
            migration.BLOB_DATA_CONTRIBUTOR_ROLE_ID,
            "--query",
            "[].id",
            "--output",
            "json",
        )
