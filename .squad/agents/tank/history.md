# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T12:33:43+0000): Azure resources must always be configured through Bicep; prefer Azure Verified Modules when a suitable maintained module exists, with native Bicep as the fallback — decided by bmoussaud

📌 Team update (2026-07-22T12:49:52+0000): Prefer Azure Container Apps with dedicated workload profiles for production hosting in France Central; use Microsoft Foundry in Sweden Central subject to exact region, model, SKU, quota, capacity, and feature validation; prefer user-assigned managed identities with least privilege and separate identities across trust boundaries — decided by bmoussaud

📌 Team update (2026-07-22T13:28:52+0000): Use `azd` and `azure.yaml` for Azure application deployment; authenticate with `azd auth login`, with `az login` as a fallback — decided by bmoussaud

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Neo's second `gpt-image-2` revision because PNG validation accepts valid PNG data with trailing bytes and the ignored egg-info directory remains on disk. Trinity and Neo may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank completed the independent final `gpt-image-2` revision without participation from locked-out authors. Switch approved it with no findings after 22 tests, `compileall`, `uv lock --check`, `git diff --check`, and egg-info absence validation passed. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank updated `create_foundry_client` endpoint normalization to support user-supplied `https://<resource>.services.ai.azure.com/openai/v1` endpoints while retaining `*.openai.azure.com`, added `size=1024x1024`, and preserved Azure identity, token scope, timeout, and zero-retry behavior. Switch approved with no findings after 24 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank fixed Foundry 500 `Unable to get resourceinformation` by removing unsupported extra `output_format`, matching the user's working `images.generate` request body, normalizing the base URL without changing the outbound route, and making 5xx errors provider-neutral without body leakage. Switch approved after 25 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank repaired user-edited Foundry regressions by restoring scope `https://ai.azure.com/.default`, bounded timeout, and `max_retries=0`, removing debug prints, retaining the exact request shape, and covering real `openai.InternalServerError` through adapter and CLI without traceback or body leakage. Switch approved after 27 tests and repository checks passed. Runtime used `*.openai.azure.com` while the authoritative sample uses `*.services.ai.azure.com/openai/v1`; endpoint/deployment pairing remains the service-side fix. No live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's artifact persistence revision because UUID collisions can overwrite existing finalized artifacts and failed temporary writes can leave partial temp files. Trinity may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank independently completed the artifact persistence revision. Artifacts expose `file_path`; `InMemoryArtifactStore` writes beneath the configured output directory using exact artifact-ID filenames, a png/txt/bin allowlist, atomic exclusive publication, collision no-overwrite, guaranteed temporary cleanup, and memory updates only after publication succeeds. `FANTASY_CARD_OUTPUT_DIR`, CLI JSON, and README support were included. Switch approved after 33 tests and repository checks passed; no commit was made. — decided by Switch

📌 Team update (2026-07-22T16:01:59+0000): Prepared `azure.yaml` and Bicep for subscription `external-bmoussaud-ms`, Sweden Central, resource group `rg-fantasy-cards-dev-8f327f8c`, Foundry account/project `fnd-fantasy-cards-dev-8f327f8c` / `prj-fantasy-cards-dev-8f327f8c`, and deployment `gpt-image-2-dev`. Bicep and azd validation passed; provisioning remains blocked on explicit user approval and no Azure resources were created. — decided by Morpheus, Tank, and Neo

📌 Team update (2026-07-23T09:03:12+0000): Independently revised rejected PR #6 under strict Switch lockout. CI whitespace validation now checks the actual committed range for pull requests, ordinary pushes, and initial pushes, and third-party actions are pinned by full SHA. Morpheus approved after all gates and 34 tests passed. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Azure provisioning, D4 validation, deployment, diagnostics, telemetry/RBAC repair, and application-only recovery completed. The real repaired revision is healthy and receives 100% traffic; Storage remains `publicNetworkAccess=Disabled` under management-group policy, so generation is intentionally degraded and D4 charges continue. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Public-endpoint repair cannot survive policy evaluation. Policy-compliant Blob recovery requires separately approved parallel VNet-integrated Container Apps environment replacement, Blob private endpoint, and private DNS. bmoussaud chose hold state unchanged; do not provision private networking or decommission the current D4 environment without new approval. — decided by Morpheus; recorded by Scribe

