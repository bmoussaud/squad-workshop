"""Local application composition."""

from dataclasses import dataclass

from fantasy_cards.adapters import (
    InMemoryArtifactStore,
    InMemoryImageGenerator,
    InMemoryJobRepository,
)
from fantasy_cards.application import GenerationService


@dataclass(frozen=True, slots=True)
class LocalApplication:
    service: GenerationService
    artifact_store: InMemoryArtifactStore
    job_repository: InMemoryJobRepository


def build_local_application() -> LocalApplication:
    artifact_store = InMemoryArtifactStore()
    job_repository = InMemoryJobRepository()
    return LocalApplication(
        service=GenerationService(
            image_generator=InMemoryImageGenerator(),
            artifact_store=artifact_store,
            job_repository=job_repository,
        ),
        artifact_store=artifact_store,
        job_repository=job_repository,
    )
