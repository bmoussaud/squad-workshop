# Squad Decisions

## Active Decisions

### 2026-07-22T12:33:43+0000: Azure resource configuration
**By:** bmoussaud (via Copilot)
**What:** Azure resources must always be configured through Bicep. Prefer Azure Verified Modules when a suitable maintained module exists; use native Bicep as the fallback.
**Why:** User directive establishing the project's Azure infrastructure-as-code standard.

### 2026-07-22T12:40:47+0000: Python application development workflow
**By:** bmoussaud (via Copilot)
**What:** Python is the primary application development language. Use `uv` for Python project, dependency, environment, and command workflows. Use TOML, centered on `pyproject.toml`, as the canonical project and tool configuration format. Runtime secrets and deployment settings remain in appropriate environment variables, secret stores, or deployment configuration.
**Why:** User directive establishing the project's application language, Python workflow tooling, and configuration standards while keeping runtime and deployment concerns in their appropriate systems.

### 2026-07-22T12:49:52+0000: Azure hosting, agentic platform, and identity preferences
**By:** bmoussaud (via Copilot)
**What:** Prefer Azure Container Apps with dedicated workload profiles for production application hosting in France Central. Approve Microsoft Foundry for the agentic platform, with Sweden Central preferred, subject to validating the exact region, model, SKU, quota, capacity, and required features before provisioning. Prefer user-assigned managed identities while preserving least privilege and separate identities for distinct trust boundaries.
**Why:** User directive establishing production hosting, agentic platform, regional, capacity-validation, and workload identity preferences.

### 2026-07-22T13:28:52+0000: Azure application deployment workflow
**By:** bmoussaud (via Copilot)
**What:** Use the Azure Developer CLI (`azd`) and `azure.yaml` to manage application deployment to Azure. Authenticate the shell to the Azure subscription with `azd auth login`; Azure CLI authentication with `az login` is available as a fallback.
**Why:** User directive establishing the project's Azure application deployment workflow.

### 2026-07-23: Resource-group-scoped AVM-first Bicep
**By:** bmoussaud (via Copilot)
**What:** Every project-owned Bicep file must use `targetScope = 'resourceGroup'`. Deployments must use an exact-version Azure Verified Module first; native Bicep is allowed only when no suitable AVM preserves the required contract, and the fallback reason must be documented.
**Why:** User directive establishing a consistent deployment boundary and requiring maintained verified modules before native resource declarations.

### 2026-07-23: CLI applications load local dotenv configuration
**By:** bmoussaud (via Copilot)
**What:** Every CLI application loads `.env` with `python-dotenv` at its composition-root entry point before reading environment-backed settings. For azd-managed projects, local configuration is refreshed with `azd env get-values > .env`; the generated file is ignored and never logged or committed.
**Why:** User directive establishing a consistent local configuration workflow for all project CLI applications.

### 2026-07-22T13:11:01+0000: Provider-neutral modular monolith for the first vertical slice
**By:** Morpheus
**What:** Start with one Python application organized around domain models and use-case services, with explicit ports for image generation, artifact storage, and job state. Keep model vendors and Azure services behind adapters. Use a validated card-generation request and a job-shaped result contract with stable identifiers, status, provenance, and artifact metadata. Begin with synchronous in-process orchestration while preserving interfaces that can move to a queue later.
**Why:** A thin end-to-end path minimizes setup cost while keeping image provider, Azure host, storage, retention, and asynchronous execution choices reversible until latency, payload size, safety, cost, and reliability are measured.

### 2026-07-22T13:11:01+0000: Switch rejected Trinity's first gpt-image-2 implementation
**By:** Switch
**What:** Reject Trinity's first `gpt-image-2` implementation because endpoint validation is unsafe, PNG validation is incomplete, CLI integration coverage is missing, and generated egg-info artifacts are included. Strict reviewer lockout applies: Trinity may not revise this artifact, and Neo owns the next revision.
**Why:** The implementation does not meet the required security, output-validation, integration-test, and repository-hygiene standards. Reviewer rejection protocol requires an independent revision owner.

### 2026-07-22T13:11:01+0000: Switch rejected Neo's second gpt-image-2 revision
**By:** Switch
**What:** Reject Neo's revision because PNG validation accepts a valid PNG followed by trailing bytes, and the ignored egg-info directory remains on disk. Strict reviewer lockout applies: Trinity and Neo may neither revise nor advise on the next revision; Tank owns it independently.
**Why:** The revision still fails strict artifact validation and repository-hygiene requirements. Reviewer rejection protocol locks out both prior authors from the next revision cycle and requires Tank to produce the next version without their contribution.

### 2026-07-22T13:11:01+0000: Foundry gpt-image-2 adapter contract
**By:** Morpheus, Trinity, Neo, Tank
**What:** Keep the in-memory image generator as the default and enable the existing Microsoft Foundry `gpt-image-2` deployment only through environment configuration. The Foundry adapter uses the OpenAI v1 endpoint with `DefaultAzureCredential` and scope `https://ai.azure.com/.default`, strict Azure endpoint validation, `max_retries=0`, a bounded timeout, safe errors, and complete base64 PNG validation through an exact terminal IEND chunk with bounded dimensions.
**Why:** Provider opt-in preserves offline behavior while the validated endpoint, authentication, retry, timeout, error, and artifact contracts make the cloud integration explicit and bounded.

### 2026-07-22T13:11:01+0000: Switch approved Tank's final gpt-image-2 revision
**By:** Switch
**What:** APPROVE Tank's independent final revision with no findings. The implementation, offline CLI integration, adapter and configuration tests, dependency and README updates, lockfile, generated-artifact exclusions, and repository cleanup satisfy the review requirements. Final local validation passed 22 tests, `compileall`, `uv lock --check`, and `git diff --check`; egg-info artifacts are absent.
**Why:** Tank corrected exact PNG termination and repository hygiene without participation from the locked-out prior authors, and Switch's third independent review found no remaining defect. Live Azure invocation remains a residual validation step because authentication was unavailable; it requires an endpoint, deployment name, authorized identity and RBAC, quota, and network access.

### 2026-07-22T13:11:01+0000: Switch approved Tank's Foundry 500 request-shape fix
**By:** Switch
**What:** APPROVE Tank's recurring repair for Foundry 500 `Unable to get resourceinformation`. User-edited regressions were repaired by restoring scope `https://ai.azure.com/.default`, the bounded timeout, and `max_retries=0`, and by removing debug prints. The exact request shape remains intact. A real `openai.InternalServerError` is covered through both adapter and CLI paths without traceback or response-body leakage. Local validation passed 27 tests, `compileall`, `uv lock --check`, and `git diff --check`.
**Why:** The repaired adapter restores the approved authentication, retry, timeout, request, and error-handling contract. The failed runtime used `foundry-j7hqwc4422gp4.openai.azure.com`, while the user's authoritative sample uses `foundry-j7hqwc4422gp4.services.ai.azure.com/openai/v1`; endpoint/deployment pairing is the remaining service-side fix. No live Azure call was made because variables and credentials were unavailable to the agent environment.

### 2026-07-22T13:11:01+0000: Switch rejected Trinity's artifact persistence revision
**By:** Switch
**What:** Reject Trinity's artifact persistence revision because a UUID collision can overwrite an existing finalized artifact, and a temporary write failure can leave a partial temp file. Strict reviewer lockout applies: Trinity may neither revise nor advise on the next revision; Tank owns the next revision independently.
**Why:** Artifact persistence must preserve existing finalized files and clean up incomplete temporary writes on failure. Reviewer rejection protocol requires an independent revision owner and excludes the rejected author from revision and advisory participation for this cycle.

