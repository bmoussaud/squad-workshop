"""Provider-neutral application ports."""

from typing import Protocol

from fantasy_cards.domain import Artifact, GeneratedImage, GenerationJob


class ImageGenerator(Protocol):
    def generate(self, prompt: str) -> GeneratedImage: ...


class ArtifactStore(Protocol):
    def save(self, content: bytes, media_type: str) -> Artifact: ...


class JobRepository(Protocol):
    def get_by_idempotency_key(self, idempotency_key: str) -> GenerationJob | None: ...

    def save(self, job: GenerationJob) -> None: ...
