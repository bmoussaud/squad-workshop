import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from infra.scripts import verify_foundry_rai_binding as verifier


POLICY_NAME = "rai-fantasy-cards-v1"


class FoundryRaiBindingVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.deployment = {"properties": {"raiPolicyName": POLICY_NAME}}
        self.policy = {
            "name": POLICY_NAME,
            "properties": {
                "basePolicyName": "Microsoft.DefaultV2",
                "mode": "Blocking",
            },
        }

    def test_accepts_exact_versioned_binding_and_baseline(self) -> None:
        self.assertEqual(
            verifier.verify(self.deployment, self.policy, POLICY_NAME),
            {
                "verified": True,
                "policy_name": POLICY_NAME,
                "base_policy": "Microsoft.DefaultV2",
                "mode": "Blocking",
            },
        )

    def test_rejects_binding_policy_or_mode_drift(self) -> None:
        cases = (
            ({"properties": {"raiPolicyName": "Microsoft.DefaultV2"}}, self.policy),
            (
                self.deployment,
                {
                    "name": "other",
                    "properties": {
                        "basePolicyName": "Microsoft.DefaultV2",
                        "mode": "Blocking",
                    },
                },
            ),
            (
                self.deployment,
                {
                    "name": POLICY_NAME,
                    "properties": {
                        "basePolicyName": "Microsoft.DefaultV2",
                        "mode": "Deferred",
                    },
                },
            ),
        )
        for deployment, policy in cases:
            with self.subTest(deployment=deployment, policy=policy):
                with self.assertRaises(ValueError):
                    verifier.verify(deployment, policy, POLICY_NAME)

    def test_cli_fails_closed_without_echoing_evidence(self) -> None:
        private_value = "private-resource-detail"
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            deployment_path = root / "deployment.json"
            policy_path = root / "policy.json"
            deployment_path.write_text(
                json.dumps(
                    {
                        "properties": {
                            "raiPolicyName": private_value,
                            "private": private_value,
                        }
                    }
                ),
                encoding="utf-8",
            )
            policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = verifier.main(
                    [
                        "--deployment-json",
                        str(deployment_path),
                        "--policy-json",
                        str(policy_path),
                        "--expected-policy-name",
                        POLICY_NAME,
                        "--format",
                        "github",
                    ]
                )

        self.assertEqual(exit_code, verifier.VERIFICATION_FAILED_EXIT_CODE)
        self.assertEqual(
            output.getvalue(),
            "verified=false\nerror=Foundry RAI binding verification failed.\n",
        )
        self.assertNotIn(private_value, output.getvalue())


if __name__ == "__main__":
    unittest.main()
