<!-- squad-decision-ledger:2 -->
# Squad Decisions

## Active Decisions

### D-issue-61-artifact-auth-owner-stream: Bind artifact access to authenticated owners and app-stream reads
**ID:** D-issue-61-artifact-auth-owner-stream
**Decided At:** 2026-07-29T10:19:41+02:00
**By:** Trinity
**Status:** active
**Supersedes:** []
**What:** Issue #61 should model each generated artifact with an authenticated owner subject, require that subject on generation and artifact reads in secure mode, return indistinguishable 404 responses for missing/unauthorized artifacts, and continue serving artifacts through the FastAPI application instead of issuing direct Blob/SAS redirects.
**Why:** The current UUID artifact route reads by artifact id only, so possession of the URL is the only authorization factor. Streaming through the app lets the web boundary enforce per-user authorization without exposing storage URLs or expanding the artifact-store port to mint user-scoped SAS URLs.
### D-switch-issue-61-artifact-auth-tests
**ID:** D-switch-issue-61-artifact-auth-tests
**Decided At:** 2026-07-29T10:19:41+02:00
**By:** Switch
**Status:** active
**Supersedes:** []
**What:** Issue #61 acceptance must be proven at the application artifact boundary with deterministic owner-identity tests: anonymous, missing/malformed/expired identity, non-owner, and legacy ownerless artifacts fail closed without leaking existence, while only the authenticated owner receives the image. PR smoke support must use real platform-compatible authentication or a clearly disabled-by-default test-only path; no production auth-bypass hook is acceptable.
**Why:** Current artifact URLs are opaque but unauthenticated, Blob privacy alone is insufficient, and existing tests prove anonymous UUID retrieval. The release gate needs falsifiable security evidence before any privacy claim is restored.
### D-issue-61-auth-design: Authenticated per-user artifact access — architecture decision
**ID:** D-issue-61-auth-design
**Decided At:** 2026-07-29T10:22:00+02:00
**By:** Morpheus (Lead)
**Status:** active
**Supersedes:** []
**What:** The recommended approach for issue #61 is Option B — app-level session auth with Entra ID via Container Apps Easy Auth, an `owner_subject` column on artifacts, and server-side proxy streaming through the existing FastAPI artifact route. This combines platform-managed identity (Entra ID) with minimal application-code coupling, preserves the existing blob-private-endpoint architecture, requires no SAS URL generation, and keeps the blast radius to one new middleware + one domain field.
**Why:** The app has no user concept today. Easy Auth provides identity at the platform layer without a custom login flow; the app only needs to read the `X-Ms-Client-Principal-Id` header injected by the sidecar. Streaming through FastAPI (already implemented) allows the authorization check to be a single `if artifact.owner != authenticated_subject: 404` gate. SAS-based options leak storage URLs and require new ports; fully custom auth (OAuth2 code flow in Python) is high-effort and error-prone. The trade-off is a Container Apps platform dependency, but this project already depends on Container Apps for hosting.
### D-untagged-pr-orphan-safety: Untagged PR resource-group orphan safety boundary
**ID:** D-untagged-pr-orphan-safety
**Decided At:** 2026-07-28T00:00:00+02:00
**By:** Tank
**Status:** active
**Supersedes:** []
**What:** The janitor retains its strict tag allowlist for normal automatic deletion. A separate legacy path may only report an untagged candidate after it exactly matches `rg-pr-<number>-<slug>-<hash8>`, its PR is absent from the active list, and GitHub verifies that the PR closed at least 24 hours ago. Deletion of that separate set requires a manual workflow dispatch with both the untagged-reap opt-in and dry-run disabled. The deployment workflow now creates the deterministic RG with lifecycle tags in the initial ARM request before `azd provision`.
**Why:** Untagged RGs cannot be safely identified by absence of metadata alone. Exact historical convention, independently verified closed-PR age, and explicit operator confirmation keep the shared Foundry RG and shared ACR outside the deletion boundary while repairing the tag-after-provision orphan window.
### D-issue-61-artifact-auth-platform: Issue #61 artifact authentication platform path
**ID:** D-issue-61-artifact-auth-platform
**Decided At:** 2026-07-29T10:19:41+02:00
**By:** Tank
**Status:** active
**Supersedes:** []
**What:** For this Azure Container Apps deployment, keep Blob private and continue serving artifact bytes through the application using the application user-assigned managed identity. Add user authentication/authorization at the app edge or in application code before making any privacy claim; do not expose Blob URLs or rely on UUID secrecy. Built-in ACA auth with Entra ID is viable for tenant users but creates PR-environment app-registration/callback management work. App-level sessions are likely the lowest-friction MVP path if consumer identities or many ephemeral PR URLs are required.
**Why:** The current storage account disables public network access, public Blob access, shared keys, and SAS, and the app identity has container-scoped Storage Blob Data Contributor. That protects storage from direct anonymous reads but not the public Container App route `/api/artifacts/{uuid}`. Per-user authorization must be enforced before the app reads Blob content.

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
### D-pr78-smoke-404-warmup-grace: Bounded retry window for transient health 404 during ACA revision warm-up
**ID:** D-pr78-smoke-404-warmup-grace
**Decided At:** 2026-07-29T15:45:00+02:00
**By:** Tank
**Status:** active
**Supersedes:** []
**What:** `infra/scripts/pr_smoke_test.py` now treats early `/health/live` and `/health/ready` HTTP 404 responses as retryable only inside a strict warm-up envelope (max 6 attempts and <45 seconds from smoke start). Outside that envelope, 404 remains fail-fast as `unexpected_status`.
**Why:** In PR environment deploys, ACA ingress/revision propagation can briefly route to no matching health path right after deploy/update, yielding short-lived 404 before the endpoint stabilizes to 200. Immediate fail-fast on first 404 creates false negatives that block downstream trusted auth configuration. A bounded grace preserves fail-closed behavior for persistent misroutes while absorbing startup jitter.

## Legacy Compatibility

Legacy import `4561565e05f4397117fc20b43fddf83059c10dab32df6209d595ddcdaef2cffa` is losslessly indexed in `decisions/archive/legacy-4561565e05f4397117fc20b43fddf83059c10dab32df6209d595ddcdaef2cffa.md`; use decision-ledger retrieval by legacy ID.
