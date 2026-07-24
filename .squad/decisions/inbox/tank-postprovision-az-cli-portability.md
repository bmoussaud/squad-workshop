# Postprovision Azure CLI portability and failure policy

- **Decision:** Resolve Azure CLI with `shutil.which("az")` and then `shutil.which("az.cmd")`; execute the resolved absolute path using an argument list with `shell=False` (the `subprocess` default).
- **Failure policy:** If Azure CLI is absent or cannot be started, the `azd` postprovision hook fails with an actionable, non-secret-bearing error. It does not warn and exit successfully.
- **Rationale:** `azd` postprovision hooks that perform Azure RBAC migration ordinarily require Azure CLI. A successful no-op could silently preserve the retired account-scoped `Storage Blob Data Contributor` assignment, weakening least privilege. Failure occurs before deletion, so the verified container assignment and existing account assignment remain intact for a safe retry.
