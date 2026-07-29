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
### D-switch-issue-61-session-auth-tests: Issue #61 app-owned Entra OIDC session auth tests
**ID:** D-switch-issue-61-session-auth-tests
**Decided At:** 2026-07-29T10:56:35+02:00
**By:** Switch
**Status:** active
**Supersedes:** ["D-switch-issue-61-artifact-auth-tests"]
**What:** Issue #61 acceptance must be proven against app-owned Entra ID single-tenant OIDC authorization-code flow plus app-managed session cookies, not Easy Auth identity headers and not local passwords or invite/shared secrets. Anonymous users are denied everywhere except agreed health probes; OIDC state, nonce, PKCE, redirect URI allowlisting, ID-token validation, open-redirect resistance, and malformed/tampered/expired/fixed/replayed/missing session cookies fail closed; opaque owner identifiers bind generation and artifact reads; pre-existing ownerless artifacts are not migrated and age out through the 30-day lifecycle; artifact authorization preserves indistinguishable 404 responses for missing/non-owner resources. PR smoke support must use real OIDC/session authentication or a disabled-by-default test identity that is impossible to enable in production; no production auth-bypass hook is acceptable.
**Why:** The product decision moved identity from platform-injected headers to in-application Entra OIDC plus session cookies. That removes the unautomatable Easy Auth header-spoofing threat, makes OIDC and session-cookie failure modes directly unit/integration-testable in-process, revives redirect-URI management cost for ephemeral PR environments, and makes CSRF a first-class risk for cookie-authenticated POST routes.
### D-issue-61-artifact-auth-platform-revised: Issue #61 in-app Entra OIDC platform path
**ID:** D-issue-61-artifact-auth-platform-revised
**Decided At:** 2026-07-29T11:00:31+02:00
**By:** Tank
**Status:** active
**Supersedes:** ["D-issue-61-artifact-auth-platform"]
**What:** For issue #61, keep Blob private and continue serving artifact bytes through the application using the application user-assigned managed identity, with authorization enforced before any Blob read. The Product Owner-selected identity model is in-app Entra ID OIDC authorization-code flow for a single tenant followed by an app-managed session cookie. This rejects Container Apps Easy Auth and authConfigs, but it does require an Entra app registration, redirect URI management, OIDC client/session secrets, and per-PR redirect URI automation or an explicit decision not to exercise interactive auth in PR environments.
**Why:** The storage posture still protects artifacts from direct anonymous Blob reads, but the public application route remains the authorization boundary. Owning the OIDC flow in application code removes the ACA Easy Auth sidecar but does not remove Entra callback friction; ephemeral PR FQDNs still need registered redirect URIs, and the application must correctly validate state, nonce, PKCE, token issuer/audience/expiry/signature, and post-login return URLs.
### D-issue-61-auth-design-revised: Authenticated per-user artifact access — revised architecture per PO ruling
**ID:** D-issue-61-auth-design-revised
**Decided At:** 2026-07-29T11:01:00+02:00
**By:** Morpheus (Lead), ratifying Benoit Moussaud (Product Owner) ruling
**Status:** active
**Supersedes:** ["D-issue-61-auth-design"]
**What:** The architecture for issue #61 is: (1) Identity provider: Entra ID, single tenant. (2) Auth flow: in-app OIDC authorization-code flow with PKCE, owned entirely by the application — NOT Container Apps Easy Auth, NOT a platform sidecar. (3) Session: app-managed signed/encrypted cookie after the OIDC exchange; session signing key from Key Vault. (4) Anonymous usage: not allowed anywhere; fail-closed middleware rejects unauthenticated requests before they reach route handlers. (5) Pre-existing ownerless artifacts: auto-deleted via the existing 30-day blob lifecycle policy (`infra/web.bicep:113-120`). (6) Owner identifier: the Entra ID token `sub` claim (opaque per-app GUID). (7) Cache policy for artifact responses: open, pending PO decision — recommendation is `private, no-store`. (8) OIDC library: `authlib` (new dependency, not currently in pyproject.toml). (9) Local passwords and invite codes explicitly rejected by PO — no credential storage surface. (10) Per-PR redirect-URI problem remains open and carries real cost (see architecture notes).
**Why:** The PO explicitly chose in-app OIDC over Easy Auth and explicitly rejected local passwords and invite codes. Easy Auth was originally recommended for its platform-edge fail-closed property, but the PO accepts that the application itself must enforce fail-closed semantics and prefers the simpler operational model. The original decision conflated "app-level session auth" and "Easy Auth" as if they were one option — they are architecturally distinct. This revision corrects the record and fully specifies the credential source, session management, and OIDC security requirements. The "high-effort and error-prone" assessment of in-app OAuth2 is mitigated by using `authlib` (a maintained, audited OIDC relying-party library) rather than hand-rolling the flow, and by the reduced complexity of a single-tenant scenario with one static redirect URI in dev.

## Legacy Compatibility

Legacy import `4561565e05f4397117fc20b43fddf83059c10dab32df6209d595ddcdaef2cffa` is losslessly indexed in `decisions/archive/legacy-4561565e05f4397117fc20b43fddf83059c10dab32df6209d595ddcdaef2cffa.md`; use decision-ledger retrieval by legacy ID.
