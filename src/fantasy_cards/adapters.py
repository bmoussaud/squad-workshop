"""Image generation and in-memory persistence adapters."""

from base64 import b64decode
from binascii import Error as Base64Error
from collections.abc import Callable
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4
import warnings

from PIL import Image, UnidentifiedImageError

from fantasy_cards.domain import Artifact, ArtifactContent, GeneratedImage, GenerationJob
from fantasy_cards.telemetry import dependency_span, record_span_outcome


class InMemoryImageGenerator:
    def generate(self, prompt: str) -> GeneratedImage:
        return GeneratedImage(
            content=f"generated image for: {prompt}".encode(),
            media_type="text/plain",
            generator_name="in-memory",
        )


class ImageGenerationError(RuntimeError):
    """A safe, provider-neutral image generation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _ImagesClient(Protocol):
    images: Any


FoundryClientFactory = Callable[[str, float], _ImagesClient]

_AZURE_OPENAI_RESOURCE_HOST = re.compile(
    r"^(?P<resource>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.openai\.azure\.com$"
)
_FOUNDRY_SERVICES_HOST = re.compile(
    r"^(?P<resource>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.services\.ai\.azure\.com$"
)
_MAX_PNG_BYTES = 25 * 1024 * 1024
_MAX_PNG_PIXELS = 16_777_216
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IEND = b"IEND"
_ARTIFACT_EXTENSIONS = {
    "image/png": ".png",
    "text/plain": ".txt",
}
_MAX_WEB_ARTIFACT_BYTES = 10 * 1024 * 1024


class ArtifactStorageError(RuntimeError):
    """A safe, provider-neutral artifact persistence failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ArtifactNotFoundError(ArtifactStorageError):
    """A requested artifact does not exist or its identifier is invalid."""

    def __init__(self) -> None:
        super().__init__("artifact_not_found", "The requested artifact was not found.")


class LocalPngImageGenerator:
    def generate(self, prompt: str) -> GeneratedImage:
        image = Image.new("RGB", (768, 1024), "#17251d")
        output = BytesIO()
        image.save(output, format="PNG")
        return GeneratedImage(
            content=output.getvalue(),
            media_type="image/png",
            generator_name="in-memory",
        )


class FoundryImageGenerator:
    def __init__(
        self,
        endpoint: str,
        deployment: str,
        timeout_seconds: float,
        client_factory: FoundryClientFactory,
    ) -> None:
        self._endpoint = endpoint
        self._deployment = deployment
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory
        self._client: _ImagesClient | None = None

    def generate(self, prompt: str) -> GeneratedImage:
        with dependency_span("foundry", "generate") as span:
            try:
                response = self._get_client().images.generate(
                    model=self._deployment,
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
            except Exception as error:
                translated_error = _translate_provider_error(error)
                record_span_outcome(
                    span, "failed", error_code=translated_error.code
                )
                raise translated_error from None

            try:
                if len(response.data) != 1:
                    raise ImageGenerationError(
                        "invalid_response",
                        "The image provider returned an invalid response.",
                    )
                encoded_image = response.data[0].b64_json
                content = b64decode(encoded_image, validate=True)
            except ImageGenerationError as error:
                record_span_outcome(span, "failed", error_code=error.code)
                raise
            except (AttributeError, IndexError, TypeError, ValueError, Base64Error):
                record_span_outcome(span, "failed", error_code="invalid_response")
                raise ImageGenerationError(
                    "invalid_response", "The image provider returned an invalid response."
                ) from None

            try:
                _validate_png(content)
            except ImageGenerationError as error:
                record_span_outcome(span, "failed", error_code=error.code)
                raise
            record_span_outcome(span, "succeeded")

        return GeneratedImage(
            content=content,
            media_type="image/png",
            generator_name="foundry",
        )

    def _get_client(self) -> _ImagesClient:
        if self._client is None:
            self._client = self._client_factory(
                self._endpoint, self._timeout_seconds
            )
        return self._client


def create_foundry_client(endpoint: str, timeout_seconds: float) -> _ImagesClient:
    base_url = normalize_azure_openai_endpoint(endpoint)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    return OpenAI(
        base_url=base_url,
        api_key=token_provider,
        timeout=timeout_seconds,
        max_retries=0,
    )


def normalize_azure_openai_endpoint(endpoint: str) -> str:
    if not endpoint or endpoint != endpoint.strip() or any(
        character.isspace() for character in endpoint
    ):
        raise ValueError("Azure OpenAI endpoint is invalid.")

    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        raise ValueError("Azure OpenAI endpoint is invalid.") from None

    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port not in (None, 443)
    ):
        raise ValueError("Azure OpenAI endpoint is invalid.")

    normalized_hostname = hostname.lower()
    is_azure_openai_resource = _AZURE_OPENAI_RESOURCE_HOST.fullmatch(
        normalized_hostname
    )
    is_foundry_service = _FOUNDRY_SERVICES_HOST.fullmatch(normalized_hostname)
    if (
        is_azure_openai_resource
        and parsed.path not in ("", "/", "/openai/v1", "/openai/v1/")
    ) or (is_foundry_service and parsed.path not in ("/openai/v1", "/openai/v1/")):
        raise ValueError("Azure OpenAI endpoint is invalid.")
    if not is_azure_openai_resource and not is_foundry_service:
        raise ValueError("Azure OpenAI endpoint is invalid.")

    return f"https://{normalized_hostname}/openai/v1"


