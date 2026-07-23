"""FastAPI inbound adapter for fantasy card generation."""

from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from anyio import to_thread
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fantasy_cards.adapters import (
    ArtifactNotFoundError,
    ArtifactStorageError,
    ImageGenerationError,
    deterministic_idempotency_key,
)
from fantasy_cards.config import (
    ConfigurationError,
    ImageGeneratorSettings,
    WebApplication,
    WebSettings,
    build_web_application,
)
from fantasy_cards.domain import CardGenerationRequest, GenerationJob
from fantasy_cards.telemetry import (
    configure_telemetry,
    record_generation_outcome,
    set_request_correlation_id,
)

_PACKAGE_DIRECTORY = Path(__file__).parent
_LOGGER = logging.getLogger("fantasy_cards.web")
_LOGGER.setLevel(logging.INFO)
_MAX_BODY_BYTES = 16 * 1024
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self'; style-src 'self'; "
        "script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


class RequestBoundaryMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        correlation_id = _correlation_id(headers.get(b"x-correlation-id"))
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        set_request_correlation_id(correlation_id)
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_BODY_BYTES:
                    await _send_too_large(scope, send, correlation_id)
                    return
            except ValueError:
                await _send_too_large(scope, send, correlation_id)
                return

        received = 0

        async def bounded_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > _MAX_BODY_BYTES:
                    raise RequestTooLarge
            return message

        response_started = False

        async def secured_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                response_headers = list(message.get("headers", []))
                response_headers.extend(
                    (name.encode(), value.encode())
                    for name, value in _SECURITY_HEADERS.items()
                )
                response_headers.append((b"x-correlation-id", correlation_id.encode()))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, bounded_receive, secured_send)
        except RequestTooLarge:
            if not response_started:
                await _send_too_large(scope, send, correlation_id)


