"""Retire the pre-container-scope Storage Blob Data Contributor assignment.

Run this explicitly as an after-deployment maintenance action after Bicep has
created the container-scoped assignment.
ARM incremental mode cannot delete a resource that was merely omitted from a
later template.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse


BLOB_DATA_CONTRIBUTOR_ROLE_ID = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
MAX_CLI_DIAGNOSTIC_LENGTH = 4_096
SENSITIVE_CLI_VALUE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["']?(?:access[_-]?token|refresh[_-]?token|id[_-]?token|token|
        authorization|client[_-]?secret|secret|password|connection[_-]?string|
        sig)["']?\s*[:=]\s*
    )
    (?P<value>"[^"\r\n]*"|'[^'\r\n]*'|[^\r\n,;]+)
    """
)
BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[a-z0-9\-._~+/=]+")


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be set from the successful Bicep provision.")
    return value


def safe_cli_diagnostic(value: str | bytes | None) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    redacted = SENSITIVE_CLI_VALUE.sub(r"\g<prefix>[REDACTED]", value)
    redacted = BEARER_TOKEN.sub("Bearer [REDACTED]", redacted)
    redacted = redacted.strip()
    if len(redacted) > MAX_CLI_DIAGNOSTIC_LENGTH:
        return f"{redacted[:MAX_CLI_DIAGNOSTIC_LENGTH]}… [truncated]"
    return redacted


def azure_cli_failure_details(error: subprocess.CalledProcessError) -> str:
    stderr = safe_cli_diagnostic(error.stderr)
    stdout = safe_cli_diagnostic(error.stdout or error.output)
    details = []
    if stderr:
        details.append(f"stderr: {stderr}")
    if stdout:
        details.append(f"stdout: {stdout}")
    return "; ".join(details) if details else "no diagnostic output was returned"


def run_az(*arguments: str) -> str:
    executable = shutil.which("az") or shutil.which("az.cmd")
    if executable is None:
        raise RuntimeError(
            "Azure CLI executable was not found. This maintenance action requires "
            "Azure CLI to verify and retire the legacy Blob RBAC assignment. Install "
            "Azure CLI, authenticate an authorized operator, and retry the script."
        )
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Azure CLI failed during legacy Blob RBAC retirement "
            f"(exit {error.returncode}): {azure_cli_failure_details(error)}"
        ) from error
    except OSError as error:
        raise RuntimeError(
            "Unable to execute Azure CLI for legacy Blob RBAC retirement. "
            "Verify the Azure CLI installation and retry the maintenance script."
        ) from error
    return completed.stdout


def role_assignment_ids(scope: str, principal_id: str) -> list[str]:
    result = run_az(
        "role",
        "assignment",
        "list",
        "--scope",
        scope,
        "--assignee",
        principal_id,
        "--role",
        BLOB_DATA_CONTRIBUTOR_ROLE_ID,
        "--query",
        "[].id",
        "--output",
        "json",
    )
    assignment_ids = json.loads(result)
    if not isinstance(assignment_ids, list) or not all(
        isinstance(assignment_id, str) for assignment_id in assignment_ids
    ):
        raise RuntimeError("Azure CLI returned an invalid role-assignment list.")
    return assignment_ids


def main() -> int:
    resource_group = required_environment("AZURE_RESOURCE_GROUP")
    storage_url = required_environment("AZURE_STORAGE_ACCOUNT_URL")
    application_principal_id = required_environment(
        "APPLICATION_IDENTITY_PRINCIPAL_ID"
    )

    storage_account_name = urlparse(storage_url).hostname
    if storage_account_name is None:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL must contain a hostname.")
    storage_account_name = storage_account_name.split(".", 1)[0]

    storage_account_id = run_az(
        "storage",
        "account",
        "show",
        "--resource-group",
        resource_group,
        "--name",
        storage_account_name,
        "--query",
        "id",
        "--output",
        "tsv",
    ).strip()
    if not storage_account_id:
        raise RuntimeError("Azure CLI did not return the Storage account resource ID.")

    container_scope = (
        f"{storage_account_id}/blobServices/default/containers/artifacts"
    )
    container_assignment_ids = role_assignment_ids(
        container_scope, application_principal_id
    )
    if len(container_assignment_ids) != 1:
        raise RuntimeError(
            "Refusing to retire the account-scoped assignment: expected exactly one "
            "direct Storage Blob Data Contributor assignment on the artifacts container."
        )

    legacy_assignment_ids = role_assignment_ids(
        storage_account_id, application_principal_id
    )
    if len(legacy_assignment_ids) != 1:
        raise RuntimeError(
            "Refusing to retire account-scoped assignments: expected exactly one direct "
            "Storage Blob Data Contributor assignment for the application identity."
        )
    run_az("role", "assignment", "delete", "--ids", legacy_assignment_ids[0])

    if role_assignment_ids(storage_account_id, application_principal_id):
        raise RuntimeError(
            "The legacy account-scoped Storage Blob Data Contributor assignment "
            "remains after retirement."
        )
    if len(role_assignment_ids(container_scope, application_principal_id)) != 1:
        raise RuntimeError(
            "The required container-scoped Storage Blob Data Contributor assignment "
            "is no longer present after retirement."
        )

    print(
        "Verified one Storage Blob Data Contributor assignment at the artifacts "
        "container scope and none at the Storage account scope."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Legacy Blob RBAC retirement failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
