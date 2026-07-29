"""Validate sanitized live evidence for a Foundry deployment RAI binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


VERIFICATION_FAILED_EXIT_CODE = 2


def verify(
    deployment: object, policy: object, expected_policy_name: str
) -> dict[str, str | bool]:
    if not expected_policy_name or not isinstance(deployment, dict) or not isinstance(
        policy, dict
    ):
        raise ValueError("Foundry RAI binding evidence is incomplete.")

    deployment_properties = deployment.get("properties")
    policy_properties = policy.get("properties")
    if not isinstance(deployment_properties, dict) or not isinstance(
        policy_properties, dict
    ):
        raise ValueError("Foundry RAI binding evidence is incomplete.")

    policy_resource_name = str(policy.get("name", "")).rsplit("/", 1)[-1]
    if (
        deployment_properties.get("raiPolicyName") != expected_policy_name
        or policy_resource_name != expected_policy_name
        or policy_properties.get("basePolicyName") != "Microsoft.DefaultV2"
        or policy_properties.get("mode") != "Blocking"
    ):
        raise ValueError("Foundry RAI binding evidence does not match the release contract.")

    return {
        "verified": True,
        "policy_name": expected_policy_name,
        "base_policy": "Microsoft.DefaultV2",
        "mode": "Blocking",
    }


def _load_document(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_foundry_rai_binding")
    parser.add_argument("--deployment-json", required=True)
    parser.add_argument("--policy-json", required=True)
    parser.add_argument("--expected-policy-name", required=True)
    parser.add_argument("--format", choices=("json", "github"), required=True)
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        result = verify(
            _load_document(arguments.deployment_json),
            _load_document(arguments.policy_json),
            arguments.expected_policy_name,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        if arguments.format == "github":
            print("verified=false")
            print("error=Foundry RAI binding verification failed.")
        else:
            print(
                json.dumps(
                    {
                        "verified": False,
                        "error": "Foundry RAI binding verification failed.",
                    },
                    sort_keys=True,
                )
            )
        return VERIFICATION_FAILED_EXIT_CODE

    if arguments.format == "github":
        for name, value in result.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            print(f"{name}={rendered}")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
