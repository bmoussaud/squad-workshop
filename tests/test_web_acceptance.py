import os
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch
from uuid import UUID


MAX_REQUEST_BYTES = 16 * 1024


def assert_canonical_uuid(test_case: unittest.TestCase, value: str) -> None:
    test_case.assertEqual(str(UUID(value)), value)


class WebAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "in-memory",
            "FANTASY_CARD_ARTIFACT_STORE": "filesystem",
            "FANTASY_CARD_OUTPUT_DIR": self.output_directory.name,
            "FANTASY_CARD_MAX_GENERATION_CONCURRENCY": "1",
            "FANTASY_CARD_RATE_LIMIT_ATTEMPTS": "10",
            "FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS": "600",
        }

    def create_client(self):
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        return TestClient(create_app())

    def test_initial_html_has_semantic_labels_and_offline_health(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True), patch(
            "azure.identity.DefaultAzureCredential",
            side_effect=AssertionError("credential discovery is forbidden"),
        ):
            with self.create_client() as client:
                response = client.get("/")
                live = client.get("/health/live")
                ready = client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('<label for="title">Card name</label>', response.text)
        self.assertIn('<label for="description">Description</label>', response.text)
        self.assertIn('name="title"', response.text)
        self.assertIn('name="description"', response.text)
        self.assertIn('action="/generations"', response.text)
        self.assertIn('method="post"', response.text.lower())
        self.assertIn("aria-live", response.text)
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json(), {"status": "ready"})

    def test_invalid_configuration_is_not_ready_without_credential_discovery(self) -> None:
        invalid_environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "foundry",
            "FANTASY_CARD_ARTIFACT_STORE": "blob",
        }
        with patch.dict(os.environ, invalid_environment, clear=True), patch(
            "azure.identity.DefaultAzureCredential",
            side_effect=AssertionError("credential discovery is forbidden"),
        ) as credential_type:
            with self.create_client() as client:
                live = client.get("/health/live")
                ready = client.get("/health/ready")

        credential_type.assert_not_called()
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json(), {"status": "live"})
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(ready.json(), {"status": "not_ready"})
        self.assertNotIn("AZURE_", ready.text)
        self.assertNotIn("FANTASY_CARD_", ready.text)

    def test_json_generation_returns_exact_safe_dto_and_streamable_artifact(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with self.create_client() as client:
                response = client.post(
                    "/api/generations",
                    json={
                        "title": " Ember Sentinel ",
                        "description": " A knight made of living flame ",
                    },
                    headers={
                        "Idempotency-Key": "acceptance-json-success",
                        "X-Correlation-ID": "not-a-valid-uuid",
                    },
                )

                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertEqual(
                    set(payload),
                    {
                        "job_id",
                        "correlation_id",
                        "status",
                        "generator_name",
                        "artifact",
                    },
                )
                self.assertEqual(payload["status"], "succeeded")
                assert_canonical_uuid(self, payload["job_id"])
                assert_canonical_uuid(self, payload["correlation_id"])
                self.assertNotEqual(payload["correlation_id"], "not-a-valid-uuid")
                artifact = payload["artifact"]
                self.assertEqual(
                    set(artifact),
                    {"artifact_id", "media_type", "size_bytes", "url"},
                )
                assert_canonical_uuid(self, artifact["artifact_id"])
                self.assertEqual(artifact["media_type"], "image/png")
                self.assertGreater(artifact["size_bytes"], 0)
                self.assertEqual(
                    artifact["url"],
                    f"/api/artifacts/{artifact['artifact_id']}",
                )

                artifact_response = client.get(artifact["url"])

        self.assertEqual(artifact_response.status_code, 200)
        self.assertEqual(artifact_response.headers["content-type"], "image/png")
        self.assertEqual(
            artifact_response.headers["cache-control"], "private, max-age=3600"
        )
        self.assertEqual(
            artifact_response.headers["x-content-type-options"], "nosniff"
        )
        self.assertEqual(
            int(artifact_response.headers["content-length"]),
            len(artifact_response.content),
        )
        self.assertNotIn("file_path", response.text)
        self.assertNotIn("idempotency_key", response.text)
        self.assertNotIn("blob", response.text.lower())

    def test_non_javascript_form_fallback_renders_success(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with self.create_client() as client:
                response = client.post(
                    "/generations",
                    data={
                        "title": "Ember Sentinel",
                        "description": "A knight made of living flame",
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Ember Sentinel", response.text)
        self.assertIn("succeeded", response.text.lower())
        self.assertIn("<img", response.text)
        self.assertRegex(
            response.text,
            r'alt="[^"]*Ember Sentinel[^"]*"',
        )
        self.assertIn(">A knight made of living flame</textarea>", response.text)

    def test_exact_field_bounds_are_accepted_and_excess_is_rejected(self) -> None:
        accepted = (
            {"title": "x", "description": "y"},
            {"title": "x" * 80, "description": "y" * 1000},
        )
        rejected = (
            {"title": " ", "description": "valid"},
            {"title": "x" * 81, "description": "valid"},
            {"title": "valid", "description": " "},
            {"title": "valid", "description": "y" * 1001},
        )

        for index, payload in enumerate(accepted):
            with self.subTest(accepted=index), patch.dict(
                os.environ, self.environment, clear=True
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        json=payload,
                        headers={"Idempotency-Key": f"accepted-{index}"},
                    )
                self.assertEqual(response.status_code, 200, response.text)

        for index, payload in enumerate(rejected):
            with self.subTest(rejected=index), patch.dict(
                os.environ, self.environment, clear=True
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        json=payload,
                        headers={"Idempotency-Key": f"rejected-{index}"},
                    )
                self.assertEqual(response.status_code, 422, response.text)
                self.assert_error_envelope(response, "invalid_request")

    def test_idempotency_key_bounds_and_printable_ascii_are_exact(self) -> None:
        valid_keys = ("x", "x" * 128, "visible ASCII !~")
        invalid_keys = ("", "x" * 129, "line\nbreak")

        for index, key in enumerate(valid_keys):
            with self.subTest(valid=repr(key)), patch.dict(
                os.environ, self.environment, clear=True
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        json={"title": "Title", "description": "Description"},
                        headers={"Idempotency-Key": key},
                    )
                self.assertEqual(response.status_code, 200, response.text)

        for key in invalid_keys:
            with self.subTest(invalid=repr(key)), patch.dict(
                os.environ, self.environment, clear=True
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        json={"title": "Title", "description": "Description"},
                        headers={"Idempotency-Key": key},
                    )
                self.assertEqual(response.status_code, 422, response.text)
                self.assert_error_envelope(response, "invalid_request")

    def test_request_size_limit_and_content_type_precede_generation(self) -> None:
        cases = (
            (
                b"{" + b"x" * (MAX_REQUEST_BYTES - 1),
                "application/json",
                422,
                "invalid_request",
            ),
            (
                b"{" + b"x" * MAX_REQUEST_BYTES,
                "application/json",
                413,
                "request_too_large",
            ),
            (b"title=x", "text/plain", 415, "unsupported_media_type"),
        )

        for body, content_type, status, code in cases:
            with self.subTest(status=status, code=code), patch.dict(
                os.environ, self.environment, clear=True
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        content=body,
                        headers={"Content-Type": content_type},
                    )
                self.assertEqual(response.status_code, status, response.text)
                self.assert_error_envelope(response, code)
                self.assertEqual(list(Path(self.output_directory.name).iterdir()), [])

    def test_safe_dependency_errors_have_stable_codes_and_correlation_ids(self) -> None:
        from fantasy_cards.adapters import ImageGenerationError

        cases = (
            ("safety_rejected", "safety_rejected", 422),
            ("provider_unavailable", "provider_unavailable", 503),
            ("generation_failed", "generation_failed", 500),
        )
        private_detail = "private prompt and provider endpoint"

        for provider_code, public_code, status in cases:
            with self.subTest(code=provider_code), patch.dict(
                os.environ, self.environment, clear=True
            ), patch(
                "fantasy_cards.adapters.LocalPngImageGenerator.generate",
                side_effect=ImageGenerationError(provider_code, private_detail),
            ):
                with self.create_client() as client:
                    response = client.post(
                        "/api/generations",
                        json={"title": "Title", "description": private_detail},
                        headers={"X-Correlation-ID": "invalid-private-value"},
                    )
                self.assertEqual(response.status_code, status, response.text)
                self.assert_error_envelope(response, public_code)
                self.assertNotIn(private_detail, response.text)
                self.assertNotIn("invalid-private-value", response.text)

    def test_rate_limit_rejects_eleventh_attempt_without_generation(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with self.create_client() as client:
                for attempt in range(10):
                    response = client.post(
                        "/api/generations",
                        json={"title": f"Card {attempt}", "description": "Description"},
                        headers={"Idempotency-Key": f"rate-{attempt}"},
                    )
                    self.assertEqual(response.status_code, 200, response.text)

                rejected = client.post(
                    "/api/generations",
                    json={"title": "Card 11", "description": "Description"},
                    headers={"Idempotency-Key": "rate-11"},
                )

        self.assertEqual(rejected.status_code, 429, rejected.text)
        self.assert_error_envelope(rejected, "rate_limited")
        self.assertIn("retry-after", rejected.headers)

    def test_second_concurrent_generation_is_rejected_immediately(self) -> None:
        started = Event()
        release = Event()
        first_response: list[object] = []

        def blocking_generate(generator: object, prompt: str):
            from fantasy_cards.domain import GeneratedImage

            started.set()
            if not release.wait(timeout=5):
                raise AssertionError("test did not release blocked generation")
            return GeneratedImage(b"png", "image/png", "acceptance-fake")

        with patch.dict(os.environ, self.environment, clear=True), patch(
            "fantasy_cards.adapters.LocalPngImageGenerator.generate", blocking_generate
        ):
            with self.create_client() as client:
                thread = Thread(
                    target=lambda: first_response.append(
                        client.post(
                            "/api/generations",
                            json={"title": "First", "description": "Description"},
                            headers={"Idempotency-Key": "busy-first"},
                        )
                    )
                )
                thread.start()
                self.assertTrue(started.wait(timeout=2))
                second = client.post(
                    "/api/generations",
                    json={"title": "Second", "description": "Description"},
                    headers={"Idempotency-Key": "busy-second"},
                )
                release.set()
                thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(second.status_code, 429, second.text)
        self.assert_error_envelope(second, "busy")
        self.assertEqual(second.headers.get("retry-after"), "30")
        self.assertEqual(len(first_response), 1)

    def test_artifact_route_rejects_invalid_or_absent_ids_without_redirect(self) -> None:
        missing_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        with patch.dict(os.environ, self.environment, clear=True):
            with self.create_client() as client:
                invalid = client.get("/api/artifacts/not-a-uuid", follow_redirects=False)
                missing = client.get(
                    f"/api/artifacts/{missing_id}", follow_redirects=False
                )

        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn("location", invalid.headers)
        self.assertNotIn("location", missing.headers)

    def test_artifact_route_distinguishes_not_found_from_dependency_failures(self) -> None:
        from fantasy_cards.adapters import ArtifactStorageError
        from fastapi.testclient import TestClient

        artifact_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        private_detail = "storage account, credential chain, and provider response"
        cases = (
            ("artifact_not_found", 404),
            ("artifact_unavailable", 503),
        )

        for error_code, expected_status in cases:
            with self.subTest(error_code=error_code):
                reader = unittest.mock.Mock()
                reader.read.side_effect = ArtifactStorageError(
                    error_code, private_detail
                )
                application = SimpleNamespace(artifact_reader=reader)
                with patch.dict(os.environ, self.environment, clear=True), patch(
                    "azure.monitor.opentelemetry.configure_azure_monitor",
                    side_effect=AssertionError("telemetry must remain disabled"),
                ) as configure:
                    from fantasy_cards.web import create_app

                    with TestClient(create_app(application=application)) as client:
                        response = client.get(
                            f"/api/artifacts/{artifact_id}",
                            headers={"X-Correlation-ID": "invalid-internal-value"},
                            follow_redirects=False,
                        )

                self.assertEqual(response.status_code, expected_status, response.text)
                configure.assert_not_called()
                self.assert_error_envelope(response, "artifact_unavailable")
                self.assertNotIn(private_detail, response.text)
                self.assertNotIn("invalid-internal-value", response.text)
                self.assertNotIn("location", response.headers)
                reader.read.assert_called_once_with(artifact_id)

    def assert_error_envelope(self, response: object, expected_code: str) -> None:
        payload = response.json()
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(
            set(payload["error"]), {"code", "message", "correlation_id"}
        )
        self.assertEqual(payload["error"]["code"], expected_code)
        self.assertTrue(payload["error"]["message"])
        assert_canonical_uuid(self, payload["error"]["correlation_id"])


if __name__ == "__main__":
    unittest.main()