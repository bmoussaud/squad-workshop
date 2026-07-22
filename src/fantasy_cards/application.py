"""Application orchestration."""

from uuid import uuid4

from fantasy_cards.domain import CardGenerationRequest, GenerationJob, JobStatus
from fantasy_cards.ports import ArtifactStore, ImageGenerator, JobRepository


class GenerationService:
    def __init__(
        self,
        image_generator: ImageGenerator,
        artifact_store: ArtifactStore,
        job_repository: JobRepository,
    ) -> None:
        self._image_generator = image_generator
        self._artifact_store = artifact_store
        self._job_repository = job_repository

    def generate(self, request: CardGenerationRequest) -> GenerationJob:
        existing_job = self._job_repository.get_by_idempotency_key(
            request.idempotency_key
        )
        if existing_job is not None:
            return existing_job

        image = self._image_generator.generate(request.prompt)
        artifact = self._artifact_store.save(image.content, image.media_type)
        job = GenerationJob(
            job_id=str(uuid4()),
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
            status=JobStatus.SUCCEEDED,
            generator_name=image.generator_name,
            artifact=artifact,
        )
        self._job_repository.save(job)
        return job