### 2026-07-22T13:11:01+0000: Switch approved Tank's artifact persistence revision
**By:** Switch
**What:** APPROVE Tank's independent artifact persistence revision. Artifacts now expose `file_path`; `InMemoryArtifactStore` writes bytes beneath the configured output directory using the exact `artifact_id` filename and a `png`/`txt`/`bin` extension allowlist. Publication is atomic and exclusive, collisions never overwrite finalized files, temporary files are always cleaned up, and in-memory state updates only after successful publication. `FANTASY_CARD_OUTPUT_DIR`, CLI JSON output, and README documentation are updated.
**Why:** Tank independently corrected the collision and temporary-cleanup defects while Trinity's reviewer lockout remained in force. Switch's final review approved the revision after 33 tests, `compileall`, `uv lock --check`, `git diff --check`, and a clean residue scan passed. No commit was created.

### 2026-07-22T16:01:59+0000: Foundry provisioning prepared and awaiting explicit approval
**By:** Morpheus, Tank, Neo
**What:** The Bicep/azd target is prepared for subscription `external-bmoussaud-ms` in Sweden Central (`swedencentral`): resource group `rg-fantasy-cards-dev-8f327f8c`, Foundry account `fnd-fantasy-cards-dev-8f327f8c`, Foundry project `prj-fantasy-cards-dev-8f327f8c`, and model deployment `gpt-image-2-dev`. The validated model target is `gpt-image-2` version `2026-04-21` on `GlobalStandard`, proposed capacity 1. At validation time, live capacity was 1 and quota was limit 2/current usage 1. Azure provisioning is a billable gate and must not run until bmoussaud explicitly approves it. No Azure resources were created.
**Why:** The design review established a coherent deployment lifecycle and an explicit approval boundary. Azure preflight and local validation passed, while Neo independently confirmed the exact regional model facts. Approval must also acknowledge cross-geography processing and default content and abuse monitoring before provisioning.

### 2026-07-23T08:27:28+0000: Policy-compliant private Blob recovery supersedes public-endpoint repair (consolidated)
**By:** Morpheus
**What:** The initial proposal to restore authenticated public Blob reachability is superseded because management-group policy enforces Storage `publicNetworkAccess=Disabled`. Recovery therefore requires a parallel external workload-profiles Container Apps environment attached at creation to a delegated `/27` infrastructure subnet, a separate `/28` private-endpoint subnet, one Blob private endpoint, and `privatelink.blob.core.windows.net` private DNS with VNet link and zone group. Reuse the existing private Storage container, application UAMI, and exact RBAC scopes; retain public Container Apps ingress. Create `-private` environment/app resources, validate before cutover, retain the old environment for rollback, and decommission only with separate approval. The user selected hold state unchanged, so no private-network implementation or destructive cost stop is authorized. The repaired application revision may remain live in degraded mode, but generation is not accepted until private Blob connectivity passes.
**Why:** Live ARM showed a non-VNet D4 Container Apps environment and no private route to policy-disabled Storage. Service endpoints cannot satisfy `publicNetworkAccess=Disabled`, and the current environment cannot gain VNet integration in place. Parallel replacement is the smallest policy-compliant recovery but temporarily doubles D4 cost and adds private endpoint/DNS cost, requiring explicit approval. Holding preserves the healthy application endpoint and security posture while leaving safe `503 artifact_unavailable` generation behavior and ongoing D4 charges explicit.

### 2026-07-23T14:02:52+0000: Safe INFO generation lifecycle logging (consolidated)
**By:** Trinity, Switch
**What:** The web boundary emits one structured INFO `generation_completed` record for each completed generation attempt. Records contain only `correlation_id`, `outcome`, `success`, and `duration_ms`; successful attempts additionally include `size_bytes`, and provider failures include `dependency: "provider"` and a stable `error_code`. Startup logging reports only whether telemetry configuration was selected. OpenTelemetry lifecycle events remain separate. Structured messages and logging dimensions must exclude titles, prompts, endpoints, provider details, credentials, and image bytes.
**Why:** The web boundary has the final outcome and artifact size, so this contract provides deterministic operational traceability for successful and provider-failed requests without exposing request, dependency, identity, or artifact-sensitive data. Focused acceptance tests enforce the safe event shape.

### 2026-07-23T14:05:36+0000: AVM-first Bicep policy correction supersedes no-AVM directive
**By:** bmoussaud (via Copilot)
**What:** Supersede the accidental native-only/no-AVM instruction recorded during this session. All project-owned Bicep resource implementations must use exact-version Azure Verified Modules. Native Bicep is allowed only when no suitable maintained AVM preserves the required contract, and each fallback must be documented.
**Why:** User correction establishing the mandatory Azure infrastructure implementation policy and its explicit exception process.

### 2026-07-27T08:47:25.103+02:00: Decouple legacy Blob role cleanup from azd deployment
**By:** Copilot
**What:** The account-scoped legacy `Storage Blob Data Contributor` assignment is retired only by the explicit `infra/scripts/retire_legacy_storage_blob_role.py` maintenance action after deployment. It is no longer an `azure.yaml` postprovision hook. The container-scoped assignment remains the required private Blob route and is created by Bicep.
**Why:** RBAC enumeration and deletion require separate operator permissions, so coupling cleanup to `azd up` made otherwise successful application deployments fail. The maintenance script remains fail-closed by deleting only one verified direct legacy assignment after verifying exactly one direct container assignment.

### 2026-07-27T08:47:25.103+02:00: Postprovision Azure CLI portability and failure policy
**By:** Tank
**What:** Resolve Azure CLI with `shutil.which("az")` and then `shutil.which("az.cmd")`; execute the resolved absolute path using an argument list with `shell=False` (the `subprocess` default). If Azure CLI is absent or cannot be started, the `azd` postprovision hook fails with an actionable, non-secret-bearing error.
**Why:** RBAC migration postprovision hooks require Azure CLI. A successful no-op could silently preserve the retired account-scoped `Storage Blob Data Contributor` assignment and weaken least privilege; failing before deletion leaves existing assignments intact for safe retry.

### 2026-07-27T08:47:25.103+02:00: Private app azd deployment target
**By:** Tank
**What:** Tag only `ca-fc-${resourceToken}-pvt` with `azd-service-name: web`; leave the original Container App fully provisioned without that tag as the manual rollback target. The private environment is external and its app has external ingress; this moves only the `azd` image-deployment target.
**Why:** `azd` discovers Container Apps by service tag. Two tagged apps make publish-web ambiguous, while the VNet-integrated private app is the one with private Blob reachability. Product Owner approval remains required for any external traffic or domain change.

### 2026-07-27T08:47:25.103+02:00: Private Container App naming
**By:** Tank
**What:** Name the private Container App `ca-fc-${resourceToken}-pvt`. The private managed-environment name remains unchanged because its current 38-character deployment name is within the 60-character managed-environment limit.
**Why:** Container App names are limited to 32 characters. The lower-case 13-character `uniqueString` resource token keeps the name deterministic and unique; for `nrp2z4rl3jd32`, the name is `ca-fc-nrp2z4rl3jd32-pvt` (23 characters).

### 2026-07-27T08:47:25.103+02:00: Card-layout visual contract for issue #11
**By:** Benoit (via Squad Coordinator)
**What:** Provider-backed generation now requests a portrait 1024x1536 fantasy trading-card layout through `build_card_prompt(title, description)`: ornate frame, top title banner, central art, and bottom stats/description area. The `ImageGenerator` port contract is `generate(title, prompt)`.
**Why:** Issue #11 requires generated images to look like fantasy trading cards rather than square subject illustrations, and the explicit prompt/port contract keeps providers, tests, and adapters aligned.

