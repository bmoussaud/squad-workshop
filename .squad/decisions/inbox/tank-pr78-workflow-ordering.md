### D-pr78-bicepparam-ingress-default: Bicep parameter default for applicationExternalIngress must be true (open), not false (closed)
**ID:** D-pr78-bicepparam-ingress-default
**Decided At:** 2026-07-29T14:30:00+02:00
**By:** Tank
**Status:** active
**Supersedes:** []
**What:** `infra/main.bicepparam` sets `applicationExternalIngress` by reading the `FANTASY_CARD_EXTERNAL_INGRESS` environment variable. The default (when the variable is absent) is `true` (open ingress), NOT `false` (closed).
**Why:**
`pull_request_target` workflows always execute the workflow YAML from the BASE branch (main), not from the PR head. This is an immutable GitHub security guarantee. Consequently, any workflow-file changes inside PR #78 (including the `configure_auth` job that opens ingress after installing real OIDC credentials) do NOT take effect for the CI check until the PR is merged.

When main's legacy workflow runs against PR #78's code:
- It does NOT set `FANTASY_CARD_EXTERNAL_INGRESS` (that echo lives in the PR's workflow step)
- If the bicepparam default were `false`, the container app deploys with closed ingress
- Main's smoke test then probes the FQDN and gets HTTP 404

The fail-closed posture (closing ingress before auth is configured) is enforced by the WORKFLOW step (`echo "FANTASY_CARD_EXTERNAL_INGRESS=false"` in "Configure shared bindings"), NOT by the bicepparam default. The bicepparam default is only a fallback for:
- Local developer `azd up` runs (where no CI env var is set)
- Pre-merge CI runs via `pull_request_target` (which use main's workflow)

After PR #78 merges, every subsequent PR's CI run uses the updated workflow, which always sets the variable explicitly before `azd provision`. The default is never the effective value in those runs.

Setting the default to `true` is safe because placeholder OIDC credentials (`00000000-0000-4000-8000-000000000000`) are non-functional — unauthenticated users can reach health endpoints but cannot authenticate. The `/health/live` and `/health/ready` endpoints are intentionally public (liveness probes require no auth) and their accessibility is not a security concern.