class RequestTooLarge(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GenerationInput:
    title: str
    description: str
    idempotency_key: str


class RollingRateLimiter:
    def __init__(self, attempts: int, window_seconds: int) -> None:
        self._attempts = attempts
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def admit(self) -> bool:
        now = monotonic()
        with self._lock:
            while self._timestamps and self._timestamps[0] <= now - self._window_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._attempts:
                return False
            self._timestamps.append(now)
            return True


class WebRuntime:
    def __init__(
        self,
        application: WebApplication | None,
        settings: WebSettings | None,
        configuration_error: bool,
    ) -> None:
        self.application = application
        self.settings = settings
        self.configuration_error = configuration_error
        self.generation_slot = BoundedSemaphore(1)
        self.rate_limiter = RollingRateLimiter(
            settings.rate_limit_attempts if settings else 10,
            settings.rate_limit_window_seconds if settings else 600,
        )


def create_app(
    application: WebApplication | None = None,
    image_settings: ImageGeneratorSettings | None = None,
    web_settings: WebSettings | None = None,
) -> FastAPI:
    configuration_error = False
    try:
        resolved_web_settings = (web_settings or WebSettings.from_environment()).validated()
        resolved_application = application or build_web_application(
            image_settings=image_settings,
            web_settings=resolved_web_settings,
        )
    except (ConfigurationError, ValueError):
        resolved_web_settings = None
        resolved_application = None
        configuration_error = True

    runtime = WebRuntime(
        resolved_application, resolved_web_settings, configuration_error
    )
    templates = Environment(
        loader=FileSystemLoader(_PACKAGE_DIRECTORY / "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )
    application_host = FastAPI(
        title="Fantasy Card Generator",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application_host.state.runtime = runtime
    application_host.state.templates = templates
    application_host.add_middleware(RequestBoundaryMiddleware)
    application_host.mount(
        "/static",
        StaticFiles(directory=_PACKAGE_DIRECTORY / "static"),
        name="static",
    )

    @application_host.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return _render(request, title="", description="", result=None, error=None)

    @application_host.post("/generations", response_class=HTMLResponse)
    async def form_generation(request: Request) -> HTMLResponse:
        correlation_id = request.state.correlation_id
        if not _matches_content_type(request, "application/x-www-form-urlencoded"):
            return _render(
                request,
                title="",
                description="",
                result=None,
                error=_message("unsupported_media_type"),
                status_code=415,
            )
        try:
            fields = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
            payload: Mapping[str, Any] = {
                "title": _single_field(fields, "title"),
                "description": _single_field(fields, "description"),
            }
            generation_input = _validated_input(payload, None)
            job = await _generate(runtime, generation_input, correlation_id)
        except UnicodeDecodeError:
            return _render_error(request, "invalid_request", 422)
        except WebError as error:
            return _render_error(
                request,
                error.code,
                error.status_code,
                title=locals().get("payload", {}).get("title", ""),
                description=locals().get("payload", {}).get("description", ""),
                retry_after=error.retry_after,
            )
        return _render(
            request,
            title=generation_input.title,
            description=generation_input.description,
            result={
                "title": generation_input.title,
                "status": job.status.value,
                "artifact_url": f"/api/artifacts/{job.artifact.artifact_id}",
            },
            error=None,
        )

    @application_host.post("/api/generations")
    async def api_generation(request: Request) -> JSONResponse:
        correlation_id = request.state.correlation_id
        if not _matches_content_type(request, "application/json"):
            return _json_error("unsupported_media_type", correlation_id, 415)
        try:
            payload = json.loads(await request.body())
            generation_input = _validated_input(
                payload, request.headers.get("Idempotency-Key")
            )
            job = await _generate(runtime, generation_input, correlation_id)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json_error("invalid_request", correlation_id, 422)
        except WebError as error:
            return _json_error(
                error.code,
                correlation_id,
                error.status_code,
                retry_after=error.retry_after,
            )
        return JSONResponse(_job_dto(job, correlation_id), status_code=200)

    @application_host.get("/api/artifacts/{artifact_id}")
    async def artifact(artifact_id: str, request: Request) -> Response:
        if not _canonical_uuid(artifact_id) or runtime.application is None:
            return _json_error("artifact_unavailable", request.state.correlation_id, 404)
        try:
            artifact_content = await to_thread.run_sync(
                runtime.application.artifact_reader.read, artifact_id
            )
        except (ArtifactNotFoundError, KeyError):
            return _json_error("artifact_unavailable", request.state.correlation_id, 404)
        except ArtifactStorageError as error:
            status_code = 404 if error.code == "artifact_not_found" else 503
            if status_code == 503:
                _log_dependency_failure(
                    request.state.correlation_id,
                    "blob",
                    "read",
                    error.code,
                )
            return _json_error(
                "artifact_unavailable", request.state.correlation_id, status_code
            )
        return Response(
            artifact_content.content,
            media_type="image/png",
            headers={
                "Content-Length": str(artifact_content.size_bytes),
                "Cache-Control": "private, max-age=3600",
            },
        )

    @application_host.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "live"}

    @application_host.get("/health/ready")
    async def readiness() -> JSONResponse:
        if runtime.configuration_error or runtime.application is None:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ready"}, status_code=200)

    configure_telemetry(application_host)
    return application_host


class WebError(Exception):
    def __init__(self, code: str, status_code: int, retry_after: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after


async def _generate(
    runtime: WebRuntime, generation_input: GenerationInput, correlation_id: str
) -> GenerationJob:
    if runtime.configuration_error or runtime.application is None:
        raise WebError("configuration_error", 503)
    if not runtime.generation_slot.acquire(blocking=False):
        _log_outcome(correlation_id, "busy", 0.0)
        raise WebError("busy", 429, 30)
    started_at = monotonic()
    try:
        if not runtime.rate_limiter.admit():
            _log_outcome(correlation_id, "rate_limited", monotonic() - started_at)
            raise WebError("rate_limited", 429, 60)
        request = CardGenerationRequest(
            title=generation_input.title,
            prompt=generation_input.description,
            correlation_id=correlation_id,
            idempotency_key=generation_input.idempotency_key,
        )
        job = await to_thread.run_sync(runtime.application.service.generate, request)
        _log_outcome(
            correlation_id,
            "succeeded",
            monotonic() - started_at,
            job.artifact.size_bytes,
        )
        return job
    except ImageGenerationError as error:
        _log_outcome(correlation_id, error.code, monotonic() - started_at)
        raise _image_error(error.code) from None
    except ArtifactStorageError:
        _log_outcome(correlation_id, "artifact_unavailable", monotonic() - started_at)
        raise WebError("artifact_unavailable", 503) from None
    except WebError:
        raise
    except Exception:
        _log_outcome(correlation_id, "generation_failed", monotonic() - started_at)
        raise WebError("generation_failed", 500) from None
    finally:
        runtime.generation_slot.release()


def _validated_input(payload: Any, idempotency_key: str | None) -> GenerationInput:
    if not isinstance(payload, dict) or set(payload) != {"title", "description"}:
        raise WebError("invalid_request", 422)
    title = payload["title"]
    description = payload["description"]
    if not isinstance(title, str) or not isinstance(description, str):
        raise WebError("invalid_request", 422)
    title = title.strip()
    description = description.strip()
    if not 1 <= len(title) <= 80 or not 1 <= len(description) <= 1000:
        raise WebError("invalid_request", 422)
    if idempotency_key is not None and (
        not 1 <= len(idempotency_key) <= 128
        or any(ord(character) < 32 or ord(character) > 126 for character in idempotency_key)
    ):
        raise WebError("invalid_request", 422)
    return GenerationInput(
        title,
        description,
        idempotency_key or deterministic_idempotency_key(title, description),
    )


def _single_field(fields: Mapping[str, list[str]], name: str) -> str:
    values = fields.get(name, [])
    if len(values) != 1:
        raise WebError("invalid_request", 422)
    return values[0]


def _job_dto(job: GenerationJob, correlation_id: str) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "correlation_id": correlation_id,
        "status": "succeeded",
        "generator_name": job.generator_name,
        "artifact": {
            "artifact_id": job.artifact.artifact_id,
            "media_type": "image/png",
            "size_bytes": job.artifact.size_bytes,
            "url": f"/api/artifacts/{job.artifact.artifact_id}",
        },
    }


def _image_error(code: str) -> WebError:
    mapping = {
        "safety_rejected": ("safety_rejected", 422),
        "provider_timeout": ("provider_timeout", 504),
        "provider_unavailable": ("provider_unavailable", 503),
        "authentication_failed": ("provider_unavailable", 503),
        "throttled": ("provider_unavailable", 503),
    }
    error_code, status_code = mapping.get(code, ("generation_failed", 500))
    return WebError(error_code, status_code)


def _json_error(
    code: str,
    correlation_id: str,
    status_code: int,
    retry_after: int | None = None,
) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": _message(code),
                "correlation_id": correlation_id,
            }
        },
        status_code=status_code,
        headers=headers,
    )


