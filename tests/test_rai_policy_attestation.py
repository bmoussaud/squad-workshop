import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "infra" / "scripts" / "verify_rai_policy.py"
SPEC = importlib.util.spec_from_file_location("verify_rai_policy", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load RAI policy attestation module")
attestation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(attestation)


def valid_documents():
    filters = []
    for (name, source), (enabled, blocking, severity) in attestation.EXPECTED_FILTERS.items():
        item = {
            "name": name,
            "source": source,
            "enabled": enabled,
            "blocking": blocking,
        }
        if severity is not None:
            item["severityThreshold"] = severity
        filters.append(item)
    deployment = {"properties": {"raiPolicyName": "policy-v1"}}
    policy = {
        "properties": {
            "basePolicyName": attestation.EXPECTED_BASE_POLICY,
            "mode": "Default",
            "contentFilters": filters,
            "customBlocklists": [
                {
                    "blocklistName": "blocklist-v1",
                    "blocking": True,
                    "source": "Prompt",
                }
            ],
        }
    }
    blocklist = {
        "properties": {"description": attestation.EXPECTED_BLOCKLIST_DESCRIPTION}
    }
    items = {
        "value": [
            {
                "name": name,
                "properties": {"isRegex": is_regex, "pattern": pattern},
            }
            for name, (is_regex, pattern) in attestation.EXPECTED_BLOCKLIST_ITEMS.items()
        ]
    }
    return deployment, policy, blocklist, items


class RaiPolicyAttestationTests(unittest.TestCase):
    def test_accepts_only_canonical_expected_properties(self) -> None:
        attestation.verify_documents(
            *valid_documents(),
            policy_name="policy-v1",
            blocklist_name="blocklist-v1",
        )

    def test_rejects_alias_only_policy_evidence(self) -> None:
        deployment, policy, blocklist, items = valid_documents()
        del policy["properties"]["contentFilters"]
        policy["properties"]["configuredFilters"] = "expected"

        with self.assertRaisesRegex(
            attestation.AttestationError, "canonical contentFilters"
        ):
            attestation.verify_documents(
                deployment,
                policy,
                blocklist,
                items,
                policy_name="policy-v1",
                blocklist_name="blocklist-v1",
            )

    def test_rejects_extra_or_duplicate_canonical_policy_entries(self) -> None:
        deployment, policy, blocklist, items = valid_documents()
        policy["properties"]["contentFilters"].append(
            {
                "name": "Unexpected",
                "source": "Prompt",
                "enabled": False,
                "blocking": False,
            }
        )

        with self.assertRaisesRegex(attestation.AttestationError, "exactly"):
            attestation.verify_documents(
                deployment,
                policy,
                blocklist,
                items,
                policy_name="policy-v1",
                blocklist_name="blocklist-v1",
            )

        deployment, policy, blocklist, items = valid_documents()
        policy["properties"]["contentFilters"].append(
            dict(policy["properties"]["contentFilters"][0])
        )
        with self.assertRaisesRegex(attestation.AttestationError, "duplicates"):
            attestation.verify_documents(
                deployment,
                policy,
                blocklist,
                items,
                policy_name="policy-v1",
                blocklist_name="blocklist-v1",
            )

        deployment, policy, blocklist, items = valid_documents()
        policy["properties"]["customBlocklists"].append(
            {
                "blocklistName": "other",
                "blocking": False,
                "source": "Completion",
            }
        )
        with self.assertRaisesRegex(attestation.AttestationError, "exactly"):
            attestation.verify_documents(
                deployment,
                policy,
                blocklist,
                items,
                policy_name="policy-v1",
                blocklist_name="blocklist-v1",
            )

    def test_rejects_missing_or_drifted_blocklist_properties(self) -> None:
        deployment, policy, blocklist, items = valid_documents()
        items["value"][0]["properties"]["pattern"] = "Different"

        with self.assertRaisesRegex(
            attestation.AttestationError, "canonical item properties"
        ):
            attestation.verify_documents(
                deployment,
                policy,
                blocklist,
                items,
                policy_name="policy-v1",
                blocklist_name="blocklist-v1",
            )

    def test_fixture_cli_is_fail_closed_and_does_not_need_azure(self) -> None:
        documents = valid_documents()
        environment = {
            "FANTASY_CARD_RAI_POLICY_NAME": "policy-v1",
            "FANTASY_CARD_RAI_BLOCKLIST_NAME": "blocklist-v1",
        }
        with TemporaryDirectory() as directory:
            paths = []
            for index, document in enumerate(documents):
                path = Path(directory) / f"{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.append(path)
            arguments = [
                "--deployment-json",
                str(paths[0]),
                "--policy-json",
                str(paths[1]),
                "--blocklist-json",
                str(paths[2]),
                "--blocklist-items-json",
                str(paths[3]),
            ]
            with patch.dict(os.environ, environment, clear=True), patch.object(
                attestation.subprocess, "run"
            ) as run:
                self.assertEqual(attestation.main(arguments), 0)
                run.assert_not_called()

            documents[1]["properties"]["customBlocklists"] = []
            paths[1].write_text(json.dumps(documents[1]), encoding="utf-8")
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(attestation.main(arguments), 1)

    def test_release_gate_fails_when_live_context_is_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {"DEPLOY_FOUNDRY": "true"},
            clear=True,
        ):
            self.assertEqual(
                attestation.main(["--gate-if-foundry-deployed"]),
                1,
            )
