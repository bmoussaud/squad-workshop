# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's first `gpt-image-2` implementation due to unsafe endpoint validation, incomplete PNG validation, missing CLI integration coverage, and generated egg-info artifacts. Strict reviewer lockout applies: Trinity may not revise this artifact; Neo owns the next revision. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Neo's second `gpt-image-2` revision because PNG validation accepts valid PNG data with trailing bytes and the ignored egg-info directory remains on disk. Trinity and Neo may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch APPROVED Tank's independent final `gpt-image-2` revision with no findings. Strict lockouts were honored, all 22 tests and repository checks passed, and only live Azure invocation remains pending due unavailable authentication. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch APPROVED Tank's `create_foundry_client` endpoint-normalization follow-up with no findings. The change supports user-supplied `services.ai.azure.com/openai/v1` endpoints while retaining `*.openai.azure.com`, adds `size=1024x1024`, and preserves identity, scope, timeout, and zero-retry constraints. All 24 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch APPROVED Tank's Foundry 500 `Unable to get resourceinformation` fix. The request now omits unsupported extra `output_format`, matches the user's working sample, preserves the exact outbound route after base-URL normalization, and reports 5xx failures without provider-specific wording or body leakage. All 25 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch APPROVED Tank's recurring Foundry 500 repair. The approved scope, timeout, zero-retry, exact request-shape, and safe error-handling contract is restored, with real `openai.InternalServerError` covered through adapter and CLI. All 27 tests and repository checks passed. Runtime used `*.openai.azure.com` while the authoritative sample uses `*.services.ai.azure.com/openai/v1`; endpoint/deployment pairing remains the service-side fix. No live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch APPROVED Tank's independent artifact persistence revision with no remaining findings. Exact artifact-ID filenames, the png/txt/bin allowlist, atomic exclusive collision-safe publication, guaranteed temporary cleanup, and post-success-only memory updates satisfy the rejected requirements. All 33 tests, `compileall`, `uv lock --check`, `git diff --check`, and the residue scan passed; no commit was made. — decided by Switch

📌 Team update (2026-07-23T09:03:12+0000): For CI, bare `git diff --check` is insufficient because a clean runner worktree can hide whitespace errors already committed in the change range. PR, push, and initial-push events require explicit committed ranges. Switch was strictly locked out after Morpheus rejected v1; Tank owned the independent revision. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Security review confirmed that management-group policy keeps Storage public access disabled and that private Blob recovery needs a separately approved VNet/private-endpoint/private-DNS replacement. The live repaired revision is healthy at 100% traffic, direct anonymous Blob access remains denied, and generation fails safely with `503 artifact_unavailable`. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Strict reviewer lockout was enforced across telemetry revisions: rejected authors did not revise the same artifact, Neo independently repaired managed-identity telemetry/security, and @copilot independently fixed telemetry test isolation before final approval. — recorded by Scribe

📌 Team update (2026-07-23T14:02:52+0000): Generation completion uses a safe structured INFO contract at the web boundary, with acceptance coverage for successful and provider-failed event metadata and no sensitive request or dependency values. — decided by Trinity, Switch
