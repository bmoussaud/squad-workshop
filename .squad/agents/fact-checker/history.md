# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Core Context

Agent Fact Checker initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-07-22

📌 2026-07-27: Verified PR-environment naming facts. The design's PR #14 SHA-256 worked example is contradicted: the stated input produces `4c32c628`, not `4717e5bb`; recorded in the decisions inbox.

## Learnings

Initial setup complete.

📌 Team update (2026-07-27T14:24:13+02:00): Your verified Container Apps rule is now enforced. Cross-agent outcomes: `web.bicep` has not yet consumed Tank’s names (Phase 3/#15 owns the parameter seam), and Rai’s RED preflight review completed the required independent Morpheus remediation and GREEN re-approval at 148 tests.

📌 Team update (2026-07-28T09:03:21Z): Fork-OIDC exploitability was checked against GitHub docs; fork PRs cannot elevate to `id-token`, so the fork-guard issue is defense-in-depth rather than active credential exfiltration — decided by Fact Checker.

📌 2026-07-28: Verified PR #45 Azure OIDC failure. GitHub emitted `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app` in both deploy and teardown failures; GitHub docs confirm this is the immutable subject format for repositories created after 2026-07-15. The subject was stable across observed teardown failures. Recommendation: update Entra federated credential to the exact emitted subject, not the legacy name-only subject.

📌 Team update (2026-07-28T12:01:41+02:00): PR-environment work in this repo requires `squad/{issue}-{slug}` branches; otherwise Azure preflight hard-blocks with `invalid_names`. GitHub's branch-rename API closed PR #44 instead of retargeting it, so renamed branches may require replacement PRs. Azure OIDC uses the immutable ID-qualified subject `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`; Entra credentials must match exactly. — recorded by Scribe

📌 Team update (2026-07-28T14:46:30+02:00): The `PR Azure Environment` pipeline is commissioned; run `30360924609` was its first green run. Branches must follow `squad/{issue}-{slug}` or preflight hard-blocks with `invalid_names`; wordy titles are safely truncated. `AZURE_ENV_NAME` is capped at 40 chars from ARM's 64-char deployment-name limit minus the current 24-char longest Bicep module prefix (`private-virtual-network-`); re-derive the budget if any longer module prefix is added, and rely on the Python CI regression test to catch violations. Bicep `existing` references create no dependency edge, so add explicit `dependsOn`. Prefer fast Python CI/static validation over discovering infra invariants through multi-minute Azure round trips. — decided by Tank, steered by Coordinator

- 2026-07-30T11:16:49.586+02:00 Azure PR-environment verification: Confirmed the undeclared `eligible` output and ambiguous Container App selection from repository evidence. Keep non-zero minimum replicas, fixed Foundry naming, and disabled live validation qualified as repository facts or risks, not claims about current live Azure resources.

- 2026-07-30T11:31:20.176+02:00 private-network consolidation verification: Approved the design only with conditions. Corrected the legacy app ingress from disabled to internal. Environment or network failure is the strongest residual risk, so live Azure inventory and validation are mandatory before deleting either rollback artifact; no implementation decision has been accepted.
