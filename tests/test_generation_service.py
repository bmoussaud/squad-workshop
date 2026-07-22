from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest
from unittest.mock import patch

from fantasy_cards.adapters import (
    InMemoryArtifactStore,
    InMemoryImageGenerator,
    InMemoryJobRepository,
)
from fantasy_cards.application import GenerationService
from fantasy_cards.domain import CardGenerationRequest, JobStatus


class GenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.artifact_store = InMemoryArtifactStore(self.output_directory.name)
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
        artifact_path = Path(job.artifact.file_path)
        self.assertEqual(artifact_path.parent, Path(self.output_directory.name))
        self.assertEqual(artifact_path.suffix, ".txt")
        self.assertIn(job.artifact.artifact_id, artifact_path.name)
        self.assertEqual(
            artifact_path.read_bytes(),
            b"generated image for: A knight made of living flame",
        )
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

    def test_uses_allowlisted_media_type_extensions(self) -> None:
        cases = (
            ("image/png", ".png"),
            ("text/plain", ".txt"),
            ("image/png/../../unsafe", ".bin"),
        )

        for media_type, expected_extension in cases:
            with self.subTest(media_type=media_type):
                artifact = self.artifact_store.save(b"content", media_type)
                artifact_path = Path(artifact.file_path)

                self.assertEqual(artifact_path.suffix, expected_extension)
                self.assertEqual(artifact_path.parent, Path(self.output_directory.name))
                self.assertIn(artifact.artifact_id, artifact_path.name)

    def test_uuid_collision_preserves_original_disk_and_memory_content(self) -> None:
        with patch("fantasy_cards.adapters.uuid4", return_value="fixed-id"):
            artifact = self.artifact_store.save(b"original", "text/plain")

            for replacement in (b"replacement-one", b"replacement-two"):
                with self.subTest(replacement=replacement):
                    with self.assertRaises(FileExistsError):
                        self.artifact_store.save(replacement, "text/plain")

                    self.assertEqual(Path(artifact.file_path).read_bytes(), b"original")
                    self.assertEqual(self.artifact_store.read("fixed-id"), b"original")
                    self.assertEqual(
                        list(Path(self.output_directory.name).iterdir()),
                        [Path(artifact.file_path)],
                    )

    def test_partial_write_failure_leaves_no_artifact_or_temp_file(self) -> None:
        class PartialWriteFile:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self._file = NamedTemporaryFile(*args, **kwargs)
                self.name = self._file.name

            def __enter__(self) -> "PartialWriteFile":
                self._file.__enter__()
                return self

            def __exit__(self, *args: object) -> None:
                self._file.__exit__(*args)

            def write(self, content: bytes) -> None:
                self._file.write(content[:3])
                raise OSError("partial write")

        with patch(
            "fantasy_cards.adapters.NamedTemporaryFile", PartialWriteFile
        ), patch("fantasy_cards.adapters.uuid4", return_value="partial-id"):
            with self.assertRaisesRegex(OSError, "partial write"):
                self.artifact_store.save(b"content", "text/plain")

        self.assertEqual(list(Path(self.output_directory.name).iterdir()), [])
        with self.assertRaises(KeyError):
            self.artifact_store.read("partial-id")

    def test_publication_failure_leaves_no_artifact_or_temp_file(self) -> None:
        with patch("fantasy_cards.adapters.os.link", side_effect=OSError("disk")), patch(
            "fantasy_cards.adapters.uuid4", return_value="publish-id"
        ):
            with self.assertRaises(OSError):
                self.artifact_store.save(b"content", "text/plain")

        self.assertEqual(list(Path(self.output_directory.name).iterdir()), [])
        with self.assertRaises(KeyError):
            self.artifact_store.read("publish-id")

    def test_successful_persistence_publishes_final_file_without_temp_residue(
        self,
    ) -> None:
        with patch("fantasy_cards.adapters.uuid4", return_value="success-id"):
            artifact = self.artifact_store.save(b"content", "text/plain")

        self.assertEqual(Path(artifact.file_path).read_bytes(), b"content")
        self.assertEqual(self.artifact_store.read("success-id"), b"content")
        self.assertEqual(
            list(Path(self.output_directory.name).iterdir()),
            [Path(self.output_directory.name) / "success-id.txt"],
        )

    def test_rejects_blank_boundary_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt must not be blank"):
            CardGenerationRequest("Title", " ", "corr", "idem")


if __name__ == "__main__":
    unittest.main()