def _render_error(
    request: Request,
    code: str,
    status_code: int,
    title: str = "",
    description: str = "",
    retry_after: int | None = None,
) -> HTMLResponse:
    response = _render(
        request,
        title=title if isinstance(title, str) else "",
        description=description if isinstance(description, str) else "",
        result=None,
        error=_message(code),
        status_code=status_code,
    )
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _render(
    request: Request,
    title: str,
    description: str,
    result: dict[str, str] | None,
    error: str | None,
    status_code: int = 200,
) -> HTMLResponse:
    template = request.app.state.templates.get_template("index.html")
    return HTMLResponse(
        template.render(
            title=title,
            description=description,
            result=result,
            error=error,
        ),
        status_code=status_code,
    )


def _message(code: str) -> str:
    return {
        "invalid_request": "Check the card name and description, then try again.",
        "unsupported_media_type": "This request format is not supported.",
        "request_too_large": "The request is too large.",
        "rate_limited": "Too many generation attempts. Please try again later.",
        "busy": "A card is already being generated. Please try again shortly.",
        "safety_rejected": "This description could not be generated. Revise it and try again.",
        "provider_timeout": "Card generation took too long. Please try again.",
        "provider_unavailable": "Card generation is temporarily unavailable.",
        "artifact_unavailable": "The requested card image is unavailable.",
        "configuration_error": "Card generation is not configured.",
        "generation_failed": "The card could not be generated.",
    }.get(code, "The request could not be completed.")