### 2026-07-27T14:24:13+02:00: PR-environment Phase 1 deterministic naming contract (#16) (consolidated)
**By:** Tank, Fact Checker, Switch, Morpheus
**What:** The authoritative Phase 1 CI/platform naming contract lives in `infra/scripts/`: `pr-{number}-{slug}-{hash8}`, where `hash8` is the first eight hexadecimal characters of SHA-256 over the pinned canonical input `owner/repo|prNumber|slug`. `compute_names()` produces Azure-safe derived names and the preflight stays pure with concurrency counts supplied as inputs. Container App names are enforced as 2–32 lowercase alphanumeric-or-hyphen characters that start with a letter and end with an alphanumeric character; this closes a design-doc omission. Switch approved the implementation and added seven boundary/regression tests.

**Why:** Placement matches the repository's CI/platform-tooling convention and makes naming deterministic, testable, and fail-loud before Azure provisioning. The design document's worked example on `bmoussaud-glowing-broccoli` is not reproducible: canonical `bmoussaud/squad-workshop|14|render-card-layout` yields `4c32c628`, not `4717e5bb`. The branch owner must correct the document and its derived examples before that branch merges; code must retain the stated algorithm rather than conform to the erroneous example.

### 2026-07-27T14:24:13+02:00: PR-environment Bicep naming seam assigned to Phase 3 (#15)
**By:** Morpheus
**What:** For PR environments, `infra/web.bicep` must consume precomputed `containerAppName`, `storageAccountName`, and `containerAppsEnvironmentName` parameters supplied by the Phase 3 workflow. It must not reconstruct names from `environmentName` or `resourceToken`. Phase 2 left these names unconsumed; its `ca-fantasy-cards-${environmentName}` construction reaches 50 characters for the PR #14 example and exceeds the 32-character Container App limit. Teardown/janitor work must key on immutable `pr-number` tags rather than a slug-derived name to tolerate branch renames.

**Why:** Tank's names are correct but currently unused by Bicep. Parameterizing the Phase 1-to-Phase 3 seam fixes the deploy-time overflow without reopening merged Phase 2 work, and immutable tags prevent branch-renaming orphan risks.

### 2026-07-27T14:24:13+02:00: PR preflight credential and Foundry safety gates (#16) (consolidated)
**By:** Rai, Morpheus
**What:** The credential trust boundary accepts only strict booleans and fails closed: malformed `is_fork` or `is_draft` values and missing/non-empty-invalid repository signals block before any later draft or cap check. Foundry use requires explicit strict-boolean `requires_foundry` and an explicit approved `foundry_authorized` signal; authorization never waives the maximum one Foundry environment cap. Printable CLI output excludes raw repository input and sanitizes control characters from error output.

**Why:** A falsey-but-ambiguous GitHub Actions signal must never allow a fork to reach Azure credentials. Foundry incurs privileged/cost-sensitive provisioning and needs both authorization and the independent capacity limit. PR-controlled branches and repositories are log-injection inputs, so logs must not echo them unsafely.

### 2026-07-27T14:24:13+02:00: Reviewer rejection protocol completed for #16 preflight
**By:** Rai, Morpheus
**What:** Rai issued a 🔴 RED review for the trust-boundary, Foundry-gate, and output-safety defects. Tank was then locked out of revision, and Morpheus produced the independent remediation. Rai empirically re-reviewed it 🟢 GREEN; the final suite passed 148 tests.

**Why:** The rejected preflight controls Azure credential access. The independent-author lockout and final reviewer re-approval ensure the remediation was not self-certified by the rejected implementation author.

### 2026-07-27T09:42:54.356+02:00: Per-PR ephemeral Azure environments (consolidated)
**By:** Morpheus, Tank
**What:** Use deterministic per-PR Azure environment names derived from PR number plus a sanitized meaningful title slug, with a stable hash suffix for Azure uniqueness and length safety (for example, `pr-14-render-card-layout-4717e5bb`). The MVP default is a trusted same-repo app-tier ephemeral deployment (Container Apps, Storage/artifacts, identity, ACR, monitoring, budget/alerts, and private Blob path as needed) bound to a shared, pre-approved Foundry account/project/model deployment. GitHub Actions should deploy on PR open/reopen/synchronize with OIDC, `azd provision`/`azd deploy`, PR-number concurrency, tags carrying PR/branch/owner/created/expires/environment-type metadata, and a PR comment with the app URL. Teardown runs on PR close/merge through `azd down --purge`, with a scheduled TTL janitor for orphaned tagged resource groups. Full-stack per-PR Foundry/model provisioning is an exception for Foundry, identity/RBAC, model deployment, regional, safety, or provider-contract changes and requires GitHub Environment approval, quota/cost preflight, budget acknowledgement, and automatic teardown. Enforce hard concurrency limits initially: no more than 3 app-tier environments and 1 cost-bearing Foundry environment until live cost/quota data supports more. Fork PRs run build/test only unless a trusted maintainer explicitly approves Azure credential exposure after reviewing the code. Post-deploy hooks should include health checks and a gated, sanitized live Foundry image-generation validation handoff for Switch/Neo tied to issue #4 and the issue #11 card-layout follow-up.
**Why:** Per-PR review environments improve validation without bypassing existing approval boundaries for scarce, billable `gpt-image-2` capacity. App-tier ephemerals provide isolated review surfaces while shared Foundry binding controls quota, budget, security, and model-capacity blast radius. Approval gates, concurrency caps, TTL teardown, and fork restrictions preserve least privilege and cost control, while the validation hook keeps live image-generation evidence explicit and sanitized.

### 2026-07-27T14:44:52+02:00: fix/9 relevance review
**By:** Switch
**What:** `fix/9-private-blob-artifact` should not be rebased as a branch. Its final tree for the #9 fix is already on `origin/main` through squash commit `0775c47` (`Fix #9: artifact_unavailable — add private Blob route for card generation (#12)`), and `git diff --exit-code 0775c47 fix/9-private-blob-artifact -- .squad/decisions/inbox docs/design/azure-deployment.md infra/foundry.bicep infra/main.bicep infra/scripts/retire_legacy_storage_blob_role.py infra/web.bicep tests/test_deployment_contract.py tests/test_retire_legacy_storage_blob_role.py tests/test_web_acceptance.py` is clean. Later main commits `11fe807`/`fef80f2` reworked only the ACR/Foundry deployment surface for shared per-PR environments; applying raw fix/9 would regress that conditional model.
**Why:** Main already contains the private Blob VNet/private-endpoint/private-DNS path, private Container App azd target, safe private app name, container-scoped Blob RBAC, manual legacy-RBAC retirement script/tests, deployment-contract coverage, and artifact-unavailable acceptance coverage. The only actionable follow-up is documentation/test augmentation for the new `deployAcr=false`/`deployFoundry=false` shared-resource paths; do not cherry-pick from fix/9.

### 2026-07-27T14:44:52+02:00: Verify squash-merged branch trees before merge cleanup
**By:** Tank
**What:** Treat an apparently ahead stale branch as potentially already integrated when the project used squash merge. Before attempting a merge or rebase, compare the branch tree to the squash commit on `origin/main`; if the trees match and the squash commit is an ancestor of `origin/main`, delete the stale branch instead of merging it.
**Why:** `fix/9-private-blob-artifact` showed as 8 commits ahead because squash merge changed commit SHAs, but its tree exactly matched main commit `0775c47`. Attempting to merge the stale branch produced phantom conflicts against newer Bicep rewrites even though no fix/9 content needed to be carried forward.