def _validate_png(content: bytes) -> None:
    if not content or len(content) > _MAX_PNG_BYTES:
        raise _invalid_response()

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG" or image.width * image.height > _MAX_PNG_PIXELS:
                    raise _invalid_response()
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.load()
    except ImageGenerationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        raise _invalid_response() from None

    _validate_png_stream_termination(content)


def _validate_png_stream_termination(content: bytes) -> None:
    if not content.startswith(_PNG_SIGNATURE):
        raise _invalid_response()

    offset = len(_PNG_SIGNATURE)
    while offset < len(content):
        remaining = len(content) - offset
        if remaining < 12:
            raise _invalid_response()

        data_length = int.from_bytes(content[offset : offset + 4], "big")
        if data_length > remaining - 12:
            raise _invalid_response()

        chunk_type = content[offset + 4 : offset + 8]
        chunk_end = offset + 12 + data_length
        if chunk_type == _PNG_IEND:
            if data_length != 0 or chunk_end != len(content):
                raise _invalid_response()
            return

        offset = chunk_end

    raise _invalid_response()


def _invalid_response() -> ImageGenerationError:
    return ImageGenerationError(
        "invalid_response", "The image provider returned an invalid response."
    )


def _translate_provider_error(error: Exception) -> ImageGenerationError:
    status_code = getattr(error, "status_code", None)
    error_code = _provider_error_code(error)
    if status_code in (401, 403):
        return ImageGenerationError(
            "authentication_failed", "Image provider authentication failed."
        )
    if status_code == 429:
        return ImageGenerationError(
            "throttled", "The image provider is temporarily rate limited."
        )
    if status_code is not None and status_code >= 500:
        return ImageGenerationError(
            "provider_unavailable", "The image provider is temporarily unavailable."
        )
    if "content" in error_code or "safety" in error_code:
        return ImageGenerationError(
            "safety_rejected", "The image request was rejected by safety controls."
        )
    if error.__class__.__name__ == "APITimeoutError":
        return ImageGenerationError(
            "provider_timeout", "The image provider timed out."
        )
    if error.__class__.__name__ == "APIConnectionError":
        return ImageGenerationError(
            "provider_unavailable", "The image provider is temporarily unavailable."
        )
    return ImageGenerationError("generation_failed", "Image generation failed.")


def _provider_error_code(error: Exception) -> str:
    code = getattr(error, "code", "")
    body = getattr(error, "body", None)
    if not code and isinstance(body, dict):
        code = body.get("code", "")
        nested_error = body.get("error")
        if not code and isinstance(nested_error, dict):
            code = nested_error.get("code", "")
    return str(code).lower()


