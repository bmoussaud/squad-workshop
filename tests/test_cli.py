import base64
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

import httpx
import openai
from PIL import Image

from fantasy_cards.cli import main
from fantasy_cards.adapters import ImageGenerationError
from fantasy_cards.config import ConfigurationError


class CliTests(unittest.TestCase):
    def test_prints_a_successful_job(self) -> None:
        output = StringIO()

        with TemporaryDirectory() as output_directory, patch.dict(
            "os.environ",
            {"FANTASY_CARD_OUTPUT_DIR": output_directory},
            clear=True,
        ), patch(
            "sys.argv",
            [
                "fantasy-card",
                "Ember Sentinel",
                "A knight made of living flame",
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
                b"generated image for: A knight made of living flame",
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
                "FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "45",
                "FANTASY_CARD_OUTPUT_DIR": output_directory,
            },
            clear=True,
        ), patch(
            "sys.argv",
            [
                "fantasy-card",
                "Ember Sentinel",
                "A private original prompt",
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
            self.assertNotIn("A private original prompt", output.getvalue())
            client_factory.assert_called_once_with(
                "https://cards.openai.azure.com", 45.0
            )
            client.images.generate.assert_called_once_with(
                model="gpt-image-2-deployment",
                prompt="A private original prompt",
                n=1,
                size="1024x1024",
            )

    def test_returns_safe_nonzero_result_for_configuration_failure(self) -> None:
        error_output = StringIO()

        with patch("sys.argv", ["fantasy-card", "Title", "private prompt"]), patch(
            "fantasy_cards.cli.build_local_application",
            side_effect=ConfigurationError("Configuration is invalid."),
        ), redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(error_output.getvalue(), "Error: Configuration is invalid.\n")
        self.assertNotIn("private prompt", error_output.getvalue())

    def test_returns_safe_nonzero_result_for_generation_failure(self) -> None:
        error_output = StringIO()
        application = Mock()
        application.service.generate.side_effect = ImageGenerationError(
            "provider_unavailable", "The image provider is temporarily unavailable."
        )

        with patch("sys.argv", ["fantasy-card", "Title", "private prompt"]), patch(
            "fantasy_cards.cli.build_local_application", return_value=application
        ), redirect_stderr(error_output):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertIn("temporarily unavailable", error_output.getvalue())
        self.assertNotIn("private prompt", error_output.getvalue())

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
        }

        with patch.dict("os.environ", environment, clear=True), patch(
            "sys.argv", ["fantasy-card", "Title", "private prompt"]
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
        self.assertNotIn("private prompt", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()