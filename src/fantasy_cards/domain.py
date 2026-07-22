"""Domain contracts for card generation."""

from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    SUCCEEDED = "succeeded"


@dataclass(frozen=True, slots=True)
class CardGenerationRequest:
    title: str
    prompt: str
    correlation_id: str
    idempotency_key: str

    def __post_init__(self) -> None:
        for field_name in ("title", "prompt", "correlation_id", "idempotency_key"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank")


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    content: bytes
    media_type: str
    generator_name: str


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class GenerationJob:
    job_id: str
    correlation_id: str
    idempotency_key: str
    status: JobStatus
    generator_name: str
    artifact: Artifact
