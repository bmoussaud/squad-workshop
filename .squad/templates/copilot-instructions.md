# Copilot Coding Agent — Squad Instructions

You are working on a project that uses **Squad**, an AI team framework. When picking up issues autonomously, follow these guidelines.

## Coordinator Canary Check

**IMPORTANT — run this check only when this session is running the Squad (Coordinator) agent, before doing any coordinator work.** Spawned member sessions and other non-coordinator sessions must skip this check; they do not receive `squad.agent.md` in `agent_instructions`.

Verify both coordinator safety-rail conditions:
1. The on-disk `.github/agents/squad.agent.md` file must exist and contain the exact token `SQUAD_COORDINATOR_CANARY_a8f3`. This token is placed at the end of that file.
2. The same token must be present in this coordinator session's own `agent_instructions`, confirming that the coordinator file was loaded.

**When either condition fails, you MUST:**
1. **STOP** — do not proceed with standard Squad behavior.
2. **WARN the user** with the matching exact message:
   - If the on-disk file is missing or its token is absent:
   ```
   ⚠️ Squad coordinator (squad.agent.md) appears to be missing or truncated. The on-disk canary token was not found. Do NOT proceed with standard Squad behavior — Squad's safety rails are not loaded. Please restart your session.
   ```
   - If the on-disk file passes but the token is absent from this coordinator session's `agent_instructions`:
   ```
   ⚠️ Squad coordinator (squad.agent.md) is intact on disk but was not loaded into this coordinator session. Do NOT proceed with standard Squad behavior — the coordinator's safety rails are not live. Please restart your session.
   ```
3. Do not continue with normal Squad routing, spawning, PR, or branch-protection behavior after emitting the warning.

## Team Context

Before starting work on any issue:

1. Read `.squad/team.md` for the team roster, member roles, and your capability profile.
2. Read `.squad/routing.md` for work routing rules.
3. If the issue has a `squad:{member}` label, read that member's charter at `.squad/agents/{member}/charter.md` to understand their domain expertise and coding style — work in their voice.

## Capability Self-Check

Before starting work, check your capability profile in `.squad/team.md` under the **Coding Agent → Capabilities** section.

- **🟢 Good fit** — proceed autonomously.
- **🟡 Needs review** — proceed, but note in the PR description that a squad member should review.
- **🔴 Not suitable** — do NOT start work. Instead, comment on the issue:
  ```
  🤖 This issue doesn't match my capability profile (reason: {why}). Suggesting reassignment to a squad member.
  ```

## Branch Naming

Use the squad branch convention:
```
squad/{issue-number}-{kebab-case-slug}
```
Example: `squad/42-fix-login-validation`

## PR Guidelines

When opening a PR:
- Reference the issue: `Closes #{issue-number}`
- If the issue had a `squad:{member}` label, mention the member: `Working as {member} ({role})`
- If this is a 🟡 needs-review task, add to the PR description: `⚠️ This task was flagged as "needs review" — please have a squad member review before merging.`
- Follow any project conventions in `.squad/decisions.md`

## Decisions

If you make a decision that affects other team members, write it to:
```
.squad/decisions/inbox/copilot-{brief-slug}.md
```
The Scribe will merge it into the shared decisions file.
