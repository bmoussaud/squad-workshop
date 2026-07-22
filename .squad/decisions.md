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

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
