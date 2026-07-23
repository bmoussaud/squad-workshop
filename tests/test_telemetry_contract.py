import importlib
from contextlib import contextmanager
import json
import logging
import os
import socket
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
from collections.abc import Iterator
import unittest
from unittest.mock import Mock, patch


class TelemetryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "in-memory",
            "FANTASY_CARD_ARTIFACT_STORE": "filesystem",
            "FANTASY_CARD_OUTPUT_DIR": self.output_directory.name,
        }

    def fake_telemetry_modules(
        self, configure: Mock, instrument: Mock, credential_factory: Mock
    ) -> dict[str, ModuleType]:
        identity = ModuleType("azure.identity")
        identity.ManagedIdentityCredential = credential_factory
        monitor = ModuleType("azure.monitor")
        opentelemetry = ModuleType("azure.monitor.opentelemetry")
        opentelemetry.configure_azure_monitor = configure
        monitor.opentelemetry = opentelemetry
        fastapi_instrumentation = ModuleType("opentelemetry.instrumentation.fastapi")
        fastapi_instrumentation.FastAPIInstrumentor = type(
            "FakeFastAPIInstrumentor",
            (),
            {"instrument_app": staticmethod(instrument)},
        )
        return {
            "azure.identity": identity,
            "azure.monitor": monitor,
            "azure.monitor.opentelemetry": opentelemetry,
            "opentelemetry.instrumentation.fastapi": fastapi_instrumentation,
        }

    @contextmanager
    def isolated_web_import(
        self,
        environment: dict[str, str],
        configure: Mock,
        instrument: Mock,
        credential_factory: Mock | None = None,
    ) -> Iterator[ModuleType]:
        credential_factory = credential_factory or Mock()
        modules = self.fake_telemetry_modules(
            configure, instrument, credential_factory
        )
        network_error = AssertionError("network access is forbidden in telemetry tests")
        with patch.dict(os.environ, environment, clear=True), patch.dict(
            sys.modules, modules
        ), patch.object(socket, "create_connection", side_effect=network_error), patch.object(
            socket.socket, "connect", side_effect=network_error
        ):
            sys.modules.pop("fantasy_cards.web", None)
            sys.modules.pop("fantasy_cards.telemetry", None)
            yield importlib.import_module("fantasy_cards.web")

    def test_import_without_connection_string_is_a_telemetry_noop(self) -> None:
        configure = Mock(side_effect=AssertionError("telemetry must remain disabled"))
        instrument = Mock(side_effect=AssertionError("instrumentation must remain disabled"))
        with self.isolated_web_import(self.environment, configure, instrument) as module:
            second_app = module.create_app()

        self.assertIsNotNone(module.app)
        self.assertIsNotNone(second_app)
        configure.assert_not_called()
        instrument.assert_not_called()

    def test_connection_string_initializes_azure_monitor_once_with_test_double(self) -> None:
        from fastapi.testclient import TestClient

        configure = Mock()
        instrument = Mock()
        credential = object()
        credential_factory = Mock(return_value=credential)
        client_id = "11111111-2222-4333-8444-555555555555"
        connection_string = (
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://private-monitor.example.invalid/"
        )
        with self.isolated_web_import(
            {
                **self.environment,
                "APPLICATIONINSIGHTS_CONNECTION_STRING": connection_string,
                "AZURE_CLIENT_ID": client_id,
            },
            configure,
            instrument,
            credential_factory,
        ) as module:
            second_app = module.create_app()
            credential_factory.assert_not_called()
            configure.assert_not_called()
            instrument.assert_not_called()
            with TestClient(module.app), TestClient(second_app):
                pass

        credential_factory.assert_called_once_with(client_id=client_id)
        configure.assert_called_once()
        self.assertIs(configure.call_args.kwargs["credential"], credential)
        self.assertEqual(instrument.call_count, 2)
        self.assertTrue(module.app.state.telemetry_instrumented)
        self.assertTrue(second_app.state.telemetry_instrumented)

    def test_connection_string_without_client_id_does_not_use_local_auth(self) -> None:
        configure = Mock(side_effect=AssertionError("local auth fallback is forbidden"))
        instrument = Mock(side_effect=AssertionError("instrumentation must remain disabled"))
        credential_factory = Mock(
            side_effect=AssertionError("an incomplete identity must not be constructed")
        )
        with self.isolated_web_import(
            {
                **self.environment,
                "APPLICATIONINSIGHTS_CONNECTION_STRING": (
                    "InstrumentationKey=00000000-0000-0000-0000-000000000000"
                ),
            },
            configure,
            instrument,
            credential_factory,
        ) as module:
            second_app = module.create_app()

        self.assertIsNotNone(module.app)
        self.assertIsNotNone(second_app)
        credential_factory.assert_not_called()
        configure.assert_not_called()
        instrument.assert_not_called()

    def test_generation_events_are_queryable_correlatable_and_payload_safe(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.adapters import ImageGenerationError

        correlation_id = "11111111-1111-4111-8111-111111111111"
        private_title = "Private card title"
        private_prompt = "Private prompt with bearer token and account endpoint"
        private_bytes = "89504e470d0a1a0a-private-image-bytes"
        configure = Mock(side_effect=AssertionError("telemetry must remain disabled"))
        instrument = Mock(side_effect=AssertionError("instrumentation must remain disabled"))
        with self.isolated_web_import(
            self.environment, configure, instrument
        ) as module, patch(
            "fantasy_cards.adapters.LocalPngImageGenerator.generate",
            side_effect=ImageGenerationError("provider_timeout", private_bytes),
        ), self.assertLogs("fantasy_cards.web", level=logging.INFO) as captured:
            with TestClient(module.create_app()) as client:
                response = client.post(
                    "/api/generations",
                    json={"title": private_title, "description": private_prompt},
                    headers={"X-Correlation-ID": correlation_id},
                )

        configure.assert_not_called()
        instrument.assert_not_called()

        self.assertEqual(response.status_code, 504, response.text)
        events = [json.loads(record.split(":", 2)[-1]) for record in captured.output]
        matching = [event for event in events if event.get("error_code") == "provider_timeout"]
        self.assertEqual(len(matching), 1, events)
        event = matching[0]
        self.assertEqual(event["correlation_id"], correlation_id)
        self.assertEqual(event["dependency"], "provider")
        self.assertFalse(event["success"])
        self.assertIn("duration_ms", event)
        serialized = json.dumps(events)
        for private_value in (private_title, private_prompt, private_bytes):
            self.assertNotIn(private_value, serialized)

    def test_blob_read_failure_emits_alert_compatible_safe_event(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.adapters import ArtifactStorageError

        artifact_id = "22222222-2222-4222-8222-222222222222"
        private_detail = "credential chain and storage response body"
        reader = Mock()
        reader.read.side_effect = ArtifactStorageError(
            "artifact_unavailable", private_detail
        )
        application = Mock(artifact_reader=reader)

        configure = Mock(side_effect=AssertionError("telemetry must remain disabled"))
        instrument = Mock(side_effect=AssertionError("instrumentation must remain disabled"))
        with self.isolated_web_import(
            self.environment, configure, instrument
        ) as module, self.assertLogs("fantasy_cards.web", level=logging.INFO) as captured:
            with TestClient(module.create_app(application=application)) as client:
                response = client.get(f"/api/artifacts/{artifact_id}")

        configure.assert_not_called()
        instrument.assert_not_called()
        self.assertEqual(response.status_code, 503, response.text)
        events = [json.loads(record.split(":", 2)[-1]) for record in captured.output]
        matching = [event for event in events if event.get("dependency") == "blob"]
        self.assertEqual(len(matching), 1, events)
        self.assertFalse(matching[0]["success"])
        self.assertEqual(matching[0]["error_code"], "artifact_unavailable")
        self.assertNotIn(private_detail, json.dumps(events))


if __name__ == "__main__":
    unittest.main()