def _log_outcome(
    correlation_id: str,
    outcome: str,
    duration_seconds: float,
    size_bytes: int | None = None,
) -> None:
    event: dict[str, str | int | float | bool] = {
        "event": "generation_completed",
        "correlation_id": correlation_id,
        "outcome": outcome,
        "success": outcome == "succeeded",
        "duration_ms": round(duration_seconds * 1000, 2),
    }
    if outcome in {
        "authentication_failed",
        "generation_failed",
        "invalid_response",
        "provider_timeout",
        "provider_unavailable",
        "safety_rejected",
        "throttled",
    }:
        event["dependency"] = "provider"
        event["error_code"] = outcome
    elif outcome == "artifact_unavailable":
        event["dependency"] = "blob"
        event["error_code"] = outcome
    elif outcome != "succeeded":
        event["error_code"] = outcome
    if size_bytes is not None:
        event["size_bytes"] = size_bytes
    _emit_structured_event(event)
    record_generation_outcome(
        correlation_id, outcome, duration_seconds, size_bytes=size_bytes
    )


def _log_dependency_failure(
    correlation_id: str,
    dependency: str,
    operation: str,
    error_code: str,
) -> None:
    _emit_structured_event(
        {
            "event": "dependency_completed",
            "correlation_id": correlation_id,
            "dependency": dependency,
            "operation": operation,
            "success": False,
            "error_code": error_code,
        }
    )


def _emit_structured_event(event: dict[str, str | int | float | bool]) -> None:
    custom_dimensions = {
        name: event[name]
        for name in (
            "correlation_id",
            "dependency",
            "duration_ms",
            "error_code",
            "operation",
            "outcome",
            "size_bytes",
            "success",
        )
        if name in event
    }
    _LOGGER.info(
        json.dumps(event, separators=(",", ":")),
        extra=custom_dimensions,
    )


def _matches_content_type(request: Request, expected: str) -> bool:
    return request.headers.get("content-type", "").split(";", 1)[0].strip().lower() == expected


def _canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _correlation_id(raw_value: bytes | None) -> str:
    if raw_value is not None:
        try:
            value = raw_value.decode("ascii")
            if _canonical_uuid(value):
                return value
        except UnicodeDecodeError:
            pass
    return str(uuid4())


async def _send_too_large(
    scope: dict[str, Any], send: Callable[[dict[str, Any]], Awaitable[None]], correlation_id: str
) -> None:
    if scope.get("path", "").startswith("/api/"):
        content = json.dumps(
            {
                "error": {
                    "code": "request_too_large",
                    "message": _message("request_too_large"),
                    "correlation_id": correlation_id,
                }
            }
        ).encode()
        content_type = b"application/json"
    else:
        content = b"Request too large"
        content_type = b"text/plain; charset=utf-8"
    headers = [
        (b"content-type", content_type),
        (b"content-length", str(len(content)).encode()),
        (b"x-correlation-id", correlation_id.encode()),
    ]
    headers.extend(
        (name.encode(), value.encode()) for name, value in _SECURITY_HEADERS.items()
    )
    await send({"type": "http.response.start", "status": 413, "headers": headers})
    await send({"type": "http.response.body", "body": content})


app = create_app()