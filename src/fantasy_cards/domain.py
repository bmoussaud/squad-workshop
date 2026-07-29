"""Domain contracts for card generation."""

from dataclasses import dataclass
from enum import StrEnum
import re


_OWNER_SUBJECT_PATTERN = re.compile(r"[A-Za-z0-9._~-]{1,255}")


def is_valid_owner_subject(value: object) -> bool:
    return isinstance(value, str) and _OWNER_SUBJECT_PATTERN.fullmatch(value) is not None


class JobStatus(StrEnum):
    SUCCEEDED = "succeeded"


@dataclass(frozen=True, slots=True)
class CardGenerationRequest:
    title: str
    prompt: str
    correlation_id: str
    idempotency_key: str
    owner_subject: str

    def __post_init__(self) -> None:
        for field_name in (
            "title",
            "prompt",
            "correlation_id",
            "idempotency_key",
            "owner_subject",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank")
        if not is_valid_owner_subject(self.owner_subject):
            raise ValueError("owner_subject is invalid")


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
    file_path: str
    owner_subject: str


@dataclass(frozen=True, slots=True, eq=False)
class ArtifactContent:
    content: bytes
    media_type: str
    size_bytes: int

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bytes):
            return self.content == other
        if not isinstance(other, ArtifactContent):
            return NotImplemented
        return (
            self.content == other.content
            and self.media_type == other.media_type
            and self.size_bytes == other.size_bytes
        )


@dataclass(frozen=True, slots=True)
class GenerationJob:
    job_id: str
    correlation_id: str
    idempotency_key: str
    status: JobStatus
    generator_name: str
    artifact: Artifact
