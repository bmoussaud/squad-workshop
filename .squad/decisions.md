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

### 2026-07-22T12:49:52+0000: Azure hosting, agentic platform, and identity preferences
**By:** bmoussaud (via Copilot)
**What:** Prefer Azure Container Apps with dedicated workload profiles for production application hosting in France Central. Approve Microsoft Foundry for the agentic platform, with Sweden Central preferred, subject to validating the exact region, model, SKU, quota, capacity, and required features before provisioning. Prefer user-assigned managed identities while preserving least privilege and separate identities for distinct trust boundaries.
**Why:** User directive establishing production hosting, agentic platform, regional, capacity-validation, and workload identity preferences.

### 2026-07-22T13:28:52+0000: Azure application deployment workflow
**By:** bmoussaud (via Copilot)
**What:** Use the Azure Developer CLI (`azd`) and `azure.yaml` to manage application deployment to Azure. Authenticate the shell to the Azure subscription with `azd auth login`; Azure CLI authentication with `az login` is available as a fallback.
**Why:** User directive establishing the project's Azure application deployment workflow.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
