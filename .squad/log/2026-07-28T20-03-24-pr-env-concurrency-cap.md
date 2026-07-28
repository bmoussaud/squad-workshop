# PR environment concurrency cap session

- **Timestamp:** 2026-07-28T20:03:24+02:00
- **Requested by:** Benoit (Product Owner)
- **Agent:** Tank (Azure Platform Engineer)
- **Outcome:** SUCCESS

Tank fixed the PR #64 app-tier environment cap failure by making cap accounting open-PR-aware, warning on closed-PR orphan resource groups, and running the janitor after teardown completion. The change was committed as `0795dc7` on `bmoussaud-literate-umbrella`.

Validation reported: `python -m unittest test_pr_env_active_count` (6 OK), `test_pr_preflight_cli` (18 OK), `compileall` OK, YAML parse OK, and `git diff --check` OK. `uv` and `actionlint` were unavailable locally.

Decision captured: keep the app-tier cap counting only environments mapped to open PRs; do not raise the cap above 3 based on orphan evidence; consider path-filtering to skip app-tier provisioning for docs/CSS/template/test-only PRs.
