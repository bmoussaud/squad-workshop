# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Core Context

Agent Ralph initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-07-22

## Learnings

Initial setup complete.

📌 Team update (2026-07-23T08:32:26+0000): Monitoring activated at bmoussaud's request. The initial GitHub scan found no open issues or pull requests; the overdue retrospective subsequently created retro-action issues #2, #3, and #4. — recorded by Scribe

📌 Team update (2026-07-23T09:03:12+0000): Completed the scan-triage-review-merge-rescan loop for retro action #3. PR #6 merged as `abd5ceeccea651550080bae9dcb9446115152034`; #2 still awaits human approval, #4 remains blocked by #2, and #5 remains unauthorized backlog work despite duplicate member labels. No pull requests remain open. — recorded by Scribe

📌 Team update (2026-07-28T12:01:41+02:00): PR-environment work in this repo requires `squad/{issue}-{slug}` branches; otherwise Azure preflight hard-blocks with `invalid_names`. GitHub's branch-rename API closed PR #44 instead of retargeting it, so renamed branches may require replacement PRs. Azure OIDC uses the immutable ID-qualified subject `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`; Entra credentials must match exactly. — recorded by Scribe

📌 Team update (2026-07-28T14:46:30+02:00): The `PR Azure Environment` pipeline is commissioned; run `30360924609` was its first green run. Branches must follow `squad/{issue}-{slug}` or preflight hard-blocks with `invalid_names`; wordy titles are safely truncated. `AZURE_ENV_NAME` is capped at 40 chars from ARM's 64-char deployment-name limit minus the current 24-char longest Bicep module prefix (`private-virtual-network-`); re-derive the budget if any longer module prefix is added, and rely on the Python CI regression test to catch violations. Bicep `existing` references create no dependency edge, so add explicit `dependsOn`. Prefer fast Python CI/static validation over discovering infra invariants through multi-minute Azure round trips. — decided by Tank, steered by Coordinator
