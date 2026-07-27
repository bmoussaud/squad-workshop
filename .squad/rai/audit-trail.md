# RAI Audit Trail

> Append-only evidence log. Entries are redacted — never contains raw secrets or harmful content.

<!-- Rai appends findings below -->

### 2026-07-27T14:24:13+02:00: PR environment preflight review
- **Scope:** `infra/scripts/pr_environment_names.py`, `infra/scripts/pr_preflight.py`, and `tests/test_pr_environment_names.py` (`main..HEAD`)
- **Verdict:** 🔴 Red
- **Critical — fail-open trust boundary:** `infra/scripts/pr_preflight.py:94` treats falsey non-boolean fork signals as trusted. Reproduction with absent/ambiguous values and matching repositories returns `PROCEED`. `:78,139` likewise make Foundry-cap enforcement solely conditional on an optional caller-controlled flag, with no explicit-review gate; no sensitive input recorded.
- **Advisory — log safety:** `infra/scripts/pr_preflight.py:121-122` includes an invalid supplied identifier in a printable result message. `infra/scripts/pr_environment_names.py:252,267,352` includes the raw repository input in JSON CLI output. No secrets observed in the diff.
- **Validation:** focused unit suite passed (39 tests); boundary reproductions completed locally.
- **Remediation status:** open; reviewer rejection requires an independent fix owner.

### 2026-07-27T15:15:53+02:00: PR environment preflight re-review
- **Scope:** remediation commit `2292357` (`e8f7688..HEAD`)
- **Verdict:** 🟢 Green
- **Trust boundary closed:** `infra/scripts/pr_preflight.py:118-152` blocks every tested malformed fork/draft/repository signal before draft evaluation. Omission of the required Foundry signal raises before a decision; no fork case proceeded.
- **Foundry control closed:** `infra/scripts/pr_preflight.py:189-213` requires explicit authorization and enforces the cap at/above one. Authorization does not waive the cap.
- **Log safety closed:** `infra/scripts/pr_preflight.py:160-169` emits only opaque names; `infra/scripts/pr_environment_names.py:88-96,374-392` sanitizes errors and emits only allowlisted printable fields. Dynamic newline/control/workflow-command probes produced neither injected lines nor controls.
- **Validation:** full suite passed (148 tests). Diff credential/identifier and terminology scan found no committed secrets or excluded terminology.
- **Remediation status:** verified closed.

### 2026-07-27T17:04:17+02:00: CI PR-ownership gate relaxation review (#25)
- **Scope:** commit `51336ce` — `.github/workflows/ci.yml`, `validate` job "Validate pull request ownership" step (authorized guardrail relaxation).
- **Verdict:** 🟢 Green — relaxation is safe and honestly described.
- **(1) Guarantee lost:** Previously every PR provably closed the issue named in its own conforming branch. Now a non-conforming (app-generated) branch may close ANY single issue with no branch cross-check. In this repo's threat model (human-opened, human-reviewed PRs; `permissions: contents: read`; workshop repo) this is acceptable — the gate is hygiene, not a security boundary, and the reviewer sees which issue is closed. Stated plainly: acceptable, not a meaningful new risk.
- **(2) Conditional cross-check soundness:** As a SECURITY control it is bypassable — an actor evades it by simply not adopting the `squad/{n}-{slug}` name; that is closer to theatre than defence. As a TYPO-CATCHER for contributors who opt into the convention it has real value (catches `squad/16-*` branch closing `#99`). The commit message and code comments describe it honestly ("conforming branches retain the guarantee… non-conforming app branches skip only that comparison"); no overstatement. Honest framing accepted.
- **(3) Injection safety (independently verified, not taken on report):** `BRANCH`/`BODY` are passed via `env:` (lines 17-19) and read as `"$BRANCH"`/`"$BODY"` (21-22); no `${{ }}` interpolation into `run:`. The new `::notice::` echoes attacker-controlled `$branch` mid-line; git refs cannot contain newlines/control chars and GitHub workflow commands are only honoured at line-start, so a crafted ref (e.g. embedded `::error::` or literal `%0A`) cannot start a new command line — no log-command injection. Confirmed by construction + ref-format constraints, not assumed.
- **(4) Fail-open vs fail-closed (empirically tested in bash):** empty/null body → count 0 → exit 1 (fail-closed); conforming match → pass; conforming mismatch → exit 1; non-conforming + one issue → pass (the accepted relaxation); two different issues → exit 1; `grep … || true` yields a 0-length array (no fail-open). No path lets the job pass when it should fail.
- **(5) Double-close false positive:** `Closes #16 … Closes #16` counts as 2 references → exit 1. This is over-strict but fails CLOSED and is PRE-EXISTING (the `-ne 1` count test is unchanged), so it is not a regression from this commit. Recommendation (non-blocking): dedupe references before the count if it becomes a contributor friction point.
- **Advisory (non-blocking):** naive `grep` matches closing keywords inside code fences/quotes; pre-existing, unchanged, fail-closed direction.
- **Validation:** control-flow reproduced in bash across 6 edge cases; injection analysed against git ref-format + Actions command semantics; diff scanned for secrets/terminology — none.
- **Remediation status:** none required. Green with two optional advisories (double-close dedupe; fenced-keyword matching).
