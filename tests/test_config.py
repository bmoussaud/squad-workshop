from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fantasy_cards.config import (
    ConfigurationError,
    ImageGeneratorSettings,
    build_local_application,
)


class ImageGeneratorSettingsTests(unittest.TestCase):
    def test_defaults_to_in_memory_without_foundry_settings(self) -> None:
        settings = ImageGeneratorSettings.from_environment({})

        self.assertEqual(settings.mode, "in-memory")
        with TemporaryDirectory() as output_directory:
            application = build_local_application(
                settings,
                client_factory=Mock(),
                output_directory=output_directory,
            )
            self.assertIsNotNone(application.service)

    def test_uses_output_directory_from_environment(self) -> None:
        with TemporaryDirectory() as output_directory, patch.dict(
            "os.environ",
            {"FANTASY_CARD_OUTPUT_DIR": output_directory},
            clear=True,
        ):
            application = build_local_application(client_factory=Mock())
            artifact = application.artifact_store.save(b"content", "text/plain")

        self.assertEqual(Path(artifact.file_path).parent, Path(output_directory))

    def test_requires_endpoint_and_deployment_only_for_foundry(self) -> None:
        for environment in (
            {"FANTASY_CARD_IMAGE_GENERATOR": "foundry"},
            {
                "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            },
            {
                "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
                "AZURE_OPENAI_ENDPOINT": " ",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "image-deployment",
            },
        ):
            with self.subTest(environment=environment):
                with self.assertRaises(ConfigurationError):
                    ImageGeneratorSettings.from_environment(environment)

    def test_validates_mode_and_bounded_timeout(self) -> None:
        for environment in (
            {"FANTASY_CARD_IMAGE_GENERATOR": "other"},
            {"FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "0"},
            {"FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "121"},
            {"FANTASY_CARD_IMAGE_TIMEOUT_SECONDS": "not-a-number"},
        ):
            with self.subTest(environment=environment):
                with self.assertRaises(ConfigurationError):
                    ImageGeneratorSettings.from_environment(environment)

    def test_rejects_unsafe_foundry_endpoint_during_composition(self) -> None:
        for endpoint in (
            "http://example.openai.azure.com",
            "https://example.openai.azure.com.evil.example",
            "https://example.openai.azure.com/models",
            "https://example.services.ai.azure.com/models",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(
                    ConfigurationError, "endpoint is invalid"
                ):
                    ImageGeneratorSettings.from_environment(
                        {
                            "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
                            "AZURE_OPENAI_ENDPOINT": endpoint,
                            "AZURE_OPENAI_DEPLOYMENT_NAME": "image-deployment",
                        }
                    )

    def test_foundry_client_factory_is_lazy(self) -> None:
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(data=[])
        factory = Mock(return_value=client)
        settings = ImageGeneratorSettings(
            mode="foundry",
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
        )

        with TemporaryDirectory() as output_directory:
            build_local_application(
                settings,
                client_factory=factory,
                output_directory=output_directory,
            )

        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()