### 2026-07-27T14:24:13+02:00 — Issue #16: PR-env deterministic naming + safety preflight (Phase 1)
Delivered infra/scripts/pr_environment_names.py + infra/scripts/pr_preflight.py + tests/test_pr_environment_names.py (36 tests, all pass; full suite 117 pass). Std-lib only, placed in infra/scripts per platform-tooling convention. Flagged hash8 doc discrepancy: rule yields 4c32c628, doc example says 4717e5bb — implemented the rule, asserted computed value, left doc fix to humans (doc lives on another branch).

### 2026-07-27T14:38:43+02:00 — Issue #16 follow-up: Fact Checker findings applied
Enforced Container Apps start-letter/end-alnum + min length 2 (regex + validator), added degenerate/truncation tests. Handled undocumented managed-environment & azd limits with defensive compaction (no uncited limits asserted). Documented hash8 canonical owner/repo input contract. hash8 doc example 4717e5bb confirmed unreproducible across 5 repo forms — asserting computed 4c32c628. Full suite 120 pass.

📌 Team update (2026-07-27T14:24:13+02:00): Your Phase 1 names are authoritative but remain unconsumed by `web.bicep`; Phase 3/#15 must pass precomputed container-app, storage-account, and managed-environment names as parameters. Rai rejected the original trust/Foundry controls; Tank was locked out while Morpheus independently remediated them, and Rai then approved GREEN (148 tests).

### 2026-07-27T16:58:24+02:00 — Issue #25: relaxed CI ownership gate
Dropped the hard branch-name regex failure in ci.yml's ownership step; `squad/{issue}-{slug}` is now a `::notice::` convention. Kept issue-closure (exactly one) as a hard gate and made the branch<->issue cross-check conditional (runs only for conforming branches). Preserved existing injection-safe env: handling of BODY. Validated 6 cases via throwaway bash harness incl. shell-injection body (no execution); 148 tests OK; actionlint unavailable (skipped).

