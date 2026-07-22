# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T12:40:47+0000): Python is the primary application language; use `uv` for Python project, dependency, environment, and command workflows, and TOML centered on `pyproject.toml` for canonical project and tool configuration. Keep runtime secrets and deployment settings in environment variables, secret stores, or deployment configuration. — decided by bmoussaud

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's first `gpt-image-2` implementation due to unsafe endpoint validation, incomplete PNG validation, missing CLI integration coverage, and generated egg-info artifacts. Strict reviewer lockout applies: Trinity may not revise this artifact; Neo owns the next revision. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Neo's second `gpt-image-2` revision because PNG validation accepts valid PNG data with trailing bytes and the ignored egg-info directory remains on disk. Trinity and Neo may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank's independent final `gpt-image-2` revision was approved by Switch with no findings after strict lockout was preserved. Final local validation passed 22 tests, `compileall`, `uv lock --check`, and `git diff --check`; egg-info artifacts are absent. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's artifact persistence revision because UUID collisions can overwrite existing finalized artifacts and failed temporary writes can leave partial temp files. Strict lockout applies: Trinity may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank completed the artifact persistence revision independently while Trinity's lockout remained in force. Switch approved exact artifact-ID filenames, the png/txt/bin allowlist, atomic exclusive no-overwrite publication, guaranteed temporary cleanup, and post-success-only memory updates after 33 tests and repository checks passed. — decided by Switch