### 2026-07-27T16:58:24.269+02:00: Relax CI ownership gate — branch name is convention, issue-closure stays a hard gate
**By:** Tank
**What:** In `.github/workflows/ci.yml`, the "Validate pull request ownership" step no longer fails on non-conforming head-branch names. The `squad/{issue-number}-{kebab-case-slug}` pattern is now a convention (emitted as `::notice::` when unmatched), not a gate. The requirement that the PR body close exactly one issue remains a hard failure. The branch↔issue cross-check is kept **conditionally**: it runs only when the branch matches the convention, so conforming branches still get the guarantee while app-generated worktree names (e.g. `bmoussaud-musical-spork`) pass.
**Why:** The Copilot app generates worktree branch names that can never satisfy the regex, so every app-authored PR failed the gate at creation and needed a manual branch rename (see #25, PR #24). Relaxing the branch check requires no coordination with app naming; keeping issue-closure strict preserves the half of the gate that carries real value. Body is attacker-controlled on fork PRs and is passed via `env:` and read as `"$BODY"` (no `${{ }}` interpolation into `run:`) — injection-safe; this was already correct and was preserved.

### 2026-07-27T17:14:24.871+02:00: PR-environment Bicep name parameterization contract (#15, work item A)

**By:** Tank

**What:** `infra/web.bicep` no longer constructs its resource names from `environmentName`/`resourceToken`. `containerAppName`, `containerAppsEnvironmentName`, `storageAccountName`, and the private `virtualNetworkName` are now parameters on both `web.bicep` and `main.bicep`, wired in `main.bicepparam` via `readEnvironmentVariable(...) , '')`. Each defaults to `''`; when empty the template falls back to the exact pre-existing dev-derived value, so `dev` deploys unchanged (verified: with only `AZURE_ENV_NAME=dev` set, all four resolve to `''`). The authoritative CLI→env-var mapping is `BICEPPARAM_ENV_VARS` in `infra/scripts/pr_environment_names.py`, and `pr_environment_names.py --format envvars` emits `NAME=value` lines ready for `$GITHUB_ENV`:

| naming key | env var | Bicep param |
| --- | --- | --- |
| `environment_name` | `AZURE_ENV_NAME` | `environmentName` |
| `container_app` | `CONTAINER_APP_NAME` | `containerAppName` |
| `managed_environment` | `CONTAINER_APPS_ENVIRONMENT_NAME` | `containerAppsEnvironmentName` |
| `storage_account` | `STORAGE_ACCOUNT_NAME` | `storageAccountName` |
| `virtual_network` | `VIRTUAL_NETWORK_NAME` | `virtualNetworkName` |
| `application_insights` | `APPLICATION_INSIGHTS_NAME` | `applicationInsightsName` |

The naming module gained a bounded `virtual_network` name (anchored to the compacted `managed_environment`, so ≤45 chars, never overflowing the 64-char VNet limit) and a `--format envvars` emitter.

**Why:** Phase 1's names were consumed by nothing; `web.bicep` would build `ca-fantasy-cards-pr-26-relax-ci-ownership-gate-8ba70a79` (55 chars vs 32 limit) and `vnet-fantasy-cards-...-private` (65 vs 64), failing `azd provision` on the first PR. Parameterizing the Phase 1→Phase 3 seam fixes the overflow without reopening merged Phase 2 work and keeps the Python module the single source of truth for name shapes. The `virtual_network` overflow (65 chars) was a genuine bug beyond the three names the seam decision named; the other private names are safe by derivation. For work item B (the workflow): export the `--format envvars` block to `$GITHUB_ENV` before `azd provision`. Identity params are deliberately NOT in this contract — one `managed_identity` token does not map onto two identities — so B owns identity-name wiring.

### 2026-07-27T17:14:24.871+02:00: PR smoke-test script retry contract (#15, item C)
**By:** Trinity
**What:** Added `infra/scripts/pr_smoke_test.py`, a stdlib-only post-deploy smoke test the Phase 3 workflow calls after `azd deploy`. It polls `GET /health/live` then `GET /health/ready` with bounded exponential backoff against one shared hard deadline, and emits a machine-readable verdict.

CLI contract: Args: `--base-url` (required, must be http/https), `--deadline-seconds` (default 180), `--request-timeout-seconds` (default 10), `--initial-backoff-seconds` (1.0), `--max-backoff-seconds` (15.0), `--backoff-multiplier` (2.0), `--format {env,json}` (default env). Output keys: `passed`, `reason_code`, `message`, `base_url`, `elapsed_seconds`, `total_attempts`, `live_healthy`, `live_status`, `live_attempts`, `live_reason`, `ready_healthy`, `ready_status`, `ready_attempts`, `ready_reason`. Exit codes: 0 = pass, 1 = smoke failure, 2 = usage/config error.

Retry policy: RETRY on connection/timeout errors and HTTP `408, 429, 502, 503, 504`. FAIL FAST on `404`, other `4xx`, `500`, and `200` with wrong JSON body. TLS verification always on; response bodies truncated + control-character-stripped before any log output.

**Why:** Cold-started Container Apps fail their first probes; retrying only transient statuses with a hard deadline gives a reliable verdict without burning CI time on non-transient answers. Scope was the script only; no Bicep, workflow, or app code was touched.

### 2026-07-27T20:05:43+02:00: Phase 3 PR-environment seam review — APPROVE WITH CHANGES (#15)
**By:** Morpheus (architecture/contract review)
**Reviewed:** commits `5bdc904` (item A, Tank), `3cc3d16` (item C, Trinity), `e0d2d64` (item B, salvaged/Tank)

**What:** The Phase 1→Phase 3 Bicep naming seam is now correctly closed. `infra/web.bicep` no longer reconstructs `containerAppName`, `containerAppsEnvironmentName`, `storageAccountName`, or the private `virtualNetworkName` from `environmentName`/`resourceToken`; all four are now parameters threaded from `main.bicepparam` and emitted by `pr_environment_names.py --format envvars`. Every empty-string fallback reproduces the exact pre-existing dev value. Tank's third overflow claim (`privateVirtualNetworkName` at 65 chars vs the 64-char VNet limit) is verified real and fixed. The identity mapping is resolved correctly: both `PLATFORM_IDENTITY_NAME` and `APPLICATION_IDENTITY_NAME` derive from the bounded `CONTAINER_APPS_ENVIRONMENT_NAME` with distinct `-plat`/`-app` suffixes. The env-var contract is closed end to end: all six emitted keys are read by `main.bicepparam`; nothing is emitted-but-unused or read-but-unemitted. RG tagging (all 8 tags incl. the Phase-4-critical immutable `pr-number`) is correctly placed in the workflow. `azd provision` then `azd deploy` are separate steps; no `azd up`.

**REQUIRED CHANGE (blocking, owner: Trinity):** The "Resolve app URL" step resolves the smoke-test FQDN from `$CONTAINER_APP_NAME` — the *public* container app. But `azd-service-name: 'web'` is on the *private* container app, so `azd deploy` pushes the real image only there; the public app keeps `containerapps-helloworld:latest`, which serves no `/health/*`. Fix: resolve the URL from `azd env get-value SERVICE_WEB_URI` (already `https://<fqdn>`), not `$CONTAINER_APP_NAME`.

**Why:** The seam fix and its dev backward-compat are sound and merge-safe. The single wiring defect is exactly the kind of contract mismatch that only surfaces on the first real PR deploy, so it must be fixed before merge.

**Non-blocking notes:** (1) App-tier concurrency cap counts RGs by tag, but tags are applied only after `azd provision`, so two simultaneous first-time PRs can both pass the cap before either tags — best-effort, acceptable for Phase 3. (2) `privateContainerAppsEnvironmentName` = bounded token + `-private` is safe only because long PR env names compact the managed-environment token to ~13 chars.

### 2026-07-27T20:04:31+02:00: Switch — Phase 3 (#15) test-quality review: APPROVE WITH CHANGES
**By:** Switch (Quality Engineer)
**Scope:** Test quality only for commits `5bdc904` (naming/Bicep, Tank), `3cc3d16` (smoke test, Trinity), `e0d2d64` (PR-deploy workflow + `pr_preflight` CLI, salvaged/unreviewed).

**Verdict:** APPROVE WITH CHANGES — changes made and committed (`a94f973`); full suite 192 OK (+6). Three reviewed modules run 111 tests in ~0.05s: fully hermetic, no real sleeps or network.

**What (changes made):**
- `pr_preflight._parse_count` used `str.isdigit()` then `int()` — crashes on some Unicode "digits" (`²`) and silently accepts others (Arabic-Indic `٥`→5). Hardened to ASCII-only (fail closed to `-1`). LOW severity but a claimed fail-closed path that crashed.
- Added hostile-input matrix for both parsers, a usage exit-2 assertion, and an explicit PROCEED≠SKIP distinctness check.
- Smoke retry set `{408,429,502,503,504}` was pinned only by a single `503` case — hand mutation shrinking it survived the suite. Added per-status retry-then-recover and per-status fail-fast coverage.
- `virtual_network` name is length-bounded by test at the boundary with adversarial inputs; mutation re-anchoring it caught.
- No pre-existing test was modified in any of the three commits.

**Why:** The suite passing after a salvage commit is not evidence of good tests. Two coverage gaps (one on a fail-closed security-adjacent parser) were only found by hand mutation testing; both are now closed with regression tests committed to `bmoussaud-musical-spork` (`a94f973`, references #15).

### 2026-07-27: PR-environment URL resolution and smoke-failure comment surfacing (#15, fix pass)
**By:** Trinity
**What:**
1. **Resolved the app URL from the canonical azd output**, not by container-app name. Uses `azd env get-value SERVICE_WEB_URI` (`main.bicep` → `web.bicep serviceUri`). It already yields a full `https://<fqdn>`, so no scheme is prepended. Dropped `az containerapp show` and the resource-group lookup.
2. **Fails loudly on an empty/invalid URL.** A `case` guard requires the value to start with `https://`; otherwise emits `::error::` and `exit 1`. `set -euo pipefail` alone does not catch an empty-but-zero-exit `get-value`.
3. **Surfaced smoke-failure detail in the PR comment (Rai A1).** A smoke failure fails the deploy job, so the old code always rendered "Deployment did not complete", making the smoke-failed branch dead code. Now: healthy only when `deployOk && smokePassed`; if smoke ran and did not pass, show the real smoke message; otherwise "did not complete".

**Scope deliberately untouched:** `infra/scripts/pr_smoke_test.py`, all Bicep, `pr_preflight.py`. No new `${{ github.event.* }}` added inside `run:` blocks. Verified statically: YAML parses, 192 tests OK. UNPROVEN until a real Azure run: the actual `azd deploy` → `SERVICE_WEB_URI` → smoke path.

**Why:** `azd-service-name: 'web'` is on the private container app so `azd deploy` ships our image only there; the public app keeps `containerapps-helloworld:latest` and serves no `/health/*`. The old URL-resolution step queried the wrong (public) app, guaranteeing 404 on every real deploy — a false smoke failure despite a good deploy. `set -euo pipefail` does not catch empty-but-zero-exit, so an explicit guard is required.

### 2026-07-27T21:07:06+02:00: TTL reaper decision engine (Phase 4, #20, item B)
**By:** Trinity
**What:** Added `infra/scripts/pr_env_reaper.py` + `tests/test_pr_env_reaper.py` (53 tests). Pure stdlib decision engine that selects which per-PR ephemeral Azure resource groups the scheduled janitor may delete; performs no Azure calls. Strictly allowlist-based: reap only when `tags` is an object AND `tags.ephemeral == "true"` (exact lowercase) AND `environment-type == "pr-app"` AND valid numeric `pr-number` AND (`expires-at` aware+strictly-past OR `pr-number` in `--closed-pr-numbers`). Immediate delete on expiry (no grace period; resolves design-doc L272). Malformed expiry is KEEP (`malformed_expiry`), never "expired long ago"; naive timestamps rejected before comparison so no `TypeError`. Closed-PR trigger checked before expiry. Exit 0 on any successful evaluation; `MALFORMED_INPUT_EXIT_CODE = 3` for bad JSON/non-array/naive `--now`; usage stays 2. Names sanitized via `_sanitize_log`. Reason codes — reap: `expired`, `orphaned_closed_pr`; keep: `malformed_group`, `no_tags`, `not_ephemeral`, `wrong_environment_type`, `missing_pr_number`, `malformed_pr_number`, `malformed_expiry`, `not_yet_expired`. Did NOT touch workflows (Tank item A), Bicep, `pr_preflight`, `pr_smoke_test`, `pr_environment_names`. Full suite: 245 OK (192 baseline + 53).
**Why:** The janitor workflow needs a provably safe decision engine that can be proven correct by unit tests alone. Strictly allowlist-based means all ambiguous/malformed input defaults to KEEP. Pure stdlib + injected clock makes it fully hermetic and testable.

### 2026-07-27T21:04:25+02:00: PR-env close-time teardown + daily TTL janitor (Phase 4, #20, item A)
**By:** Tank
**What:** Added `.github/workflows/pr-environment-teardown.yml` (`pull_request: closed`, both merge+abandon) and `.github/workflows/pr-environment-janitor.yml` (`schedule` daily + `workflow_dispatch` with `dry_run` input).

Key decisions:
1. **Teardown mechanism = tag-scoped `az group delete`, not `azd down --purge`.** `azd down` requires azd environment state that does not exist on a fresh runner. PR stacks set `DEPLOY_FOUNDRY=false` and contain no per-PR Key Vault — the only resource types `--purge` reclaims — so `az group delete` is functionally equivalent.
2. **Separate concurrency group `pr-azure-teardown-<n>` with `cancel-in-progress: false`.** The deploy workflow's `cancel-in-progress: true` (group `pr-azure-<n>`) can never cancel an in-flight teardown; `cancel-in-progress: false` prevents a duplicate closed event from cancelling a teardown already in progress.
3. **Idempotency:** empty tag-match set is the expected no-op (exit 0). Real `az group delete` failures fail the run; only "already gone" treated as success.
4. **Fork safety:** teardown job skipped at job level (`head.repo.fork == false`).
5. **Janitor decision is the reaper's, never bash.** Authoritative reap/keep verdict comes from `infra/scripts/pr_env_reaper.py --format env`; delete loop iterates strictly over `reap_names`. `--now` injected explicitly; closed PRs passed via `--closed-pr-numbers`.
6. **Dry-run:** `workflow_dispatch` input `dry_run=true` reports without deleting.

Security: no `github.event.*` interpolated into `run:` blocks; third-party actions SHA-pinned; least-privilege permissions per job.
**Why:** Completing the PR-environment lifecycle requires both a guaranteed close-time cleanup and a backstop janitor for orphaned environments. The azd-state-free `az group delete` approach is the only reliable teardown on a fresh runner. Separate concurrency ensures cleanup is never interrupted by an obsolete deploy — per design doc L114.

### 2026-07-27: Phase 4 teardown/janitor security review — 🟢 GREEN (#20)
**By:** Rai (RAI/security reviewer)
**Artifacts reviewed:** `infra/scripts/pr_env_reaper.py` (Trinity, 5677e3f); `.github/workflows/pr-environment-teardown.yml` + `pr-environment-janitor.yml` (Tank, e6d2b2e)
**What:** Ratified Phase 4 artifacts as safe to ship. Proved the reaper's allowlist adversarially by running it against crafted hostile JSON: odd casing, whitespace, `tags:null`, tags-as-list, JSON boolean `true`, tz-naive expiry, non-ASCII pr-number, garbage closed-PR tokens, embedded newline in name — every non-ephemeral / ambiguous case is KEPT. Confirmed the identity gates run BEFORE any expiry/closed check, so a stale `expires-at` on a shared/production RG can never trigger a delete. Malformed input exits 3 → `set -e`+`pipefail` in janitor → run fails → no delete. Accepted Tank's `az group delete` deviation: PR stacks create no Key Vault and no Cognitive Services account, so `--purge` reclaims nothing. Two non-blocking advisories raised (both fixed by Tank in the advisory pass): (1) teardown comment overstated PR_NUMBER validation; (2) `az group list` failure reported as false no-op.
**Why:** When an unattended scheduled deleter is the artifact under review, the reviewer must prove the allowlist rather than accept it — empirical hostile-input runs are what convert the "allowlist-based" claim into evidence.

### 2026-07-27: Phase 4 TTL reaper test review — APPROVE WITH CHANGES (#20)
**By:** Switch (QA/test)
**What:** Reviewed `infra/scripts/pr_env_reaper.py` + `tests/test_pr_env_reaper.py` (commit 5677e3f, Trinity). Applied 16 mutations: all 8 of Trinity's claimed-caught mutations verified empirically caught; of 8 additional mutations, 7 caught and 1 survived. The surviving mutation: setting `MALFORMED_INPUT_EXIT_CODE = 0` — every malformed-input test asserted `code == reaper.MALFORMED_INPUT_EXIT_CODE`, so the assertion moved with the constant and the "never exit 0 on garbage" invariant was not pinned to a concrete non-zero literal. Fix: added `test_malformed_input_exit_code_is_a_nonzero_literal` pinning the constant to `3` and asserting a real malformed run returns non-zero literal `3`. Catastrophe guard confirmed: shared-foundry with stale-2000 `expires-at` is KEPT (identity gates run before expiry). Tests fully hermetic (no wall-clock/network/sleep). 245 → 246 tests.
**Why:** The exit code carries a real security guarantee relied upon by Rai's GREEN verdict (malformed input fails the janitor run, preventing deletion). Nothing in the test suite actually pinned that guarantee to a concrete value until this change.

### 2026-07-27: Teardown must fail loudly on query failure, not report a false no-op (#20)
**By:** Tank
**What:** Fixed two non-blocking advisories in `.github/workflows/pr-environment-teardown.yml`. Advisory 2 (silent skip): `az group list` ran under `set -uo pipefail` (no `-e`); a failed query left `matches` empty and the idempotency branch reported a false `status=noop` exit 0, leaking the resource group. Fix: capture the `az group list` exit status explicitly (`matches="$(...)" || query_rc=$?`) and `exit 1` when `query_rc != 0`; empty-but-successful result still no-ops with `status=noop` exit 0. Advisory 1 (comment overstatement): added real `^[0-9]+$` guard on `PR_NUMBER` before it reaches `--query` rather than softening the comment — makes the "validated integer" claim true. Proved via bash: failing query → exit 1 (loud); empty-but-successful query → `status=noop`, exit 0; guard accepts `42`, rejects `42; rm -rf` and empty string. Suite: 246 tests OK.
**Why:** A silently-false no-op on an Azure query failure leaves a resource group alive and billing for up to 24 hours (until the janitor next runs), while showing a green run — directly contrary to the purpose of Phase 4. An actual `^[0-9]+$` guard removes reliance on the reader knowing GitHub's payload schema.

### 2026-07-27: Azure OIDC federation and repo configuration for per-PR environments (#29)
**By:** Tank
**What:** Configured the secretless Azure/GitHub identity path for PR environment workflows: Entra app registration `squad-workshop-pr-envs`, one federated credential for GitHub environment `azure-pr-app`, subscription-scope Contributor plus Role Based Access Control Administrator, and the required repository Actions variables. The GitHub environment intentionally has no reviewer or branch gate so automated teardown and janitor runs are not blocked. PR #30 still fails preflight because its branch name is invalid for the naming gate; the shared ACR variable is populated, so that is not a configuration gap.
**Why:** Per-PR environments create fresh resource groups and Bicep creates role assignments inside them, so subscription-scope deploy identity and RBAC assignment rights are required. OIDC avoids client secrets, and the branch-name failure preserves the fail-closed preflight contract.

### 2026-07-28T08:22:20+02:00: Phase 5 per-PR cost tagging and observability (#18) (consolidated)
**By:** Trinity, Tank, Rai, Switch
**What:** Phase 5 keeps the existing RG-scoped budget implementation in `infra/web.bicep` (Actual 50/80/100 alerts) and adds deterministic per-PR observability/resource identity. `PrEnvironmentNames` now includes a fail-closed `log_analytics` name (Azure 4-63 rule, hash8 preserved) emitted as `LOG_ANALYTICS_WORKSPACE_NAME` through `BICEPPARAM_ENV_VARS`. Child resources receive only the stable identity tag subset `ephemeral`, `pr-number`, `author`, and `created-at` through empty-defaulted Bicep params; `expires-at` remains RG-only. The redundant guarded workflow export step was removed, leaving `--format envvars` → `BICEPPARAM_ENV_VARS` → `main.bicepparam` as the single load-bearing path, now pinned by a test that every emitted env var is read by `main.bicepparam`.
**Why:** Per-PR Log Analytics names prevent cross-PR collision with the dev default. Stable child tags improve cost and ownership attribution without creating a second, drifting TTL source of truth. Rai rated the widened child tags YELLOW/advisory-only because deletion tools read RG tags and require both `ephemeral=true` and `environment-type=pr-app`, while child tags deliberately omit `environment-type`. Switch mutation-tested the naming path (7/7 mutations caught) and closed the env-var wiring regression gap. Follow-ups: owner acknowledgement for durable `author`/`created-at` child metadata, and a separate hardening item for pre-existing non-secure `APPLICATIONINSIGHTS_CONNECTION_STRING` output.

### 2026-07-28T09:03:21Z: Phase 6 Foundry exception gate and live validation contract (#17) (consolidated)
**By:** Trinity, Tank, Switch, Rai, Fact Checker
**What:** Phase 6 establishes a fail-closed Foundry exception gate for PR environments:
- Foundry provisioning is authorized by approval, never by detection. `DEPLOY_FOUNDRY` derives solely from the `foundry_exception` environment approval; detection only requests review. A detection false positive must cost a prompt, never a billable Foundry account.
- Detection is a triage signal, not a security perimeter. Because `pull_request` checks out PR-controlled code, path/content detection can never be a complete boundary. Enforcement lives in deploy-time integrity assertions and trusted-context job guards.
- Detection asymmetry is intentional: conservative means matching less. A false negative deploys against shared Foundry with `DEPLOY_FOUNDRY=false` (cheap, safe, documented default), while a false positive provisions billable Foundry and saturates the cap.
- Privileged jobs re-assert the non-forgeable trusted-event subset: `fork == false`, `head.repo.full_name == github.repository`, and `draft == false` are job-level preconditions on `foundry_exception`, `deploy`, `live_foundry_validation`, and `comment`, in addition to `pr_preflight.py` gates. This duplication is deliberate because the script is PR-supplied; do not clean it up.
- Gate order in `pr_preflight.py` is load-bearing. Fork is gate #1 and Foundry is gate #6. The deploy condition permits the Foundry path without `decision == 'proceed'`, which is safe only because `foundry_unauthorized` is unreachable until the five earlier gates pass. `PreflightFoundryGateOrderTests` pins this invariant.
- `environment-type=pr-foundry` resource groups are deleted by close-time teardown for the exact PR number, never by TTL reaping. The TTL janitor may warn on expired, malformed, or closed-PR `pr-foundry` groups but auto-deletes only `pr-app` groups.
- Accepted Rai 🟡 risks shipped: PR-controlled preflight/detector remains until base-ref execution is implemented; a same-repo collaborator can still mutate workflow/IaC; Foundry approval is self-approval/cost acknowledgement in a single-collaborator repo, not independent review; repo `vars` for client/tenant IDs are readable by fork runs and must remain identifiers only, with secrets kept out of `vars`.

Detector contract: `requires:foundry` is the explicit opt-in label for the Foundry-per-PR approval gate and `validate:live-foundry` is the independent live-validation label. The exact Foundry path allowlist is `infra/foundry.bicep`, `infra/modules/shared-foundry-rbac.bicep`, `infra/main.bicep`, `infra/main.bicepparam`, `src/fantasy_cards/adapters.py`, `tests/test_foundry_adapter.py`, and `tests/test_card_prompt_contract.py`; broader app-tier files are deliberately excluded unless authors add the explicit label.

Testing/review outcome: Switch approved with changes after mutation testing caught 11/11 requested mutations, including exact/case-sensitive path matching, literal label matching, and the preflight gate-order invariant. Rai moved from 🔴 RED twice to 🟡 YELLOW after deploy-time integrity checks and trusted-context job guards were added. Fact Checker verified the fork-OIDC path stops at GitHub's read-only fork token/no `id-token` elevation boundary, making the prior finding defense-in-depth rather than live credential exfiltration.
**Why:** Foundry/model provisioning is scarce and billable, so approval must be the only provisioning authority. PR-controlled detection can help route review but cannot enforce cost/security boundaries. Trusted job-level guards, fail-closed `DEPLOY_FOUNDRY=false`, deploy-time IaC switch integrity checks, explicit close-time teardown, and pinned tests make the remaining Phase 6 behavior intentional and reviewable.

### 2026-07-28: Keep PR-environment branch convention, surface blocked diagnostics
**By:** Tank
**What:** PR Azure Environment still requires branches that feed ephemeral Azure naming to match `squad/{issue}-{slug}`; workflow helper commands now capture and print non-zero diagnostic output before enforcing failures.
**Why:** `pr_preflight.py` exit 3 is a valid policy BLOCKED verdict, not a crash. Printing the verdict preserves the gate while making branch-name and cap failures self-diagnosing in Actions logs.

### 2026-07-28T12:01:41+02:00: PR Azure OIDC subject must use immutable owner/repository IDs (consolidated)
**By:** Tank, Fact Checker
**What:** The `azure-pr-app` Entra federated credential for this repository must match GitHub's emitted immutable subject exactly: `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`. PR #45 deploy and PR #44 teardown failures are Azure-side OIDC federation mismatches, not PR content or branch-derived behavior.
**Why:** Azure login fails before any provision/delete operation with AADSTS700213 when Entra cannot find an exact issuer/audience/subject match. Fact Checker verified the ID-qualified subject is expected for this repository because it was created after GitHub's 2026-07-15 immutable OIDC subject change; GitHub's OIDC customization API reports the same default `sub_claim_prefix`, and the subject was stable across observed runs. Do not broaden the credential; match the emitted subject case-sensitively.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction

### 2026-07-28T09:55:56+02:00: Dev Azure infrastructure deployment state corrected
**By:** status-summary session (requested by Benoit Moussaud (Product Owner))
**What:** Dev Azure infrastructure is deployed as of this session. The deployed dev resource group is `rg-fantasy-cards-dev-8f327f8c`, and `gpt-image-2-dev` succeeded. Prior recorded state that no Azure resources existed was stale.
**Why:** Tank's status-summary investigation found live deployed resources, contradicting prior shared state. The team must treat the dev stack as existing while Benoit's cost, geography, and content-filtering approval remains outstanding for future changes.

### 2026-07-28T09:55:56+02:00: CI exists but branch protection is not enabled
**By:** status-summary session (requested by Benoit Moussaud (Product Owner))
**What:** CI exists and runs tests on pull requests and pushes, but GitHub branch protection is not enabled; merges are currently ungated by required checks.
**Why:** Switch's status-summary investigation confirmed 253 tests pass locally and CI workflow coverage exists, while `gh` reports the branch is not protected. The team must not assume CI gates merges until branch protection is configured.

### 2026-07-28T10:05:06+02:00: Foundry approval gate closed for development only (#2) — SUPERSEDED by 2026-07-28T10:14:07+02:00 re-decision
**By:** Benoit Moussaud (Product Owner)
**What:** APPROVED FOR DEVELOPMENT ONLY and retroactively accepts the live dev stack in `rg-fantasy-cards-dev-8f327f8c`: Foundry account `AIServices/S0` in Sweden Central, deployment `gpt-image-2-dev`, model `gpt-image-2` version `2026-04-21`, `GlobalStandard`, capacity 1, provisioning state `Succeeded`. Benoit explicitly acknowledged (1) billable provisioning, (2) cross-geography processing from France Central to Sweden Central, (3) default content and abuse monitoring, and (4) the `swedencentral` / `GlobalStandard` / capacity-1 target. Production remains gated.
**Superseded by:** 2026-07-28T10:14:07+02:00 governance re-decision accepting non-EU inference processing for both dev and production after #39/fact-checker corrected the GlobalStandard routing premise. This original entry remains for audit trail only.
**Conditions:** Production approval requires follow-up issues #37 (user-facing notice), #36 (retention/deletion policy), #38 (likeness/IP/minors policy), and #39 (revalidate GlobalStandard routing) to be resolved. Issue #39 may invalidate the EU-only assumption underpinning this development approval.
**Why:** Tank confirmed the factual Azure state, spend, budget alerts, and live RAI policy (`Microsoft.DefaultV2` with Hate/Sexual/Violence/Selfharm blocking at Medium plus Jailbreak and Protected Material Text). Rai assessed the gate as 🟡 YELLOW: approve dev only, with the four production preconditions above.

### 2026-07-28: GlobalStandard is not EU-bound for Foundry inference
**By:** Tank
**What:** The current `gpt-image-2-dev` deployment uses `GlobalStandard`, and Microsoft documentation says Global deployment types may process prompts and responses in any geography/region where the relevant model is deployed. For `gpt-image-2`, official availability includes US regions as well as EU regions, so the deployment cannot be treated as EU-only for inference processing.
**Why:** Benoit's development approval in #2 was based on a France Central → Sweden Central/EU-only processing assumption. Stored data at rest remains in the customer-designated geography, but inference processing under `GlobalStandard` can leave the EU. Production should not use the current SKU for EU-only residency, and #2 should be revisited for the changed factual basis.

### 2026-07-28T10:14:07+02:00: GlobalStandard routing correction and Foundry re-decision (#39, #2)
**By:** Benoit Moussaud (Product Owner), informed by Tank and Fact Checker independent verification
**Supersedes:** `2026-07-28T10:05:06+02:00: Foundry approval gate closed for development only (#2)` for both scope and factual basis; that entry remains above as an audit record.
**What:** Benoit explicitly accepted non-EU inference processing for both development and production for the current Microsoft Foundry `gpt-image-2` path. The earlier approval was based on a false premise: that France Central application traffic to a Sweden Central Foundry resource using `GlobalStandard` meant EU-only inference processing. Corrected fact: Microsoft documents Global deployment types as eligible for processing in any Azure region/geography where the model is deployed; data at rest remains in the customer-designated geography, but prompts/responses for inference are globally routable under `GlobalStandard`. Live read-only Azure evidence confirmed the dev deployment is `gpt-image-2` version `2026-04-21` in Sweden Central on `GlobalStandard`, and current live availability for this subscription exposes `GlobalStandard` only for `gpt-image-2`; `DataZoneStandard` or regional `Standard` are not purchasable for this model in the current context. Where DataZone pricing exists, it carries an approximately 10% premium.
**How caught:** Tank revalidated issue #39 and Fact Checker independently checked the same EU-residency claim without seeing Tank's work. Both contradicted the EU-only premise. Fact Checker also verified the model/version/region claim, partially verified the documented content-filter behavior behind the `Microsoft.DefaultV2` name, and verified abuse-monitoring retention/human-review behavior.
**Evidence:** Microsoft deployment-type docs: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types (`Global` types: may be processed in any Azure region; `DataZone` types stay within the Microsoft-specified data zone; `Standard/Regional` stays in deployment region). Microsoft data/privacy docs: https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy (Global/DataZone affect location of prompt/response processing; stored data at rest remains in the customer-designated geography; prompts/completions are not used to train base models). Microsoft model availability docs: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure and https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability.
**Rationale accepted by Benoit:** EU-bound inference is not purchasable for `gpt-image-2` in this subscription/context. Constraining inference to the EU would mean abandoning the model. Only prompt text crosses the processing boundary; generated artifacts and project storage remain in France Central / customer-designated storage.
**Follow-through:** Issue #2 was reopened, corrected, re-decided, and closed again. Issue #39 was closed as resolved with risk accepted. Issue #37 scope changed: the user-facing notice must say inference processing may occur outside the EU; EU-only wording is now known false.
**Revisit triggers:** Reopen this decision if Microsoft makes `gpt-image-2` available under EU `DataZoneStandard` or regional `Standard` in the target subscription/regions, if the model/SKU/version changes, if production handles materially different prompt or personal/sensitive data categories, if customer/legal requirements require EU-only processing, if Microsoft changes Global/DataZone processing semantics or abuse-monitoring retention, or if a viable alternative model meets requirements with EU-bound inference.

### 2026-07-28T10:14:07+02:00: Parallel uncorrelated verification for governance facts
**By:** Scribe (process learning from Tank and Fact Checker)
**What:** For governance decisions involving compliance, data residency, safety gates, or billable/cloud approval, use independent parallel verification by at least two uncorrelated agents when the fact pattern is material and reversible cost or risk depends on it. The agents should not rely on each other's findings before reporting; Scribe/coordinator then reconciles convergent or conflicting evidence.
**Why:** Tank and Fact Checker independently caught a factual error in an already-signed-off Foundry governance decision: `GlobalStandard` was incorrectly treated as EU-only. The independent convergence provided enough confidence to reopen, correct, and re-decide issue #2 before production notice wording or approval gates propagated the false premise.

### 2026-07-28T11:41:20+02:00: Issue #41 accessible green palette revision
**By:** Neo
**What:** Independently revised the rejected green-background palette after Switch's accessibility rejection. The new palette uses `--paper: #e4f1df`, `--surface: #f7fcf4`, masthead `rgba(228, 241, 223, 0.96)`, result `#d8ecd2`, `--muted: #556052`, `--coral: #9e3a31`, `--gold: #7a5d16`, and shared border/line color `#697564`.
**Why:** Baseline original contrast was ink 14.36/15.65/13.91, muted 5.13/5.59/4.97, coral 4.13/4.50/4.00, gold 2.39/2.61/2.32 across paper/surface/result. Trinity's green regressed muted on result and all coral/gold surfaces: ink 13.67/15.13/12.47, muted 4.88/5.40/4.45, coral 3.93/4.35/3.58, gold 2.28/2.52/2.08. Neo's revised green keeps the page visibly sage-green and raises revised ratios to ink 13.61/15.31/12.78, muted 5.64/6.35/5.30, coral 5.78/6.50/5.43, gold 5.27/5.93/4.95, line/borders 4.15/4.66/3.89.
**Validation:** `python -m uv run python -m unittest discover -s tests` passed after updating the static CSS contract for the new hex values.

### 2026-07-28T11:36:33+02:00: Switch rejected issue #41 green-background revision
**By:** Switch
**What:** Reject Trinity's commit `d9b6e49` for issue #41 because the selected green palette fails WCAG contrast review. Trinity is locked out from revising this artifact; Neo owns the next visual/palette revision independently.
**Why:** Blocking contrast failures against the new green result/background colors include muted text `#68675f` on `#d2ead2` at 4.45:1 (<4.5), gold glyph `#c8972d` on `#d2ead2` at 2.08:1 (<3), and coral eyebrow `#c84d3f` below normal-text AA on `#dff3df`, `#f4fbf4`, and `#d2ead2`. Full suite rerun passed: 278 tests OK.

### 2026-07-28: Green background palette for issue #41
**By:** Trinity
**What:** Use `--paper: #dff3df` for the page background, `--surface: #f4fbf4` for the workspace, `rgba(223, 243, 223, 0.96)` for the masthead, and `#d2ead2` for the result pane.
**Why:** Product only specified the page green; these dependent values replace paper-matched warm neutrals with a coherent light green family while preserving readable contrast with existing text colors.

### 2026-07-28: PR environments use Consumption profile without dedicated capacity bounds
**By:** Tank
**What:** The Container Apps templates now map `workloadProfileType == 'Consumption'` to the built-in `Consumption` workload profile and omit dedicated `minimumCount`/`maximumCount`; non-Consumption profiles still use the `dedicated` profile with explicit bounds.
**Why:** PR workflow sets min count `0` deliberately for scale-to-zero cost control. ARM validates dedicated profile minimum counts as `>= 1`; using the Consumption profile preserves the PR cost intent instead of forcing always-on dedicated nodes.

### 2026-07-28: Bound PR AZURE_ENV_NAME for ARM deployment-name safety
**By:** Tank
**What:** `AZURE_ENV_NAME` for PR environments is capped at 40 characters while retaining `pr-{number}-` and the existing `hash8`; only the displayed slug token is truncated.
**Why:** ARM nested deployment names are limited to 64 chars. The longest module-name prefix currently present in `infra/` is `private-virtual-network-` (24 chars), so the shared environment token must be ≤40 chars to keep every `{module-prefix}-{AZURE_ENV_NAME}` deployment name valid.
**Scope:** The shared `pr_environment_names.py` helper is authoritative for preflight and deploy. Teardown and janitor remain tag-scoped by `pr-number` and do not derive resource names independently.

### 2026-07-28: Compact PR nested deployment names
**By:** Tank
**What:** Nested Bicep module deployment names use the compact PR Container Apps environment token when present instead of the full `AZURE_ENV_NAME`.
**Why:** ARM deployment names are capped at 64 chars; long PR slugs can fit Azure resource names via the naming module but still overflow nested deployment names when prefixed (`foundry-...`).

**Update:** The same 64-character ARM deployment-name cap also applies to child modules inside `foundry.bicep`. Foundry internals now use a deterministic compact `uniqueString` token for module deployment operation names; resource names are unchanged.

**Status:** Historical interim mitigation, superseded by the root-cause `AZURE_ENV_NAME` 40-character budget. Keep the 64-character module-deployment regression test as the durable guardrail.

### 2026-07-28: Add immutable GitHub OIDC credential for PR Azure environment
**By:** Tank
**What:** Added Entra federated credential `github-pr-app-environment-immutable` on `squad-workshop-pr-envs` for exact subject `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`.
**Why:** The repo uses GitHub's immutable OIDC subject format; the only existing credential was legacy `repo:bmoussaud/squad-workshop:environment:azure-pr-app`, causing AADSTS700213 in deploy, teardown, and janitor jobs using `azure-pr-app`.

### 2026-07-28T17:36:00+02:00: Markdown-aware PR ownership references
**By:** Switch
**What:** The CI ownership gate recognizes unique closing references only in genuine top-level Markdown prose. Code spans, fenced and indented code blocks, blockquotes, and Markdown tables are documentation or quotation and do not close issues. The gate remains fail-closed: exactly one unique issue is required. The PR body remains environment-backed and is never interpolated into the workflow run script.
**Why:** Plain-text matching counted documented syntax as issue closures and rejected valid PRs.
