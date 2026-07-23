# Application Development Standard

Python is the primary language for application development. Use `uv` where
applicable to manage the Python version and environment, project dependencies and
lockfile, and execution of application, test, and project-tool commands.

Use TOML for Python project and tool configuration, with `pyproject.toml` as the
canonical project configuration file. This standard does not require runtime
secrets or environment-specific deployment settings to be stored in TOML; use
environment variables, secret stores, and deployment-specific configuration when
those mechanisms are appropriate.

## CLI Environment Configuration

All CLI applications must load local environment configuration from `.env` at
their composition-root entry point with `python-dotenv`'s `load_dotenv()` before
reading environment-backed settings. Existing process environment variables keep
precedence over values loaded from the file.

For an `azd` environment, refresh local configuration from the repository root:

```bash
azd env get-values > .env
```

Treat `.env` as generated local runtime state: ignore it in Git, never read or
log its contents in automation, and regenerate it after Azure outputs change.

## Web Application

The deployable ASGI entry point is `fantasy_cards.web:app`. Run it locally with
the deterministic PNG generator and filesystem artifact adapter:

```bash
uv run uvicorn fantasy_cards.web:app --host 0.0.0.0 --port 8000 --workers 1 --limit-concurrency 16
```

The web host is a thin inbound adapter over `GenerationService`. It serves a
Jinja2 form at `GET /`, accepts the no-JavaScript form at `POST /generations`,
and exposes JSON generation at `POST /api/generations`. Generated artifacts are
streamed through `GET /api/artifacts/{artifact_id}`; storage paths and provider
values are never exposed. `GET /health/live` checks only the process, while
`GET /health/ready` validates composition and environment configuration without
credential discovery or dependency network calls.

Request bodies are limited to 16 KiB. Card names are trimmed and limited to 80
Unicode characters; descriptions are trimmed and limited to 1000. Each process
admits one generation at a time and applies a rolling, process-local attempt
limit. These controls reset on restart and are not coordinated across replicas.
Job state and idempotency are also process-local in this synchronous slice.

### Web Configuration

Local defaults use `FANTASY_CARD_ARTIFACT_STORE=filesystem` and write beneath
`FANTASY_CARD_OUTPUT_DIR` (default `artifacts`). The Azure composition uses:

- `FANTASY_CARD_ARTIFACT_STORE=blob`
- `AZURE_STORAGE_ACCOUNT_URL` as the HTTPS Blob service URL
- `FANTASY_CARD_BLOB_CONTAINER` as the private container name
- `FANTASY_CARD_MAX_GENERATION_CONCURRENCY=1`
- `FANTASY_CARD_RATE_LIMIT_ATTEMPTS=10`
- `FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS=600`

`BlobArtifactStore` implements the provider-neutral `ArtifactStore` and
`ArtifactReader` ports. It authenticates lazily with `DefaultAzureCredential`,
accepts only PNG payloads up to 10 MiB, creates opaque UUID blob names without
overwrite, and performs bounded application-mediated reads. It does not create
containers or accept connection strings, account keys, or SAS tokens.

Artifact reads distinguish absence from dependency failure at the adapter
boundary. Invalid or absent canonical artifact IDs raise `ArtifactNotFoundError`
and the web route returns `404 artifact_unavailable`. Blob authorization,
service, malformed-content, and other storage failures raise
`ArtifactStorageError` and return `503 artifact_unavailable`. Every JSON error
retains the stable envelope and server-generated or validated correlation ID;
storage exception details are never serialized.

Foundry selection is unchanged: set `FANTASY_CARD_IMAGE_GENERATOR=foundry`
with `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, and the bounded
`FANTASY_CARD_IMAGE_TIMEOUT_SECONDS`. The CLI remains available through
`uv run fantasy-card` and retains its existing local composition.

### Application Telemetry

When both `APPLICATIONINSIGHTS_CONNECTION_STRING` and `AZURE_CLIENT_ID` are
present, the application lazily creates
`ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)`, passes it to the
supported `azure-monitor-opentelemetry` distribution, configures the exporter
once, and instruments each FastAPI application instance. The connection string
routes telemetry; it is not a local-auth credential. If either setting is absent,
telemetry setup is a no-op and does not fall back to connection-string-only local
authentication. Imports, health checks, CLI use, and offline tests do not request
tokens or make network calls. Local structured JSON logs remain enabled in both
modes.

FastAPI request spans provide HTTP duration and status. Explicit client spans are
named `fantasy_cards.foundry.generate`, `fantasy_cards.blob.write`, and
`fantasy_cards.blob.read`; their attributes are limited to
`fantasy_cards.dependency`, `fantasy_cards.operation`,
`fantasy_cards.outcome`, `fantasy_cards.error_code`, and artifact byte count.
Generation events add correlation ID, safe outcome, duration, and optional byte
count. Structured dependency logs export the stable dimensions `dependency`,
`operation`, `success`, `error_code`, and `correlation_id` for alert queries.

Automatic Azure SDK and HTTP client instrumentation, browser injection, live
metrics, and performance counters are disabled. Telemetry never records card
titles, descriptions/prompts, image bytes, provider or storage endpoints,
deployment/account/container names, tokens, credentials, exception text, or
provider response bodies.