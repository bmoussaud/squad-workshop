import base64
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import httpx
import openai
from PIL import Image

from fantasy_cards.adapters import ImageGenerationError, build_card_prompt
from fantasy_cards.cli import main
from fantasy_cards.config import ConfigurationError
from fantasy_cards.policy import CONTENT_POLICY_REFUSAL


SAFE_PROMPT = "adult original fantasy knight made of living flame"
CLIENT_ID = "11111111-1111-4111-8111-111111111111"


class CliTests(unittest.TestCase):
    @patch("fantasy_cards.cli.load_dotenv")
    def test_loads_dotenv_before_building_application(self, load_dotenv: Mock) -> None:
        with patch("sys.argv", ["fantasy-card", "Ember Sentinel", SAFE_PROMPT]), patch(
            "fantasy_cards.cli.build_local_application",
            side_effect=RuntimeError("composition reached"),
        ), self.assertRaisesRegex(RuntimeError, "composition reached"):
            main()

        load_dotenv.assert_called_once_with()

    def test_prints_a_successful_job(self) -> None:
        output = StringIO()

        with patch(
            "fantasy_cards.cli.load_dotenv"
        ), TemporaryDirectory() as output_directory, patch.dict(
            "os.environ",
            {"FANTASY_CARD_OUTPUT_DIR": output_directory},
            clear=True,
        ), patch(
            "sys.argv",
            [
                "fantasy-card",
                "Ember Sentinel",
                SAFE_PROMPT,
                "--correlation-id",
                "corr-cli",
                "--idempotency-key",
                "idem-cli",
            ],
        ), redirect_stdout(output):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            job = json.loads(output.getvalue())
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["correlation_id"], "corr-cli")
            self.assertEqual(job["idempotency_key"], "idem-cli")
            self.assertEqual(job["generator_name"], "in-memory")
            self.assertEqual(job["artifact"]["media_type"], "text/plain")
            artifact_path = Path(job["artifact"]["file_path"])
            self.assertEqual(artifact_path.parent, Path(output_directory))
            self.assertIn(job["artifact"]["artifact_id"], artifact_path.name)
            self.assertEqual(
                artifact_path.read_bytes(),
                f"generated card for: Ember Sentinel | {SAFE_PROMPT}".encode(),
            )

    def test_selects_foundry_provider_offline_from_environment(self) -> None:
        png_output = BytesIO()
        Image.new("RGB", (1, 1), "blue").save(png_output, format="PNG")
        client = Mock()
        client.images.generate.return_value.data = [
            Mock(b64_json=base64.b64encode(png_output.getvalue()).decode())
        ]
        output = StringIO()

        with TemporaryDirectory() as output_directory, patch.dict(
            "os.environ",
            {
                "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
                "AZURE_OPENAI_ENDPOINT": "https://cards.openai.azure.com",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-image-2-deployment",
                "AZURE_CLIENT_ID": CLIENT_ID,
                "FANTASY_CARD_CONTENT_POLICY_ID": "original-fantasy-closed-v1",
                "FANTASY_CARD_CONTENT_POLICY_VERSION": "1",
                "FANTASY_CARD_FOUNDRY_RAI_POLICY_NAME": "rai-fantasy-cards-v1",
                "FANTASY_CARD_FOUNDRY_BOUND_RAI_POLICY_NAME": "rai-fantasy-cards-v1",
                "FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "45",
                "FANTASY_CARD_OUTPUT_DIR": output_directory,
            },
            clear=True,
        ), patch(
            "sys.argv",
            [
                "fantasy-card",
                "Ember Sentinel",
                SAFE_PROMPT,
                "--correlation-id",
                "corr-foundry",
                "--idempotency-key",
                "idem-foundry",
            ],
        ), patch(
            "fantasy_cards.config.create_foundry_client", return_value=client
        ) as client_factory, redirect_stdout(output):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            job = json.loads(output.getvalue())
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["generator_name"], "foundry")
            self.assertEqual(job["artifact"]["media_type"], "image/png")
            artifact_path = Path(job["artifact"]["file_path"])
            self.assertEqual(artifact_path.parent, Path(output_directory))
            self.assertEqual(artifact_path.suffix, ".png")
            self.assertEqual(artifact_path.read_bytes(), png_output.getvalue())
            self.assertNotIn(SAFE_PROMPT, output.getvalue())
            client_factory.assert_called_once_with(
                "https://cards.openai.azure.com", 45.0, CLIENT_ID
            )
            client.images.generate.assert_called_once_with(
                model="gpt-image-2-deployment",
                prompt=build_card_prompt("Ember Sentinel", SAFE_PROMPT),
                n=1,
                size="1024x1536",
            )

    def test_returns_safe_nonzero_result_for_configuration_failure(self) -> None:
        error_output = StringIO()

        with patch("sys.argv", ["fantasy-card", "Ember Sentinel", SAFE_PROMPT]), patch(
            "fantasy_cards.cli.build_local_application",
            side_effect=ConfigurationError("Configuration is invalid."),
        ), redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(error_output.getvalue(), "Error: Configuration is invalid.\n")
        self.assertNotIn(SAFE_PROMPT, error_output.getvalue())

    def test_returns_safe_nonzero_result_for_generation_failure(self) -> None:
        error_output = StringIO()
        application = Mock()
        application.service.generate.side_effect = ImageGenerationError(
            "provider_unavailable", "The image provider is temporarily unavailable."
        )

        with patch("sys.argv", ["fantasy-card", "Ember Sentinel", SAFE_PROMPT]), patch(
            "fantasy_cards.cli.build_local_application", return_value=application
        ), redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertIn("temporarily unavailable", error_output.getvalue())
        self.assertNotIn(SAFE_PROMPT, error_output.getvalue())

    def test_real_openai_internal_server_error_returns_without_traceback(self) -> None:
        request = httpx.Request(
            "POST",
            "https://example.services.ai.azure.com/openai/v1/images/generations",
        )
        response = httpx.Response(
            500,
            request=request,
            json={"error": {"message": "Unable to get resource information."}},
        )
        client = Mock()
        client.images.generate.side_effect = openai.InternalServerError(
            "Unable to get resource information.",
            response=response,
            body=response.json(),
        )
        error_output = StringIO()
        environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
            "AZURE_OPENAI_ENDPOINT": (
                "https://example.services.ai.azure.com/openai/v1"
            ),
            "AZURE_OPENAI_DEPLOYMENT_NAME": "image-deployment",
            "AZURE_CLIENT_ID": CLIENT_ID,
            "FANTASY_CARD_CONTENT_POLICY_ID": "original-fantasy-closed-v1",
            "FANTASY_CARD_CONTENT_POLICY_VERSION": "1",
            "FANTASY_CARD_FOUNDRY_RAI_POLICY_NAME": "rai-fantasy-cards-v1",
            "FANTASY_CARD_FOUNDRY_BOUND_RAI_POLICY_NAME": "rai-fantasy-cards-v1",
        }

        with patch.dict("os.environ", environment, clear=True), patch(
            "sys.argv", ["fantasy-card", "Ember Sentinel", SAFE_PROMPT]
        ), patch(
            "fantasy_cards.config.create_foundry_client", return_value=client
        ), redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            error_output.getvalue(),
            "Error: The image provider is temporarily unavailable.\n",
        )
        self.assertNotIn("Traceback", error_output.getvalue())
        self.assertNotIn("Unable to get resource information", error_output.getvalue())
        self.assertNotIn(SAFE_PROMPT, error_output.getvalue())

    def test_policy_refusal_precedes_idempotency_and_composition_without_echo(self) -> None:
        rejected = "Barack Obama as Batman in banksy style age 12"
        error_output = StringIO()
        with patch(
            "sys.argv", ["fantasy-card", "Unknown Person", rejected]
        ), patch(
            "fantasy_cards.cli.deterministic_idempotency_key"
        ) as idempotency, patch(
            "fantasy_cards.cli.build_local_application"
        ) as build_application, redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(error_output.getvalue(), f"Error: {CONTENT_POLICY_REFUSAL}\n")
        self.assertNotIn(rejected, error_output.getvalue())
        idempotency.assert_not_called()
        build_application.assert_not_called()


if __name__ == "__main__":
    unittest.main()