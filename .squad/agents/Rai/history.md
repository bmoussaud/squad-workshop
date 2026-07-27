# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Core Context

Agent Rai initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-07-22

## Learnings

Initial setup complete.

## Review History

- 2026-07-27: Rejected issue #16 Phase 1 preflight. Fork trust accepts ambiguous falsey signals and can proceed; Foundry exceptions also lack a mandatory review/cap gate. Independent remediation is required. Also flagged raw identifier/repository interpolation in outputs as advisory log-safety exposure.
- 2026-07-27: Approved Morpheus's independent issue #16 remediation. Strict trust signals, Foundry authorization plus cap enforcement, and log-safe projections passed focused adversarial probes and the full suite.

📌 Team update (2026-07-27T14:24:13+02:00): Cross-agent architecture outcome for #16: Tank’s deterministic names are correct but `web.bicep` currently reconstructs and overflows PR Container App names. Phase 3/#15 must consume precomputed names as parameters; no Azure PR environment should rely on the current Bicep construction.

- 2026-07-27: Reviewed authorized CI guardrail relaxation (#25, commit 51336ce). 🟢 Green. Branch-name regex demoted to advisory `::notice::`; "closes exactly one issue" kept as a hard, fail-closed gate; branch↔issue cross-check made conditional on convention. Verified independently: BRANCH/BODY still injection-safe via env + "$VAR" (no `${{ }}` in run:); `::notice::` echo of attacker-controlled `$branch` cannot inject workflow commands (refs carry no newline, commands only honoured at line-start). Bash-reproduced edge cases all fail-closed. Learning: the conditional cross-check is a typo-catcher, not a security control (bypassable by branch name) — but the commit/comments say so honestly, so it passes. Double-close-same-issue false positive is over-strict but pre-existing and fail-closed; flagged as optional dedupe recommendation.

📌 Team update (2026-07-27T16:58:24.269+02:00): Tank's CI relaxation for issue #25 (commit 51336ce) ratified GREEN by Rai. Decision merged into decisions.md. App-generated worktree branch names now pass CI without requiring manual rename. — decided by Tank, reviewed by Rai

- 2026-07-27: Reviewed Phase 3 PR deploy workflow + `pr_preflight.py` CLI (#15, commit e0d2d64) — treated as unreviewed code of unknown provenance (author lost pre-commit; coordinator self-validated). 🟢 Green. Traced fork isolation end-to-end: `head.repo.fork` -> strict `_parse_tristate_bool` -> `evaluate` step-0 bool gate -> `decision` string -> deploy `if: == 'proceed'` JOB-level exclusion. Empirically probed 9 input cases: only exact `false` proceeds; forks/empty/ambiguous -> blocked/exit3; draft -> skip (NOT proceed); empty count -> blocked. Confirmed id-token:write only on deploy, pull-requests:write only on comment, all PR values via env (no `${{ github.event.* }}` in run:), 4 actions SHA-pinned, `_sanitize_log` blocks `$GITHUB_OUTPUT` newline injection, comment never claims health without deploy-success AND smoke-pass. 186 tests pass (re-run independently). Two non-blocking advisories: (1) the smoke-message comment branch is dead code (smoke failure fails deploy job -> "Deployment did not complete" renders instead — fail-closed); (2) preflight crash = silent green no-op. Learning: this workflow's fork gate is layered (Python strict-bool + job-level `if` + `pull_request` never `pull_request_target`) — every ambiguity fails closed by construction; the coordinator's shallow checks happened to be correct but I verified each independently rather than trusting them.
