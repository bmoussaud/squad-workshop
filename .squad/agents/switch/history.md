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

📌 Team update (2026-07-27T08:47:25.103+02:00): Independent review of the card-contract tests remains an open follow-up on PR #13 — decided by Benoit (via Squad Coordinator).

2026-07-27T14:24:13+02:00 — Reviewed Tank's PR-envs Phase 1 (#16, commits dfdee7e/e8f7688). Verdict: APPROVE WITH FINDINGS. Ran CI gates myself: full suite 120 OK via `uv run python -m unittest discover`, targeted module 46 OK, compileall/lock-check/egg-info/diff --check all clean. Adversarial probes (path traversal, unicode, storage no-hyphen sweep, container-app start/end rules, GITHUB_OUTPUT safety, preflight fail-closed caps) all held. Hash discrepancy handled honestly (doc example 4717e5bb not reproducible; code pins owner/repo -> 4c32c628 and flags for human). Added 7 regression tests in commit 2513c58; did not touch the implementation. Open human item: correct the design doc worked example.

📌 Team update (2026-07-27T14:24:13+02:00): Cross-agent outcome for #16: Rai’s RED review triggered Tank lockout; Morpheus independently fixed strict trust booleans, Foundry authorization-plus-cap, and log safety; Rai re-reviewed GREEN with 148 tests. `web.bicep` still does not consume the tested names; Phase 3/#15 owns that seam.
📌 Team update (2026-07-27T09:42:54.356+02:00): Per-PR ephemeral Azure environment design includes a gated post-deploy live-Foundry validation hook for sanitized image-generation evidence, tied to issue #4 and the issue #11 card-layout follow-up. — decided by Morpheus, Tank

2026-07-27T20:04:31+02:00 — Reviewed Phase 3 (#15) test quality: 5bdc904 (naming/Bicep, Tank), 3cc3d16 (smoke, Trinity), e0d2d64 (workflow + pr_preflight CLI, salvaged/never-reviewed). Verdict: APPROVE WITH CHANGES — made and committed the changes (a94f973), so it now clears the bar. Ran the suite myself (192 OK; the 3 reviewed modules = 111 tests in ~0.05s, fully hermetic). Hand mutation testing found two gaps a green suite hid: (1) smoke retry set {408,429,502,503,504} was pinned only by 503 — shrinking it survived; added per-status retry + fail-fast coverage. (2) pr_preflight._parse_count used isdigit()+int(), crashing on unicode superscript and silently accepting Arabic-Indic digits — hardened to ASCII fail-closed, added hostile-input matrix, usage exit-2, and PROCEED!=SKIP checks. Caught mutations: fail-open trust bool, vnet overflow re-anchor, shrunk retry set. No pre-existing test was modified in any commit. Did not push, did not open a PR.

2026-07-27T21:17:00+02:00 — Reviewed Phase 4 (#20) TTL reaper test quality: 5677e3f (pr_env_reaper.py + tests, Trinity). Verdict: APPROVE WITH CHANGES — committed one strengthening test. Ran full suite myself (245 OK baseline; reaper-only 53 in 0.012s, hermetic). Empirically applied 16 mutations (patch source, run, restore via git). All 8 of Trinity's claimed-caught mutations verified caught. Of 8 additional unanticipated mutations, 7 caught and 1 SURVIVED: setting the constant MALFORMED_INPUT_EXIT_CODE=0 — every malformed-input test asserted against the constant itself, so the 'never exit 0 on garbage' invariant was not pinned to a non-zero literal. Added test_malformed_input_exit_code_is_a_nonzero_literal pinning it to 3 and asserting a real malformed run returns non-zero; re-applying the mutation now FAILS. Catastrophe guard confirmed: shared-foundry with stale-2000 expires-at is kept because identity gates run before expiry (gate-order bug that deletes shared ACR is caught). Hermeticity clean (no wall-clock/network/sleep). Both #20 commits are pure insertions; no pre-existing test weakened. 245->246 tests green, tree restored. No source change (Trinity not locked out). Did not push, did not open a PR.
