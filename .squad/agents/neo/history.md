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
