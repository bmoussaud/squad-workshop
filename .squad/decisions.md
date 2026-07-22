# Squad Decisions

## Active Decisions

### 2026-07-22T12:33:43+0000: Azure resource configuration
**By:** bmoussaud (via Copilot)
**What:** Azure resources must always be configured through Bicep. Prefer Azure Verified Modules when a suitable maintained module exists; use native Bicep as the fallback.
**Why:** User directive establishing the project's Azure infrastructure-as-code standard.

### 2026-07-22T12:40:47+0000: Python application development workflow
**By:** bmoussaud (via Copilot)
**What:** Python is the primary application development language. Use `uv` for Python project, dependency, environment, and command workflows. Use TOML, centered on `pyproject.toml`, as the canonical project and tool configuration format. Runtime secrets and deployment settings remain in appropriate environment variables, secret stores, or deployment configuration.
**Why:** User directive establishing the project's application language, Python workflow tooling, and configuration standards while keeping runtime and deployment concerns in their appropriate systems.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
