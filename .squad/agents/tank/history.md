# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Summarized Learnings

Tank owns Azure platform, Bicep, deployment workflows, and independent repair work under reviewer lockout. Standing project rules: Azure resources are Bicep/AVM-first, deployments use `azd`, production hosting prefers Azure Container Apps, Foundry use remains gated by region/model/quota/capacity approval, and user-assigned managed identities should preserve least privilege.

Key retained history:
- 2026-07-22: Completed the independent final `gpt-image-2` and artifact-persistence revisions after Switch lockouts; Switch approved both after repository checks. Foundry endpoint/request-shape repairs preserved identity scope `https://ai.azure.com/.default`, bounded timeouts, zero retries, and safe 5xx handling.
- 2026-07-23: Helped prepare Foundry provisioning for Sweden Central but Azure creation remained explicitly approval-gated. Also participated in deployment/telemetry/private-Blob recovery work; policy-disabled Storage requires a separately approved private endpoint/DNS/VNet path before generation is fully healthy.
- 2026-07-27 #16/#25: Delivered deterministic PR-environment naming/preflight and relaxed the CI branch-name gate to advisory while keeping exact issue closure hard-fail. Names use `pr-{number}-{slug}-{hash8}`; the design-doc hash example remains known-wrong.
- 2026-07-27 #15: Parameterized Bicep names (`containerAppName`, `containerAppsEnvironmentName`, `storageAccountName`, `virtualNetworkName`) and env-var emission. Phase 3 was accepted after Trinity fixed the URL-resolution defect and Switch hardened tests.
- 2026-07-27 #20: Added close-time teardown and daily janitor workflows. Teardown uses tag-scoped `az group delete`, separate non-cancelling concurrency, fork skips, idempotent empty matches, and janitor delegates delete decisions to Trinity's `pr_env_reaper.py`. Later fixed Rai advisories so Azure query failures fail loudly and PR numbers are actually regex-validated.
- 2026-07-27 #29: Configured secretless Azure OIDC for PR environments: Entra app `squad-workshop-pr-envs`, one `azure-pr-app` federated credential, subscription-scope Contributor + RBAC Admin, GitHub environment, and repo variables. PR #30 remains blocked by branch-name preflight, not ACR config.
- 2026-07-28 #18: Verified budget alerts were already present. Added child-resource identity tags via empty-defaulted params and Bicep `union`; excluded `expires-at` from children; reported pre-existing non-secure Application Insights connection-string output. Coordinator removed the redundant observability export step because Trinity's envvars path is authoritative.

## Recent Updates

📌 Team update (2026-07-28T08:22:20+02:00): Phase 5/#18 accepted Tank's child-tagging and budget verification after coordinator correction. Child resources carry only stable identity tags (`ephemeral`, `pr-number`, `author`, `created-at`), never `expires-at`; RG budget alerts were already complete; the redundant guarded Log Analytics export step was removed so Trinity's `BICEPPARAM_ENV_VARS` path is the single source. — decided by Tank, corrected by coordinator, reviewed by Rai and Switch

📌 Team update (2026-07-27T14:44:52+02:00): Cancelled the stale merge path for `fix/9-private-blob-artifact` after Switch verified it had already been squash-merged to `origin/main` as `0775c47` with an identical tree. Cleaned up the obsolete fix/9 worktree/branch, its subset recovery/provisioning/testing worktrees and local branches, the zero-ahead Neo investigation worktree/branch, and the fully merged remote-only refs `copilot/status-per-env-issues`, `copilot/status-per-env-issues-again`, `squad/3-add-ci-validation-gates`, and `squad/19-per-pr-envs-phase2-bicep-azd`. Remote deletion used `gh api`; no `git push` was used.
- 2026-07-28 #17: Wired Phase 6 PR-environment Foundry scope detection, approval gating, post-login Foundry recheck, and opt-in `validate:live-foundry` validation evidence. Normal app-tier PRs remain automatic; Foundry-scoped PRs pause on `azure-foundry-provisioning` and pass `foundry_authorized=true` only after environment approval. Documented the real GitHub reviewer constraint: `bmoussaud` is the sole required reviewer; self-review prevention must stay disabled.
- 2026-07-28 #17 correction: Foundry exception RGs tagged `environment-type=pr-foundry` must have an explicit cap-release lifecycle. Close-time teardown is the right deletion path because PR closure is unambiguous; TTL janitor should surface but not auto-delete `pr-foundry` because inferred deletion of billable/scarce model resources is higher risk.
- 2026-07-28 #17 Rai RED fix: Treat Foundry path/label detection as triage, not a security perimeter, because PR head IaC is what `azd provision` deploys. `deployFoundry` now fails closed in Bicep defaults, PR `DEPLOY_FOUNDRY` is derived only from `azure-foundry-provisioning` approval success, and the workflow asserts the Foundry switch/wiring before provisioning.

📌 Team update (2026-07-28T09:03:21Z): Foundry provisioning is authorized only by the `foundry_exception` environment approval; `DEPLOY_FOUNDRY` must default false, privileged jobs must duplicate trusted event-context guards, and `pr-foundry` teardown is close-time only — decided by Trinity, Tank, Switch, Rai, Fact Checker.
