"""Privacy-safe OpenTelemetry integration for Azure Monitor."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import logging
import os
from threading import Lock
from typing import Any
from uuid import UUID

_LOGGER = logging.getLogger("fantasy_cards.telemetry")
_CONFIGURATION_LOCK = Lock()
_CONFIGURED_WITH: Any | None = None
_REJECTED_AZURE_CLIENT_IDS = {
    "00000000-0000-0000-0000-000000000000",
    "00000000-0000-4000-8000-000000000000",
}


def configure_telemetry(application: Any) -> bool:
    """Register lazy Azure Monitor configuration for one FastAPI application."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        _LOGGER.info(
            '{"event":"telemetry_configuration_selected","outcome":"disabled"}'
        )
        return False
    client_id = _validated_client_id(
        os.getenv("AZURE_CLIENT_ID"), required=True, context="telemetry"
    )

    application.router.add_event_handler(
        "startup",
        lambda: _activate_telemetry(application, connection_string, client_id),
    )
    _LOGGER.info(
        '{"event":"telemetry_configuration_selected","outcome":"enabled"}'
    )
    return True


def _activate_telemetry(
    application: Any, connection_string: str, client_id: str
) -> None:
    try:
        from azure.identity import ManagedIdentityCredential
        from azure.monitor.opentelemetry import configure_azure_monitor

        global _CONFIGURED_WITH
        with _CONFIGURATION_LOCK:
            if _CONFIGURED_WITH is not configure_azure_monitor:
                credential = ManagedIdentityCredential(client_id=client_id)
                configure_azure_monitor(
                    browser_sdk_loader_config={"enabled": False},
                    connection_string=connection_string,
                    credential=credential,
                    enable_live_metrics=False,
                    enable_performance_counters=False,
                    instrumentation_options={
                        "azure_sdk": {"enabled": False},
                        "fastapi": {"enabled": False},
                        "requests": {"enabled": False},
                        "urllib": {"enabled": False},
                        "urllib3": {"enabled": False},
                    },
                    logger_name="fantasy_cards",
                )
                _CONFIGURED_WITH = configure_azure_monitor

        if not getattr(application.state, "telemetry_instrumented", False):
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(application)
            application.state.telemetry_instrumented = True
    except Exception:
        _LOGGER.warning(
            '{"event":"telemetry_configuration_failed","outcome":"disabled"}'
        )


def _validated_client_id(
    raw_client_id: str | None, *, required: bool, context: str
) -> str:
    client_id = (raw_client_id or "").strip()
    if not client_id:
        if required:
            raise ValueError(f"AZURE_CLIENT_ID is required for {context}.")
        return ""
    try:
        normalized = str(UUID(client_id))
    except ValueError:
        raise ValueError("AZURE_CLIENT_ID must be a valid GUID.") from None
    if normalized in _REJECTED_AZURE_CLIENT_IDS:
        raise ValueError("AZURE_CLIENT_ID contains a reserved GUID value.")
    return normalized


@contextmanager
def dependency_span(dependency: str, operation: str) -> Iterator[Any]:
    """Create a dependency span without recording exception details."""
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind

    tracer = trace.get_tracer("fantasy_cards")
    with tracer.start_as_current_span(
        f"fantasy_cards.{dependency}.{operation}",
        kind=SpanKind.CLIENT,
        record_exception=False,
        set_status_on_exception=False,
        attributes={
            "fantasy_cards.dependency": dependency,
            "fantasy_cards.operation": operation,
        },
    ) as span:
        yield span


def record_span_outcome(
    span: Any,
    outcome: str,
    *,
    error_code: str | None = None,
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> None:
    from opentelemetry.trace import Status, StatusCode

    span.set_attribute("fantasy_cards.outcome", outcome)
    if error_code is not None:
        span.set_attribute("fantasy_cards.error_code", error_code)
    if attributes:
        for name, value in attributes.items():
            span.set_attribute(name, value)
    span.set_status(Status(StatusCode.OK if outcome == "succeeded" else StatusCode.ERROR))


def record_generation_outcome(
    correlation_id: str,
    outcome: str,
    duration_seconds: float,
    size_bytes: int | None = None,
) -> None:
    from opentelemetry import trace

    attributes: dict[str, str | int | float] = {
        "fantasy_cards.correlation_id": correlation_id,
        "fantasy_cards.outcome": outcome,
        "fantasy_cards.duration_ms": round(duration_seconds * 1000, 2),
    }
    if size_bytes is not None:
        attributes["fantasy_cards.artifact_size_bytes"] = size_bytes
    trace.get_current_span().add_event(
        "fantasy_cards.generation.completed", attributes=attributes
    )


def set_request_correlation_id(correlation_id: str) -> None:
    from opentelemetry import trace

    trace.get_current_span().set_attribute(
        "fantasy_cards.correlation_id", correlation_id
    )