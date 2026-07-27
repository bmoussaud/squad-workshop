### 2026-07-27T17:14:24.871+02:00: PR smoke-test script retry contract (#15, item C)
**By:** Trinity
**What:** Added `infra/scripts/pr_smoke_test.py`, a stdlib-only post-deploy smoke test the Phase 3 workflow calls after `azd deploy`. It polls `GET /health/live` then `GET /health/ready` with bounded exponential backoff against one shared hard deadline, and emits a machine-readable verdict.

CLI contract (for Tank to wire the workflow):
- Args: `--base-url` (required, must be http/https), `--deadline-seconds` (default 180), `--request-timeout-seconds` (default 10), `--initial-backoff-seconds` (1.0), `--max-backoff-seconds` (15.0), `--backoff-multiplier` (2.0), `--format {env,json}` (default env).
- Output keys (env `key=value` lines or JSON object): `passed`, `reason_code`, `message`, `base_url`, `elapsed_seconds`, `total_attempts`, `live_healthy`, `live_status`, `live_attempts`, `live_reason`, `ready_healthy`, `ready_status`, `ready_attempts`, `ready_reason`.
- Exit codes: 0 = pass, 1 = smoke failure (fail the workflow step), 2 = usage/config error (bad URL or knob).

Retry policy: RETRY on connection/timeout errors and HTTP `408, 429, 502, 503, 504` (cold-start / no-ready-replica / throttling). FAIL FAST on everything else — `404` (wrong image), other `4xx`, `500` (app bug, not transient), and any `200` whose JSON body is not the expected `{"status": "live"|"ready"}`. Readiness legitimately answers `503` during warmup, so `503` is retried and a persistently misconfigured app is caught by the deadline rather than hanging.

**Why:** Cold-started Container Apps fail their first probes; retrying only *transient* statuses with a hard deadline gives a reliable verdict without burning CI time on non-transient answers. TLS verification is always on (no disable flag). Response bodies are never echoed wholesale — only a short, truncated, control-character-stripped excerpt — so a crafted response on a public repo cannot inject a log line or GitHub Actions workflow command. Scope was the script only; no Bicep, workflow, or app code was touched (items A and B are Tank's).
