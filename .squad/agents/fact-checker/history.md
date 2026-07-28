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
