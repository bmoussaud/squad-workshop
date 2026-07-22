"""In-memory adapters for local development and tests."""

from hashlib import sha256
from uuid import uuid4

from fantasy_cards.domain import Artifact, GeneratedImage, GenerationJob


class InMemoryImageGenerator:
    def generate(self, prompt: str) -> GeneratedImage:
        return GeneratedImage(
            content=f"generated image for: {prompt}".encode(),
            media_type="text/plain",
            generator_name="in-memory",
        )


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}

    def save(self, content: bytes, media_type: str) -> Artifact:
        artifact_id = str(uuid4())
        self._content[artifact_id] = content
        return Artifact(
            artifact_id=artifact_id,
            media_type=media_type,
            size_bytes=len(content),
        )

    def read(self, artifact_id: str) -> bytes:
        return self._content[artifact_id]


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}

    def get_by_idempotency_key(self, idempotency_key: str) -> GenerationJob | None:
        return self._jobs.get(idempotency_key)

    def save(self, job: GenerationJob) -> None:
        self._jobs[job.idempotency_key] = job


def deterministic_idempotency_key(title: str, prompt: str) -> str:
    return sha256(f"{title}\0{prompt}".encode()).hexdigest()
