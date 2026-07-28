# PR Azure Environment pipeline commissioning

- **Timestamp:** 2026-07-28T14:46:30+02:00
- **Session:** Commissioning the PR Azure Environment deploy pipeline
- **Implementer:** Tank
- **Coordinator:** steered root-cause fixes and scope choice

## What happened

The `PR Azure Environment` workflow was commissioned from first-time failure to green on PR #45. Tank resolved sequential blockers in preflight diagnostics, Azure OIDC federation, Container Apps workload profile configuration, ARM deployment-name budgeting, and Bicep dependency ordering.

## Outcome

Run `30360924609` is the first green run of this workflow. Preflight gate, Provision and deploy, Update PR comment, and Python CI `validate` all passed. PR #45 is open, mergeable, and clean.

## Durable decisions and lessons

- `AZURE_ENV_NAME` is capped at 40 chars: ARM 64-char deployment-name cap minus current longest module prefix `private-virtual-network-` (24).
- Branches must follow `squad/{issue}-{slug}` for PR Azure environments; the preflight gate hard-blocks invalid names.
- Bicep `existing` references do not imply dependency edges; add explicit `dependsOn`.
- Prefer fast Python CI/static regression tests for infrastructure invariants before relying on Azure round trips.

## Outstanding for Benoit

- Orphaned untagged RG `rg-pr-45-change-application-background-color-to-green-1a64a29b` needs manual cleanup or a janitor rule for untagged strays.
- Active RG `rg-pr-45-change-application-backgr-1a64a29b` expires `2026-08-04T12:58:32Z`.
- Managed ACA infra RG `ME_pr45...` remains tied to the active environment.
- Azure Cost Management returned `429`; actual cost figures unavailable.

## Health report

- decisions.md size before archival: 63148 bytes
- decisions.md size after archival: 62787 bytes
- decisions.md final size: 65542 bytes
- entries archived: 0
- decision inbox files processed: 4 (tank-pr45-consumption-profile.md, tank-pr45-env-name-budget.md, tank-pr45-module-names.md, tank-pr45-oidc-credential.md)
- duplicate decision blocks removed/skipped: 0
- cross-agent histories updated: fact-checker, morpheus, neo, Rai, ralph, scribe, switch, tank, trinity
- histories summarized: tank
- archive note: No entries older than 7 days were found; decisions.md continues to grow monotonically and needs a real archiving strategy.
