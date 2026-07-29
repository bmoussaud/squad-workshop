"""Environment-backed application composition."""

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
from uuid import UUID

from fantasy_cards.adapters import (
    BlobArtifactStore,
    FoundryClientFactory,
    FoundryImageGenerator,
    InMemoryArtifactStore,
    InMemoryImageGenerator,
    InMemoryJobRepository,
    LocalPngImageGenerator,
    create_foundry_client,
    normalize_azure_openai_endpoint,
)
from fantasy_cards.application import GenerationService
from fantasy_cards.policy import (
    CONTENT_POLICY_ID,
    CONTENT_POLICY_VERSION,
    FOUNDRY_RAI_POLICY_NAME,
)
from fantasy_cards.ports import ArtifactReader, ArtifactStore


@dataclass(frozen=True, slots=True)
class LocalApplication:
    service: GenerationService
    artifact_store: InMemoryArtifactStore
    job_repository: InMemoryJobRepository


@dataclass(frozen=True, slots=True)
class WebApplication:
    service: GenerationService
    artifact_reader: ArtifactReader
    job_repository: InMemoryJobRepository


class ConfigurationError(ValueError):
    """A safe runtime configuration error."""


@dataclass(frozen=True, slots=True)
class ImageGeneratorSettings:
    mode: str = "in-memory"
    endpoint: str | None = None
    deployment: str | None = None
    managed_identity_client_id: str | None = None
    content_policy_id: str | None = None
    content_policy_version: str | None = None
    rai_policy_name: str | None = None
    bound_rai_policy_name: str | None = None
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
            managed_identity_client_id=values.get("AZURE_CLIENT_ID"),
            content_policy_id=values.get("FANTASY_CARD_CONTENT_POLICY_ID"),
            content_policy_version=values.get("FANTASY_CARD_CONTENT_POLICY_VERSION"),
            rai_policy_name=values.get("FANTASY_CARD_FOUNDRY_RAI_POLICY_NAME"),
            bound_rai_policy_name=values.get(
                "FANTASY_CARD_FOUNDRY_BOUND_RAI_POLICY_NAME"
            ),
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
        if self.mode == "foundry" and any(
            not value or not value.strip()
            for value in (
                self.endpoint,
                self.deployment,
                self.managed_identity_client_id,
                self.content_policy_id,
                self.content_policy_version,
                self.rai_policy_name,
                self.bound_rai_policy_name,
            )
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
            try:
                client_id = str(UUID(self.managed_identity_client_id or ""))
            except ValueError:
                raise ConfigurationError(
                    "Foundry runtime identity configuration is invalid."
                ) from None
            if client_id != self.managed_identity_client_id:
                raise ConfigurationError(
                    "Foundry runtime identity configuration is invalid."
                )
            if (
                self.content_policy_id != CONTENT_POLICY_ID
                or self.content_policy_version != CONTENT_POLICY_VERSION
                or self.rai_policy_name != FOUNDRY_RAI_POLICY_NAME
                or self.bound_rai_policy_name != FOUNDRY_RAI_POLICY_NAME
            ):
                raise ConfigurationError(
                    "Foundry content policy attestation does not match this runtime."
                )
        return self


@dataclass(frozen=True, slots=True)
class WebSettings:
    artifact_store: str = "filesystem"
    storage_account_url: str | None = None
    blob_container: str | None = None
    output_directory: str = "artifacts"
    max_generation_concurrency: int = 1
    rate_limit_attempts: int = 10
    rate_limit_window_seconds: int = 600

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "WebSettings":
        values = os.environ if environment is None else environment
        try:
            settings = cls(
                artifact_store=values.get(
                    "FANTASY_CARD_ARTIFACT_STORE", "filesystem"
                ),
                storage_account_url=values.get("AZURE_STORAGE_ACCOUNT_URL"),
                blob_container=values.get("FANTASY_CARD_BLOB_CONTAINER"),
                output_directory=values.get("FANTASY_CARD_OUTPUT_DIR", "artifacts"),
                max_generation_concurrency=int(
                    values.get("FANTASY_CARD_MAX_GENERATION_CONCURRENCY", "1")
                ),
                rate_limit_attempts=int(
                    values.get("FANTASY_CARD_RATE_LIMIT_ATTEMPTS", "10")
                ),
                rate_limit_window_seconds=int(
                    values.get("FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS", "600")
                ),
            )
        except ValueError:
            raise ConfigurationError("Web runtime limits must be integers.") from None
        return settings.validated()

    def validated(self) -> "WebSettings":
        if self.artifact_store not in ("filesystem", "blob"):
            raise ConfigurationError(
                "Artifact store must be 'filesystem' or 'blob'."
            )
        if self.artifact_store == "blob" and (
            not self.storage_account_url or not self.blob_container
        ):
            raise ConfigurationError("Blob artifact configuration is incomplete.")
        if self.max_generation_concurrency != 1:
            raise ConfigurationError("Generation concurrency must be exactly 1.")
        if not 1 <= self.rate_limit_attempts <= 100:
            raise ConfigurationError("Rate limit attempts must be between 1 and 100.")
        if not 1 <= self.rate_limit_window_seconds <= 3600:
            raise ConfigurationError(
                "Rate limit window must be between 1 and 3600 seconds."
            )
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
            managed_identity_client_id=settings.managed_identity_client_id or "",
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


def build_web_application(
    image_settings: ImageGeneratorSettings | None = None,
    web_settings: WebSettings | None = None,
    client_factory: FoundryClientFactory | None = None,
) -> WebApplication:
    image_settings = (
        image_settings or ImageGeneratorSettings.from_environment()
    ).validated()
    web_settings = (web_settings or WebSettings.from_environment()).validated()
    client_factory = client_factory or create_foundry_client

    artifact_store: ArtifactStore
    artifact_reader: ArtifactReader
    if web_settings.artifact_store == "blob":
        blob_store = BlobArtifactStore(
            web_settings.storage_account_url or "",
            web_settings.blob_container or "",
        )
        artifact_store = blob_store
        artifact_reader = blob_store
    else:
        filesystem_store = InMemoryArtifactStore(web_settings.output_directory)
        artifact_store = filesystem_store
        artifact_reader = filesystem_store

    if image_settings.mode == "foundry":
        image_generator = FoundryImageGenerator(
            endpoint=image_settings.endpoint or "",
            deployment=image_settings.deployment or "",
            timeout_seconds=image_settings.timeout_seconds,
            managed_identity_client_id=image_settings.managed_identity_client_id
            or "",
            client_factory=client_factory,
        )
    else:
        image_generator = LocalPngImageGenerator()

    job_repository = InMemoryJobRepository()
    return WebApplication(
        service=GenerationService(
            image_generator=image_generator,
            artifact_store=artifact_store,
            job_repository=job_repository,
        ),
        artifact_reader=artifact_reader,
        job_repository=job_repository,
    )