📌 Team update (2026-07-27T16:58:24.269+02:00): Rai independently reviewed commit 51336ce (issue #25 CI relaxation) and issued 🟢 GREEN. Injection safety confirmed; conditional cross-check is a typo-catcher, not a security control (documented honestly). Non-blocking advisories: duplicate `Closes #N` counts double (over-strict, pre-existing); grep matches keywords inside code fences (pre-existing). — reviewed by Rai

### 2026-07-27T17:14:24+02:00 — Issue #15 (Phase 3, work item A): Bicep/azd name parameterization
Parameterized `infra/web.bicep` resource names instead of constructing them from `environmentName`/`resourceToken`. Added params `containerAppName`, `containerAppsEnvironmentName`, `storageAccountName` and (newly discovered overflow) private `virtualNetworkName` to `web.bicep` + `main.bicep`, threaded via `main.bicepparam` `readEnvironmentVariable(..., '')` with empty-sentinel fallback to today's dev-derived values (dev unchanged — verified both empty→computed and PR-value→passthrough with `az bicep build-params`). Added a bounded `virtual_network` name (anchored to compacted `managed_environment`, ≤45 chars) and a `--format envvars` emitter + `BICEPPARAM_ENV_VARS` contract to `pr_environment_names.py`; documented the CLI→env-var table in the design doc. Left the three `private*` names derived-from-token/param alone (justified: inherently bounded). Ran: `az bicep build` (exit 0), `build-params` both paths, full suite 173 tests OK (was 148). Deferred identity-name mapping to work item B.

📌 Team update (2026-07-27T20:35:12+02:00): Phase 3 (#15) complete. Morpheus approved seam closure (item A) — APPROVE WITH CHANGES (one blocking defect in item B's URL resolution, owned by Trinity and fixed in the fix pass; commit 06a04a7). Switch's test review (a94f973) hardened `_parse_count` in `pr_preflight.py` from crashable-on-unicode to ASCII fail-closed: this was Tank-authored code. Also Switch extended `PropertySweepTests` with the vnet invariant. Tank was excluded from the fix pass as author of items A and B (reviewer rejection protocol). Final suite: 192 tests OK. — recorded by Scribe

### 2026-07-27T21:04:25+02:00 — Issue #20 (Phase 4, work item A): PR-env teardown + daily janitor
Added `.github/workflows/pr-environment-teardown.yml` (`pull_request: closed`, both merge+abandon) and `.github/workflows/pr-environment-janitor.yml` (`schedule` daily + `workflow_dispatch` dry-run). Teardown uses tag-scoped `az group delete` (allowlist tags ephemeral+environment-type+pr-number) instead of fragile `azd down` state reconstruction; no per-PR KV/CogSvc so nothing to `--purge`. Concurrency: SEPARATE group `pr-azure-teardown-<n>` + `cancel-in-progress:false` so an obsolete/queued deploy (deploy group `pr-azure-<n>`, cancel-in-progress:true) can never interrupt cleanup. Idempotent: empty tag-match = no-op exit 0; only "already gone" treated as success, real delete failures fail (no `|| true`). Fork job skipped at job level (never attempts a login it can't complete). Janitor: `az group list` first-pass `--query` = candidates only; authoritative reap/keep from Trinity's `pr_env_reaper.py --format env` (reads `reap_names=`, verified space-separated); `--now` injected explicitly; closed PRs via `gh pr list` -> `--closed-pr-numbers` for pre-TTL orphans; resilient delete surfaces overall failure. No `github.event.*` in run blocks; actions SHA-pinned; least-priv per job. Owned ONLY workflows — did not touch reaper/tests (Trinity). Both parse; full suite 245 OK. Recorded decision in inbox.

### 2026-07-27T21:27:16+02:00 — Issue #20 (Phase 4 advisories): teardown failure-honesty
Fixed two non-blocking advisories in .github/workflows/pr-environment-teardown.yml from Rai's GREEN review; surgical, workflow file only. ADVISORY 1: z group list ran under set -uo pipefail (no `-e`), so a failed query left `matches` empty and the idempotency branch reported a FALSE `status=noop` exit 0 — leaking the RG until the janitor reaped it (up to 7 days). Fix: capture the query exit status explicitly (`matches=$(az group list ...)` || query_rc=$?`) and `exit 1` on `query_rc != 0`; empty-but-successful still no-ops exit 0 (idempotency preserved for never-deployed/draft/fork/already-gone). Did NOT add `set -e` — delete loop's "already gone vs failed" distinction untouched. ADVISORY 2: chose the real guard over softening the comment — reject `PR_NUMBER` not matching `^[0-9]+$` before `--query`; makes the "validated integer" claim true and removes reliance on the reader knowing GitHub's payload schema. Proved via Git bash: failing query -> exit 1 loud; empty success -> noop exit 0; guard accepts 42, rejects "42; rm -rf" and "". YAML parses; full suite 246 OK. Decision in inbox (tank-teardown-failure-honesty.md).

## 2026-07-27 - Issue #29: Azure OIDC + repo config for per-PR ephemeral envs

- Created Entra app registration `squad-workshop-pr-envs` (appId 3fdc9811-6ee9-4b95-89ae-ed79bba74235, SP f7cead19-c757-47ba-9993-f6c44a9d9c21), no secret.
- Added federated credential `github-pr-app-environment` subject `repo:bmoussaud/squad-workshop:environment:azure-pr-app` - one credential covers deploy/teardown/janitor.
- Granted Contributor + Role Based Access Control Administrator at subscription scope (no Owner).
- Created GitHub Environment `azure-pr-app` (no reviewers/branch policy).
- Set 11 repo Actions variables (SHARED_* + AZURE_*).
- Verified: compliant branch + real ACR => decision=proceed; empty ACR => invalid_service_name.
- Finding: PR #30 branch `bmoussaud-musical-spork` fails the name gate (invalid_names) before the ACR check, so its preflight stays red by design. Rerun confirmed SHARED_ACR_NAME now populated.
- Added runbook docs/runbooks/pr-environment-azure-setup.md.
