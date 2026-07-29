# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Summarized by Scribe on 2026-07-29T10:19:41+02:00 because the history exceeded 15KB. Keep concise lasting context below. -->

### Standing project conventions
- Python is the primary application language. Use `uv` for project/dependency/environment/command workflows and TOML centered on `pyproject.toml`; keep secrets and deployment settings in env vars, secret stores, or deployment config.
- Azure resources are Bicep/azd-managed. PR-environment branches must follow `squad/{issue}-{slug}` or Azure preflight blocks with `invalid_names`.
- Prefer fast Python CI/static validation for infra invariants before Azure round trips.

### Reviewer lockout history relevant to Trinity
- Switch rejected Trinity's first `gpt-image-2` implementation for unsafe endpoint validation, incomplete PNG validation, missing CLI integration coverage, and egg-info artifacts; Neo owned the next revision.
- Switch rejected Neo's second image revision; Trinity and Neo were locked out and Tank owned the final independent revision.
- Tank's final `gpt-image-2` revision was approved: exact terminal PNG validation, safe endpoint/auth/retry/timeout/error contract, no egg-info artifacts, 22 tests plus checks passed.
- Switch rejected Trinity's artifact persistence revision for UUID overwrite and partial-temp-file risks; Tank independently fixed exact artifact-ID filenames, png/txt/bin allowlist, atomic exclusive publication, temp cleanup, and post-success-only memory updates. 33 tests/checks passed.
- For issue #37, Trinity independently replaced Neo's locked-out AI disclosure revision and shipped PR #64 (`a60b027`); follow-up #61 was filed. Verify governance claims against primary Microsoft Learn sources.

### Application and telemetry contracts
- Initial FastAPI/Jinja2 app, Blob adapter, UI, config, and docs reached Azure. Repaired revision was healthy but returned safe `503 artifact_unavailable` while policy-disabled Storage lacked private route.
- Application Insights export with local auth disabled requires explicit `ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)`; configured telemetry stays isolated from offline tests.
- Generation completion logging is one safe structured INFO event at the web boundary. Allowed fields: `correlation_id`, `outcome`, `success`, `duration_ms`; success may add `size_bytes`; provider failures may add `dependency: provider` and stable `error_code`. Exclude titles, prompts, endpoints, provider details, credentials, and image bytes.
- Issue #41 green-background change added a static CSS contract test. Palette/background changes must be contrast-checked against every foreground token on affected surfaces.

### PR-environment Python tooling owned or touched by Trinity
- Phase 1 audit confirmed `infra/scripts/pr_environment_names.py`, `infra/scripts/pr_preflight.py`, and tests were coherent issue #16 work aligned with docs, but not yet wired to `azure.yaml` or workflows. Targeted tests 67 and full suite 148 passed; local commit `2292357` recorded that work.
- Issue #15 item C added `infra/scripts/pr_smoke_test.py` with 17 tests. It polls `/health/live` then `/health/ready` under one deadline, retries connection errors and HTTP 408/429/502/503/504, fails fast on 404/other 4xx/500/wrong 200 bodies, keeps TLS verification on, and sanitizes/truncates response bodies. Full suite reached 165.
- Independent Phase 3 workflow fix: resolve app URL from `azd env get-value SERVICE_WEB_URI`, not the public Container App. Do not prepend a scheme; empty/invalid URL fails loudly. PR comment now reports real smoke failures. Static validation: YAML parsed and 192 tests passed; real Azure path remained unproven then.
- Switch later pinned smoke retry coverage per status because only 503 had been covered; final suite 192 passed.
- Issue #20 Phase 4 item B added `infra/scripts/pr_env_reaper.py` with 53 tests. Reap only exact allowlist groups: tags object, `ephemeral == 'true'`, `environment-type == 'pr-app'`, valid numeric `pr-number`, and either aware strictly-past `expires-at` or PR number in `--closed-pr-numbers`. Malformed input exits 3; malformed/naive timestamps and hostile tags keep resources. Rai proved adversarial safety; Switch pinned malformed-input exit code to literal nonzero 3. Suite reached 246.
- Issue #18 Phase 5 added deterministic `log_analytics` naming mirroring `application_insights`: max 63, compaction preserves `hash8`, printable/env var mapping added. Tests covered boundary/pathological cases; suite reached 252. Shared-worktree branch switching once clobbered uncommitted edits, so coordinate before switching and commit promptly.
- Issue #17 Phase 6 added `infra/scripts/pr_foundry_scope.py` with 16 tests. It is stdlib-only, path/label-based, and triage-only. Keep exact cost/safety allowlist narrow: Foundry files, main Bicep/params, adapters, Foundry/card prompt tests, or `requires:foundry`; `validate:live-foundry` is independent. Malformed input exits 3 and never emits false success. Full suite reached 269. Do not broaden matches without explicit cost-gate rationale.

### Azure PR environment operational facts
- Branch rename via GitHub API closed PR #44 instead of retargeting it; renamed branches may require replacement PRs.
- Azure OIDC subject is immutable and ID-qualified: `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`; Entra credentials must match exactly.
- PR Azure Environment pipeline run `30360924609` was first green. `AZURE_ENV_NAME` is capped at 40 chars from ARM deployment-name budget (64 minus current longest Bicep module prefix `private-virtual-network-`). Re-derive if module prefixes grow. Bicep `existing` references create no dependency edge; add explicit `dependsOn`.

### Issue #61 artifact authorization
- Read-only analysis found FastAPI currently returns `/api/artifacts/{uuid}` from form and JSON generation, stores artifacts without owner, and serves artifact content by UUID only.
- Recommended secure default: bind generated artifacts to authenticated subject, require principal on generation/read, app-stream artifacts with indistinguishable 404 for absent/unauthorized, and keep anonymous mode explicit for local development only.
- 📌 Team update (2026-07-29T10:19:41+02:00): Issue #61 design synthesis elevated app-level owner binding and fail-closed proxy work, and recorded the adjacent cross-user idempotency leak in `application.py:20-25` and `adapters.py:535-543` as a required sequencing consideration. — decided by Squad Coordinator
📌 Team update (2026-07-29T11:05:00+02:00): Issue #61 identity model changed from Container Apps Easy Auth headers to app-owned single-tenant Entra OIDC with app-managed session cookies. Trinity's implementation plan must use the session principal instead of `X-Ms-Client-Principal-Id`, add CSRF protection for the two state-changing POST routes, and include `authlib` as the recommended OIDC dependency. — decided by Benoit Moussaud; recorded by Scribe
