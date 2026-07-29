# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Summarized Learnings

<!-- Summarized by Scribe on 2026-07-29T11:05:00+02:00 because the history exceeded 15KB. Keep concise lasting context below. -->

### Standing quality conventions
- Tests use Python `unittest`/`pytest`; invoke with `PYTHONPATH=src python -m pytest` to avoid importing sibling worktrees. Use `uv` where project workflows require it.
- Reviewer lockout is strict: after Switch rejects a revision, the rejected author does not repair that same scope.
- Quality evidence must be falsifiable and non-tautological. Avoid tests that only assert a value against itself; pin externally meaningful literals for security-bearing constants.
- Green builds can hide weak assertions. Preserve explicit fail-fast/retry/status coverage, malformed input exits, and negative-path assertions that prove dangerous calls did not occur.

### Durable contracts Switch enforces
- Foundry `gpt-image-2` adapter: opt-in config, Azure OpenAI v1 route, managed-identity scope `https://ai.azure.com/.default`, strict Azure endpoint validation, bounded timeout, zero retries, safe errors, and complete base64 PNG validation through terminal IEND.
- Artifact persistence: exact artifact-ID filenames, png/txt/bin allowlist, atomic exclusive no-overwrite publication, guaranteed temp cleanup, and post-success-only in-memory state updates.
- Web logging: one safe structured INFO event at generation completion; allowed fields include correlation_id, outcome, success, duration_ms, size_bytes on success, and dependency/provider error_code for provider failures. Never log prompts, titles, endpoints, credentials, provider internals, or bytes.
- Palette/background changes must be contrast-checked against every foreground token on every affected surface.
- PR-environment safety: branch convention is `squad/{issue}-{slug}`; preflight gate order keeps fork/untrusted/draft/invalid-name/app-cap before foundry authorization. `AZURE_ENV_NAME` budget is currently 40 chars; Bicep `existing` references need explicit `dependsOn`.

### Recent quality history
- Issue #41 green palette: Switch rejected inaccessible coral/gold/muted contrast, then approved Neo's accessible revision with static contrast tests.
- Issue #49 content-policy test design: application policy rejections should return 422 `content_policy_rejected`, never call the provider or save artifacts, avoid raw prompt/title leakage in responses/logs, preserve provider `safety_rejected` semantics, cover evasion/idempotency/form+JSON surfaces, and make production RAI policy wiring verifiable by explicit identifier/version or release evidence.

### Issue #61 artifact authorization quality plan
- Original #61 gate required owner-bound artifact reads, fail-closed identity handling, enumeration resistance, safe logs/errors, and PR smoke auth without a production bypass.
- Product decision changed identity from Easy Auth headers to app-owned single-tenant Entra OIDC plus app-managed session cookies. Manual Easy Auth header-spoofing evidence is superseded.
- Revised acceptance coverage must automate OIDC/session behavior: state, nonce, PKCE, redirect URI allowlisting, ID-token signature/issuer/audience/expiry validation, open-redirect resistance, malformed/tampered/expired/fixed/replayed/missing session cookies, and opaque owner binding on generation/read.
- Cookie-authenticated POST routes require CSRF protection and tests for the two state-changing POST surfaces.
- Anonymous access is denied except agreed health probes; missing/non-owner artifacts must remain indistinguishable 404; pre-existing ownerless artifacts are not migrated and age out through the 30-day lifecycle.
- PR smoke support must use real OIDC/session auth or a disabled-by-default test identity that is impossible to enable in production. No production auth-bypass hook is acceptable.

📌 Team update (2026-07-29T11:11:09+02:00): LESSON from issue #61 closure: when the coordinator or PO asks for a verdict, restating the constraint is not an answer. Switch's quality role owes a recommendation; in this case the final verdict was that losing unattended authenticated PR end-to-end generation is an ACCEPTABLE LOSS while health-only PR smoke remains valuable and auth-bypass substitutes remain rejected. — recorded by Scribe