class InMemoryArtifactStore:
    def __init__(self, output_directory: str | Path = "artifacts") -> None:
        self._output_directory = Path(output_directory)
        self._content: dict[str, bytes] = {}

    def save(self, content: bytes, media_type: str) -> Artifact:
        artifact_id = str(uuid4())
        extension = _ARTIFACT_EXTENSIONS.get(media_type, ".bin")
        self._output_directory.mkdir(parents=True, exist_ok=True)
        file_path = self._output_directory / f"{artifact_id}{extension}"
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                dir=self._output_directory,
                prefix=f".{artifact_id}-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
            os.link(temporary_path, file_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        self._content[artifact_id] = content
        return Artifact(
            artifact_id=artifact_id,
            media_type=media_type,
            size_bytes=len(content),
            file_path=str(file_path),
        )

    def read(self, artifact_id: str) -> ArtifactContent:
        content = self._content[artifact_id]
        path = next(self._output_directory.glob(f"{artifact_id}.*"), None)
        media_type = "image/png" if path and path.suffix == ".png" else "text/plain"
        return ArtifactContent(content, media_type, len(content))


class BlobArtifactStore:
    def __init__(
        self,
        account_url: str,
        container_name: str,
        service_client: Any | None = None,
    ) -> None:
        parsed_account_url = urlsplit(account_url)
        hostname = parsed_account_url.hostname or ""
        if (
            parsed_account_url.scheme != "https"
            or parsed_account_url.username is not None
            or parsed_account_url.password is not None
            or parsed_account_url.port not in (None, 443)
            or parsed_account_url.path not in ("", "/")
            or parsed_account_url.query
            or parsed_account_url.fragment
            or not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9]{1,22}[a-z0-9])?\.blob\.core\.windows\.net",
                hostname,
            )
        ):
            raise ValueError("Azure Storage account URL is invalid.")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?", container_name):
            raise ValueError("Blob container name is invalid.")
        self._account_url = account_url
        self._container_name = container_name
        self._service_client = service_client

    def save(self, content: bytes, media_type: str) -> Artifact:
        if media_type != "image/png" or not content or len(content) > _MAX_WEB_ARTIFACT_BYTES:
            raise ArtifactStorageError(
                "artifact_unavailable", "The generated artifact could not be stored."
            )

        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings

        with dependency_span("blob", "write") as span:
            for _ in range(3):
                artifact_id = str(uuid4())
                blob_name = f"{artifact_id}.png"
                try:
                    self._container_client().get_blob_client(blob_name).upload_blob(
                        content,
                        overwrite=False,
                        content_settings=ContentSettings(content_type="image/png"),
                    )
                except ResourceExistsError:
                    continue
                except Exception as error:
                    translated_error = _translate_blob_error(error, "stored")
                    record_span_outcome(
                        span, "failed", error_code=translated_error.code
                    )
                    raise translated_error from None
                record_span_outcome(
                    span,
                    "succeeded",
                    attributes={"fantasy_cards.artifact_size_bytes": len(content)},
                )
                return Artifact(
                    artifact_id=artifact_id,
                    media_type="image/png",
                    size_bytes=len(content),
                    file_path=blob_name,
                )
            record_span_outcome(span, "failed", error_code="artifact_unavailable")
            raise ArtifactStorageError(
                "artifact_unavailable", "The generated artifact could not be stored."
            )

    def read(self, artifact_id: str) -> ArtifactContent:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            canonical_id = str(__import__("uuid").UUID(artifact_id))
        except (ValueError, AttributeError, TypeError):
            raise ArtifactNotFoundError() from None
        if canonical_id != artifact_id:
            raise ArtifactNotFoundError()

        with dependency_span("blob", "read") as span:
            try:
                downloader = self._container_client().get_blob_client(
                    f"{artifact_id}.png"
                ).download_blob(max_concurrency=1)
                properties = downloader.properties
                size_bytes = int(properties.size)
                media_type = properties.content_settings.content_type
                if (
                    media_type != "image/png"
                    or size_bytes < 1
                    or size_bytes > _MAX_WEB_ARTIFACT_BYTES
                ):
                    raise ArtifactStorageError(
                        "artifact_unavailable", "The requested artifact is unavailable."
                    )
                content = downloader.readall()
            except ResourceNotFoundError:
                record_span_outcome(span, "not_found", error_code="artifact_not_found")
                raise ArtifactNotFoundError() from None
            except ArtifactStorageError as error:
                record_span_outcome(span, "failed", error_code=error.code)
                raise
            except Exception as error:
                translated_error = _translate_blob_error(error, "read")
                record_span_outcome(
                    span, "failed", error_code=translated_error.code
                )
                raise translated_error from None
            if len(content) != size_bytes:
                record_span_outcome(span, "failed", error_code="artifact_unavailable")
                raise ArtifactStorageError(
                    "artifact_unavailable", "The requested artifact is unavailable."
                )
            record_span_outcome(
                span,
                "succeeded",
                attributes={"fantasy_cards.artifact_size_bytes": size_bytes},
            )
            return ArtifactContent(content, media_type, size_bytes)

    def _container_client(self) -> Any:
        if self._service_client is None:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient

            self._service_client = BlobServiceClient(
                account_url=self._account_url,
                credential=DefaultAzureCredential(),
            )
        return self._service_client.get_container_client(self._container_name)


def _translate_blob_error(error: Exception, action: str) -> ArtifactStorageError:
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

    if isinstance(error, ClientAuthenticationError) or getattr(
        error, "status_code", None
    ) in (401, 403):
        return ArtifactStorageError(
            "artifact_unavailable", "Artifact storage authorization failed."
        )
    if isinstance(error, HttpResponseError):
        return ArtifactStorageError(
            "artifact_unavailable", f"The generated artifact could not be {action}."
        )
    return ArtifactStorageError(
        "artifact_unavailable", f"The generated artifact could not be {action}."
    )


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}

    def get_by_idempotency_key(self, idempotency_key: str) -> GenerationJob | None:
        return self._jobs.get(idempotency_key)

    def save(self, job: GenerationJob) -> None:
        self._jobs[job.idempotency_key] = job


def deterministic_idempotency_key(title: str, prompt: str) -> str:
    return sha256(f"{title}\0{prompt}".encode()).hexdigest()
