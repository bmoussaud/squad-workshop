"""Retire the pre-container-scope Storage Blob Data Contributor assignment.

This azd postprovision migration runs only after Bicep has created the
container-scoped assignment. ARM incremental mode cannot delete a resource
that was merely omitted from a later template.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from urllib.parse import urlparse


BLOB_DATA_CONTRIBUTOR_ROLE_ID = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be set by the successful Bicep provision.")
    return value


def run_az(*arguments: str) -> str:
    executable = shutil.which("az") or shutil.which("az.cmd")
    if executable is None:
        raise RuntimeError(
            "Azure CLI executable was not found. This azd postprovision hook requires "
            "Azure CLI to verify and retire the legacy Blob RBAC assignment. Install "
            "Azure CLI and rerun azd up."
        )
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError(
            "Unable to execute Azure CLI for postprovision Blob RBAC retirement. "
            "Verify the Azure CLI installation and rerun azd up."
        ) from error
    return completed.stdout


def role_assignment_ids(scope: str, principal_id: str) -> list[str]:
    result = run_az(
        "role",
        "assignment",
        "list",
        "--scope",
        scope,
        "--assignee-object-id",
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
    if len(legacy_assignment_ids) > 1:
        raise RuntimeError(
            "Refusing to retire account-scoped assignments: more than one direct "
            "Storage Blob Data Contributor assignment matched the application identity."
        )
    if legacy_assignment_ids:
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
