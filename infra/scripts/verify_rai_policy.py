"""Fail-closed attestation of canonical Foundry RAI policy ARM properties."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import quote


API_VERSION = "2024-10-01"
EXPECTED_BASE_POLICY = "Microsoft.DefaultV2"
EXPECTED_BLOCKLIST_DESCRIPTION = (
    "Versioned protected-name prompt blocklist for fantasy card generation."
)
EXPECTED_FILTERS = {
    ("hate", "Prompt"): (True, True, "Medium"),
    ("sexual", "Prompt"): (True, True, "Medium"),
    ("violence", "Prompt"): (True, True, "Medium"),
    ("selfharm", "Prompt"): (True, True, "Medium"),
    ("hate", "Completion"): (True, True, "Medium"),
    ("sexual", "Completion"): (True, True, "Medium"),
    ("violence", "Completion"): (True, True, "Medium"),
    ("selfharm", "Completion"): (True, True, "Medium"),
    ("jailbreak", "Prompt"): (True, True, None),
    ("protected material text", "Completion"): (True, True, None),
}
EXPECTED_BLOCKLIST_ITEMS = {
    "crystal-guardian": (False, "Crystal Guardian"),
    "hollow-knight": (False, "Hollow Knight"),
    "mickey-mouse": (False, "Mickey Mouse"),
    "pikachu": (False, "Pikachu"),
    "taylor-swift": (False, "Taylor Swift"),
}


class AttestationError(RuntimeError):
    pass


def _properties(document: Any, label: str) -> dict[str, Any]:
    if not isinstance(document, dict) or not isinstance(document.get("properties"), dict):
        raise AttestationError(f"{label} response lacks canonical properties.")
    return document["properties"]


def verify_documents(
    deployment: Any,
    policy: Any,
    blocklist: Any,
    blocklist_items: Any,
    *,
    policy_name: str,
    blocklist_name: str,
) -> None:
    deployment_properties = _properties(deployment, "Deployment")
    if deployment_properties.get("raiPolicyName") != policy_name:
        raise AttestationError("Deployment canonical raiPolicyName is not the required policy.")

    policy_properties = _properties(policy, "RAI policy")
    if policy_properties.get("basePolicyName") != EXPECTED_BASE_POLICY:
        raise AttestationError("RAI policy canonical basePolicyName is not Microsoft.DefaultV2.")
    if policy_properties.get("mode") != "Default":
        raise AttestationError("RAI policy canonical mode is not Default.")

    filters = policy_properties.get("contentFilters")
    if not isinstance(filters, list):
        raise AttestationError("RAI policy canonical contentFilters is missing.")
    actual_filters: dict[tuple[str, str], tuple[Any, Any, Any]] = {}
    for item in filters:
        if not isinstance(item, dict):
            raise AttestationError("RAI policy contentFilters contains a malformed item.")
        name = item.get("name")
        source = item.get("source")
        if isinstance(name, str) and isinstance(source, str):
            key = (name.casefold(), source)
            if key in actual_filters:
                raise AttestationError("RAI policy canonical contentFilters has duplicates.")
            actual_filters[key] = (
                item.get("enabled"),
                item.get("blocking"),
                item.get("severityThreshold"),
            )
    if actual_filters != EXPECTED_FILTERS:
        raise AttestationError("RAI policy canonical contentFilters do not match exactly.")

    expected_binding = {
        "blocklistName": blocklist_name,
        "blocking": True,
        "source": "Prompt",
    }
    custom_blocklists = policy_properties.get("customBlocklists")
    if custom_blocklists != [expected_binding]:
        raise AttestationError(
            "RAI policy canonical customBlocklists do not match exactly."
        )

    blocklist_properties = _properties(blocklist, "RAI blocklist")
    if blocklist_properties.get("description") != EXPECTED_BLOCKLIST_DESCRIPTION:
        raise AttestationError("RAI blocklist canonical description does not match.")

    if not isinstance(blocklist_items, dict) or not isinstance(
        blocklist_items.get("value"), list
    ):
        raise AttestationError("RAI blocklist items response lacks canonical value.")
    actual_items: dict[str, tuple[Any, Any]] = {}
    for item in blocklist_items["value"]:
        if not isinstance(item, dict) or not isinstance(item.get("properties"), dict):
            raise AttestationError("RAI blocklist items contains a malformed item.")
        name = item.get("name")
        if isinstance(name, str):
            actual_items[name] = (
                item["properties"].get("isRegex"),
                item["properties"].get("pattern"),
            )
    if actual_items != EXPECTED_BLOCKLIST_ITEMS:
        raise AttestationError("RAI blocklist canonical item properties do not match.")


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _az_rest(url: str) -> Any:
    try:
        completed = subprocess.run(
            ["az", "rest", "--method", "get", "--url", url, "--output", "json"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise AttestationError("Azure CLI is unavailable for canonical ARM reads.") from error
    if completed.returncode:
        raise AttestationError("Canonical Foundry ARM read failed.")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AttestationError("Canonical Foundry ARM read returned invalid JSON.") from error


def _resource_url(
    subscription: str,
    resource_group: str,
    account: str,
    child_path: str,
) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{quote(subscription, safe='')}/resourceGroups/{quote(resource_group, safe='')}/"
        "providers/Microsoft.CognitiveServices/accounts/"
        f"{quote(account, safe='')}/{child_path}?api-version={API_VERSION}"
    )


def _required(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise AttestationError(f"Missing required live attestation value: {label}.")
    return value.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Attest canonical Foundry RAI policy and blocklist properties."
    )
    parser.add_argument("--deployment-json", type=Path)
    parser.add_argument("--policy-json", type=Path)
    parser.add_argument("--blocklist-json", type=Path)
    parser.add_argument("--blocklist-items-json", type=Path)
    parser.add_argument("--gate-if-foundry-deployed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.gate_if_foundry_deployed and os.environ.get(
        "DEPLOY_FOUNDRY", ""
    ).casefold() != "true":
        print("Foundry creation not requested; canonical attestation gate not applicable.")
        return 0

    fixture_paths = (
        arguments.deployment_json,
        arguments.policy_json,
        arguments.blocklist_json,
        arguments.blocklist_items_json,
    )
    try:
        policy_name = _required(
            os.environ.get("FANTASY_CARD_RAI_POLICY_NAME"),
            "FANTASY_CARD_RAI_POLICY_NAME",
        )
        blocklist_name = _required(
            os.environ.get("FANTASY_CARD_RAI_BLOCKLIST_NAME"),
            "FANTASY_CARD_RAI_BLOCKLIST_NAME",
        )
        if any(fixture_paths):
            if not all(fixture_paths):
                raise AttestationError("All four canonical JSON fixtures are required.")
            deployment, policy, blocklist, blocklist_items = (
                _load(path) for path in fixture_paths if path is not None
            )
        else:
            subscription = _required(
                os.environ.get("AZURE_SUBSCRIPTION_ID"), "AZURE_SUBSCRIPTION_ID"
            )
            resource_group = _required(
                os.environ.get("AZURE_RESOURCE_GROUP"), "AZURE_RESOURCE_GROUP"
            )
            account = _required(
                os.environ.get("AZURE_AI_ACCOUNT_NAME"), "AZURE_AI_ACCOUNT_NAME"
            )
            deployment_name = _required(
                os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                "AZURE_OPENAI_DEPLOYMENT_NAME",
            )
            deployment = _az_rest(
                _resource_url(
                    subscription,
                    resource_group,
                    account,
                    f"deployments/{quote(deployment_name, safe='')}",
                )
            )
            policy = _az_rest(
                _resource_url(
                    subscription,
                    resource_group,
                    account,
                    f"raiPolicies/{quote(policy_name, safe='')}",
                )
            )
            blocklist = _az_rest(
                _resource_url(
                    subscription,
                    resource_group,
                    account,
                    f"raiBlocklists/{quote(blocklist_name, safe='')}",
                )
            )
            blocklist_items = _az_rest(
                _resource_url(
                    subscription,
                    resource_group,
                    account,
                    f"raiBlocklists/{quote(blocklist_name, safe='')}/raiBlocklistItems",
                )
            )
        verify_documents(
            deployment,
            policy,
            blocklist,
            blocklist_items,
            policy_name=policy_name,
            blocklist_name=blocklist_name,
        )
    except (AttestationError, OSError, json.JSONDecodeError) as error:
        print(f"RAI policy attestation failed: {error}", file=sys.stderr)
        return 1
    print("Canonical Foundry RAI policy and blocklist properties attested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
