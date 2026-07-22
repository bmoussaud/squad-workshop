import unittest

from fantasy_cards.adapters import (
    InMemoryArtifactStore,
    InMemoryImageGenerator,
    InMemoryJobRepository,
)
from fantasy_cards.application import GenerationService
from fantasy_cards.domain import CardGenerationRequest, JobStatus


class GenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact_store = InMemoryArtifactStore()
        self.job_repository = InMemoryJobRepository()
        self.service = GenerationService(
            image_generator=InMemoryImageGenerator(),
            artifact_store=self.artifact_store,
            job_repository=self.job_repository,
        )

    def test_generates_and_persists_a_job_with_operation_ids(self) -> None:
        request = CardGenerationRequest(
            title="Ember Sentinel",
            prompt="A knight made of living flame",
            correlation_id="corr-123",
            idempotency_key="idem-123",
        )

        job = self.service.generate(request)

        self.assertEqual(job.status, JobStatus.SUCCEEDED)
        self.assertEqual(job.correlation_id, "corr-123")
        self.assertEqual(job.idempotency_key, "idem-123")
        self.assertEqual(job.generator_name, "in-memory")
        self.assertEqual(
            self.artifact_store.read(job.artifact.artifact_id),
            b"generated image for: A knight made of living flame",
        )
        self.assertIs(
            self.job_repository.get_by_idempotency_key("idem-123"), job
        )

    def test_reuses_the_existing_job_for_an_idempotency_key(self) -> None:
        first_request = CardGenerationRequest("A", "first", "corr-1", "same")
        second_request = CardGenerationRequest("B", "second", "corr-2", "same")

        first_job = self.service.generate(first_request)
        second_job = self.service.generate(second_request)

        self.assertIs(second_job, first_job)

    def test_rejects_blank_boundary_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt must not be blank"):
            CardGenerationRequest("Title", " ", "corr", "idem")


if __name__ == "__main__":
    unittest.main()