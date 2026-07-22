# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Product direction | Benoit | Product goals, user priorities, acceptance decisions |
| Architecture and scope | Morpheus | System design, interfaces, priorities, technical trade-offs |
| Python application | Trinity | Python services, APIs, data flow, model integration |
| Generative media | Neo | Image generation, prompting, model evaluation, visual quality |
| Azure platform | Tank | Deployment, storage, identity, monitoring, cost controls |
| Code review | Morpheus | Review cross-cutting changes and architectural consistency |
| Testing | Switch | Automated tests, image-quality evaluation, edge cases, release verification |
| Scope & priorities | Morpheus | What to build next, trade-offs, decisions |
| Session logging | Scribe | Automatic — never needs routing |
| Work monitoring | Ralph | Backlog scans, stalled work, follow-up routing |
| RAI review | Rai | Content safety, bias checks, credential detection, ethical review |
| Verification | Fact Checker | Verify claims, challenge assumptions, run pre-mortems |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Morpheus |
| `squad:{name}` | Pick up issue and complete the work | Named member |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.
8. **Human routing** — Benoit is not spawnable. Present Product Owner decisions to Benoit through the user and continue independent work while awaiting input.
