"""Environment-backed application composition."""

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from fantasy_cards.adapters import (
    FoundryClientFactory,
    FoundryImageGenerator,
    InMemoryArtifactStore,
    InMemoryImageGenerator,
    InMemoryJobRepository,
    create_foundry_client,
    normalize_azure_openai_endpoint,
)
from fantasy_cards.application import GenerationService


@dataclass(frozen=True, slots=True)
class LocalApplication:
    service: GenerationService
    artifact_store: InMemoryArtifactStore
    job_repository: InMemoryJobRepository


class ConfigurationError(ValueError):
    """A safe runtime configuration error."""


@dataclass(frozen=True, slots=True)
class ImageGeneratorSettings:
    mode: str = "in-memory"
    endpoint: str | None = None
    deployment: str | None = None
    timeout_seconds: float = 60.0

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "ImageGeneratorSettings":
        values = os.environ if environment is None else environment
        raw_timeout = values.get("FANTASY_CARD_IMAGE_TIMEOUT_SECONDS", "60")
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError:
            raise ConfigurationError(
                "Image generation timeout must be a number."
            ) from None
        return cls(
            mode=values.get("FANTASY_CARD_IMAGE_GENERATOR", "in-memory"),
            endpoint=values.get("AZURE_OPENAI_ENDPOINT"),
            deployment=values.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            timeout_seconds=timeout_seconds,
        ).validated()

    def validated(self) -> "ImageGeneratorSettings":
        if self.mode not in ("in-memory", "foundry"):
            raise ConfigurationError(
                "Image generator must be 'in-memory' or 'foundry'."
            )
        if not 1 <= self.timeout_seconds <= 120:
            raise ConfigurationError(
                "Image generation timeout must be between 1 and 120 seconds."
            )
        if self.mode == "foundry" and (
            not self.endpoint
            or not self.endpoint.strip()
            or not self.deployment
            or not self.deployment.strip()
        ):
            raise ConfigurationError(
                "Foundry image generation configuration is incomplete."
            )
        if self.mode == "foundry":
            try:
                normalize_azure_openai_endpoint(self.endpoint or "")
            except ValueError:
                raise ConfigurationError(
                    "Azure OpenAI endpoint is invalid."
                ) from None
        return self


def build_local_application(
    settings: ImageGeneratorSettings | None = None,
    client_factory: FoundryClientFactory | None = None,
    output_directory: str | Path | None = None,
) -> LocalApplication:
    settings = (settings or ImageGeneratorSettings.from_environment()).validated()
    client_factory = client_factory or create_foundry_client
    artifact_store = InMemoryArtifactStore(
        output_directory or os.environ.get("FANTASY_CARD_OUTPUT_DIR", "artifacts")
    )
    job_repository = InMemoryJobRepository()
    if settings.mode == "foundry":
        image_generator = FoundryImageGenerator(
            endpoint=settings.endpoint or "",
            deployment=settings.deployment or "",
            timeout_seconds=settings.timeout_seconds,
            client_factory=client_factory,
        )
    else:
        image_generator = InMemoryImageGenerator()
    return LocalApplication(
        service=GenerationService(
            image_generator=image_generator,
            artifact_store=artifact_store,
            job_repository=job_repository,
        ),
        artifact_store=artifact_store,
        job_repository=job_repository,
    )
