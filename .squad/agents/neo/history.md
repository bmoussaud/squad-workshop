# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's first `gpt-image-2` implementation due to unsafe endpoint validation, incomplete PNG validation, missing CLI integration coverage, and generated egg-info artifacts. Strict reviewer lockout applies: Trinity may not revise this artifact; Neo owns the next revision. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Neo's second `gpt-image-2` revision because PNG validation accepts valid PNG data with trailing bytes and the ignored egg-info directory remains on disk. Trinity and Neo may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank's independent final `gpt-image-2` revision was approved by Switch with no findings after strict lockout was preserved. Exact terminal IEND validation now rejects trailing bytes, and repository hygiene checks confirm no egg-info artifacts. — decided by Switch

📌 Team update (2026-07-22T16:01:59+0000): Independently validated `gpt-image-2` version `2026-04-21` in Sweden Central on `GlobalStandard`: proposed and live capacity 1, quota limit 2/current usage 1. Provisioning awaits explicit user approval, including acceptance of cross-geography processing and default content and abuse monitoring; no Azure resources were created. — decided by Morpheus, Tank, and Neo

📌 Team update (2026-07-23T08:27:28+0000): Independently repaired the managed-identity Application Insights path and Storage/IaC security under strict reviewer lockout. With Application Insights local auth disabled, telemetry needs an explicit UAMI credential plus component-scoped Monitoring Metrics Publisher; Storage public access remains policy-disabled. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): A later telemetry test-isolation rejection locked Neo out of that artifact; @copilot owned the independent revision. The final repaired application is healthy at 100% traffic, generation remains safely degraded, and telemetry ingestion is propagation pending. — recorded by Scribe

📌 Team update (2026-07-27T08:47:25.103+02:00): Live-endpoint validation of 1024x1536 output plus title/stats legibility remains an open follow-up on PR #13 — decided by Benoit (via Squad Coordinator).

📌 Team update (2026-07-27T09:42:54.356+02:00): Per-PR ephemeral Azure environment design includes a gated post-deploy live-Foundry validation hook for sanitized image-generation evidence, tied to issue #4 and the issue #11 card-layout follow-up. — decided by Morpheus, Tank

📌 Team update (2026-07-27T14:44:52+02:00): Stale branch `bmoussaud-neo-investigating-artifact-bug` was cleaned up after verifying the relevant fix/9 content was already squash-merged on main as `0775c47`. Squash-merge SHA divergence can create phantom `N commits ahead` branches even when the tree is integrated; compare trees before rebasing or merging stale work. — recorded by Scribe

📌 Team update (2026-07-28T10:05:06+02:00): Benoit Moussaud (Product Owner) approved the Foundry stack for development only. Neo must carry forward #37: production requires a user-facing notice before release. Production also remains gated on #36 retention/deletion policy, #38 likeness/IP/minors policy, and #39 revalidate GlobalStandard routing; #39 may invalidate the EU-only assumption behind the approval.

📌 Team update (2026-07-28T10:14:07+02:00): Issue #37 scope changed. The user-facing notice must state that inference processing may occur outside the EU under GlobalStandard; any EU-only wording is factually wrong. Artifacts/storage remain in France Central/customer-designated storage. — decided by Benoit Moussaud

### 2026-07-28T11:41:20+02:00 — Issue #41 accessible green palette revision
- Owned Switch's rejected palette revision independently under reviewer lockout; Trinity did not participate.
- Established original baseline contrast before changing taste: original coral and gold already failed on some/all surfaces, while Trinity's green introduced additional regressions for muted/result, coral, and gold.
- Revised only palette/color values: sage-green backgrounds plus darker muted/coral/gold and shared line/border color so normal text clears 4.5:1 and icon/UI colors clear 3:1 across paper, surface, and result.
- Updated the static CSS contract to the new palette and validated with the full unittest suite.
