# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Summarized Learnings

Tank owns Azure platform, Bicep, deployment workflows, PR environments, and independent repair work under reviewer lockout. Standing project rules: Azure resources are Bicep/AVM-first, deployments use `azd`, production hosting prefers Azure Container Apps, Foundry remains gated by region/model/quota/capacity approval, and managed identities should preserve least privilege.

Key retained history:
- 2026-07-22: Completed independent final `gpt-image-2` and artifact-persistence revisions after Switch lockouts; both were approved after repository checks. Endpoint/request-shape repairs preserved identity scope `https://ai.azure.com/.default`, bounded timeouts, zero retries, and safe 5xx handling.
- 2026-07-23: Helped prepare Foundry provisioning for Sweden Central. Policy-disabled Storage required the later private endpoint/DNS/VNet path before generation could be fully healthy.
- 2026-07-27 #16/#25: Delivered deterministic PR-environment naming/preflight and relaxed the CI branch-name gate to advisory while keeping exact issue closure hard-fail.
- 2026-07-27 #15/#20/#29: Parameterized PR Bicep names/env-var emission, added close-time teardown and daily janitor workflows, and configured secretless Azure OIDC for PR environments. Teardown/janitor deletion is tag-scoped and must fail loudly on Azure query errors.
- 2026-07-28 #18/#17/#39/#41: Verified budget alerts and child tags, participated in Foundry exception gating/live validation, confirmed `GlobalStandard` is not EU-bound for inference, and supported the accessible green-background PR.
- 2026-07-28 #23: Corrected the PR #14 per-PR environment worked example to the implementation-derived `hash8` value `4c32c628`. The canonical SHA-256 input is `bmoussaud/squad-workshop|14|render-card-layout`; keep `repo` explicitly documented as GitHub `owner/repo` and label `azd` and managed-environment length caps as conservative project constraints where their platforms publish no maximum.

## Recent Updates

- 2026-07-28T17:40:33.461+02:00 #34: `@secure()` must decorate the Application Insights connection-string outputs at both the Foundry module and root deployment boundaries. Bicep secure outputs require Bicep 0.35.1 or later; verify that the compiled ARM output type is `securestring`. The connection string remains available only through the existing secure Container App app-setting wiring, not `azd` or deployment outputs.
- 2026-07-28 #45 preflight: Diagnosed `pr_preflight.py` exit 3 as an intentional `invalid_names` hard block for branches outside `squad/{issue}-{slug}`; workflow diagnostics now print helper output before enforcement.
- 2026-07-28 #45 OIDC: Added Entra federated credential `github-pr-app-environment-immutable` on app `squad-workshop-pr-envs` for exact subject `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`; deploy/teardown/janitor OIDC now authenticate.
- 2026-07-28 #45 workload profile: PR environments use Container Apps `Consumption` workload profile semantics and omit dedicated min/max counts so scale-to-zero remains valid.
- 2026-07-28 #45 naming: Replaced per-module name compaction with the root fix: `AZURE_ENV_NAME` is bounded at 40 chars (`64 - 24`) in `infra/scripts/pr_environment_names.py`. Preflight and deploy share that helper; teardown/janitor delete by `pr-number` tags. Python CI has a regression test enumerating Bicep module deployment prefixes against the 64-char ARM limit.
- 2026-07-28 #45 Bicep ordering: Public Container App diagnostics and replica alert use explicit `dependsOn: [containerApp]`; `existing` resource references do not create dependency edges.
- 2026-07-28 #45 outcome: Run `30360924609` was the first green `PR Azure Environment` workflow run: Preflight gate, Provision and deploy, Update PR comment, and Python CI `validate` passed. PR #45 is open, mergeable, and clean.
- Outstanding: Orphaned untagged RG `rg-pr-45-change-application-background-color-to-green-1a64a29b` will not be janitor-reaped; active tagged RG `rg-pr-45-change-application-backgr-1a64a29b` expires `2026-08-04T12:58:32Z`; managed ACA infra RG `ME_pr45...` remains tied to the active environment; Azure Cost Management returned `429`.

📌 Team update (2026-07-28T14:46:30+02:00): The `PR Azure Environment` pipeline is commissioned; run `30360924609` was its first green run. Branches must follow `squad/{issue}-{slug}` or preflight hard-blocks with `invalid_names`; wordy titles are safely truncated. `AZURE_ENV_NAME` is capped at 40 chars from ARM's 64-char deployment-name limit minus the current 24-char longest Bicep module prefix (`private-virtual-network-`); re-derive the budget if any longer module prefix is added, and rely on the Python CI regression test to catch violations. Bicep `existing` references create no dependency edge, so add explicit `dependsOn`. Prefer fast Python CI/static validation over discovering infra invariants through multi-minute Azure round trips. — decided by Tank, steered by Coordinator
📌 Team update (2026-07-28T20:14:00+02:00): Tank shipped #34 as PR #55 and #23 as PR #57. The ephemeral-environment concurrency cap correctly blocked provisioning at 4/3; this is a capacity rail, not a defect. The current `rename_branch` tool still produces `bmoussaud-*` names incompatible with preflight's required `squad/{issue}-{slug}` convention (#54). — recorded by Scribe
📌 Team update (2026-07-28T22:16:40+02:00): Tank's #71 is authoritative; duplicate #72 was a coordinator tracking error, not a Tank failure. Forensics: #56 tag +102s after merge, #57 tag +~4m, and #59 deletion completed ~26m after close. The 18:15Z cap failure was closed-PR capacity, proving #71's accounting defect; the separate close/deploy race and slow async deletion remain open and unfiled. — recorded by Scribe
