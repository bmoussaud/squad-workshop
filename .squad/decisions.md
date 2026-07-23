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

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
