# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Summarized by Scribe on 2026-07-28T11:22:44+02:00; older detailed review notes were condensed to durable lessons. Append new learnings below. -->

📌 Team update (2026-07-22T13:11:01+0000): Reviewer lockout is strict. Switch rejected Trinity's first `gpt-image-2` implementation, then rejected Neo's second revision; Tank owned the final independent repair and Switch approved only after exact PNG termination, repository hygiene, adapter/configuration coverage, compileall, lock check, diff check, and no egg-info residue passed. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Foundry `gpt-image-2` adapter contract remains: opt-in environment configuration, OpenAI v1 route, `DefaultAzureCredential` with `https://ai.azure.com/.default`, strict Azure endpoint validation, bounded timeout, `max_retries=0`, no debug/provider leakage, and complete base64 PNG validation through terminal IEND. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Artifact persistence must use exact artifact-ID filenames with png/txt/bin allowlist, atomic exclusive no-overwrite publication, guaranteed temporary cleanup, and post-success-only in-memory state updates. — decided by Switch

📌 Team update (2026-07-23T14:02:52+0000): Generation completion logging is a safe structured INFO event at the web boundary. Allowed fields are correlation_id, outcome, success, duration_ms, size_bytes for success, and dependency/provider error_code for provider failures; prompts, titles, endpoints, credentials, provider internals, and bytes stay out. — decided by Trinity and Switch

📌 Team update (2026-07-27T14:24:13+02:00): PR-environment Phase 1 naming/preflight tests pin deterministic SHA-256 naming, Azure-safe bounds, strict trust booleans, Foundry authorization plus cap, and sanitized printable output. The design-doc worked hash example was not reproducible; code keeps the pinned algorithm. — decided by Switch, Rai, Morpheus, Tank

📌 Team update (2026-07-27T20:04:31+02:00): Phase 3 test review showed green suites can hide weak assertions. Preserve per-status smoke retry/fail-fast coverage, ASCII-only numeric parsing in preflight, usage exit-2 checks, PROCEED/SKIP distinctness, and Bicep env-var wiring tests. — decided by Switch

📌 Team update (2026-07-27T21:17:00+02:00): TTL reaper safety depends on literal non-zero malformed-input exit code 3, strict allowlist tags, no wall-clock/network/sleep in tests, and gate order that keeps shared/prod resources before expiry/orphan checks. — decided by Switch

📌 Team update (2026-07-28T08:22:20+02:00): Phase 5/#18 test review proved `log_analytics` naming tests non-tautological and added Bicep wiring coverage for the single envvars path after redundant workflow export was removed. — decided by Switch

📌 Team update (2026-07-28T09:03:21Z): Phase 6 Foundry scope tests pin literal `requires:foundry` label matching, exact/case-sensitive path matching, and preflight gate order so fork/untrusted/draft/invalid-name/app-cap outrank `foundry_unauthorized`. — decided by Trinity, Tank, Switch, Rai, Fact Checker

📌 Team update (2026-07-28T09:55:56+02:00): Current status correction: dev Azure infrastructure is deployed in `rg-fantasy-cards-dev-8f327f8c` and `gpt-image-2-dev` succeeded; CI exists and runs tests, but branch protection is not enabled, so merges are ungated until protection is configured. — decided by status-summary session

📌 Team update (2026-07-28T10:14:07+02:00): Governance correction accepted: GlobalStandard is not EU-bound for `gpt-image-2` inference, and Benoit accepted non-EU inference for dev and production. Reject stale EU-only notices, tests, or docs. — decided by Benoit Moussaud

📌 Team update (2026-07-28T11:36:33+02:00): Switch rejected Trinity's first #41 green palette because muted/result, coral, and gold failed WCAG contrast on the new surfaces. Trinity was locked out and Neo owned the independent visual/palette revision. — decided by Switch

📌 Team update (2026-07-28T11:46:26+02:00): Switch approved Neo's #41 palette with notes after independently recomputing all contrast ratios and adding tests that pin foreground/border tokens and AA/UI contrast. Darker borders are more visible than the old warm design but accessible and coherent. — decided by Switch

📌 Team update (2026-07-28T11:22:44+02:00): Issue #41 established that palette/background changes must be contrast-checked against every foreground token used on every affected surface before review. The original pre-green design already had coral/gold AA failures; Neo's accessible sage-green revision corrected those pre-existing failures while fixing Trinity's green regressions. — decided by Switch and Neo

📌 Team update (2026-07-28T12:01:41+02:00): PR-environment work in this repo requires `squad/{issue}-{slug}` branches; otherwise Azure preflight hard-blocks with `invalid_names`. GitHub's branch-rename API closed PR #44 instead of retargeting it, so renamed branches may require replacement PRs. Azure OIDC uses the immutable ID-qualified subject `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`; Entra credentials must match exactly. — recorded by Scribe

📌 Team update (2026-07-28T14:46:30+02:00): The `PR Azure Environment` pipeline is commissioned; run `30360924609` was its first green run. Branches must follow `squad/{issue}-{slug}` or preflight hard-blocks with `invalid_names`; wordy titles are safely truncated. `AZURE_ENV_NAME` is capped at 40 chars from ARM's 64-char deployment-name limit minus the current 24-char longest Bicep module prefix (`private-virtual-network-`); re-derive the budget if any longer module prefix is added, and rely on the Python CI regression test to catch violations. Bicep `existing` references create no dependency edge, so add explicit `dependsOn`. Prefer fast Python CI/static validation over discovering infra invariants through multi-minute Azure round trips. — decided by Tank, steered by Coordinator

📌 Team update (2026-07-28T17:36:00+02:00): PR ownership validation must parse only genuine top-level Markdown closing references. Mask code spans (including balanced nested delimiters), fenced/indented blocks, blockquotes, and tables; preserve offsets/newlines; retain one-unique-issue fail-closed enforcement and environment-backed PR-body access. — decided by Switch
