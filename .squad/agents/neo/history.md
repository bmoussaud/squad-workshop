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
