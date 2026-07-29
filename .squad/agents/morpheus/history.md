# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Summarized Learnings

<!-- Summarized by Scribe on 2026-07-29T11:05:00+02:00 because the history exceeded 15KB. Keep concise lasting context below. -->

### Standing architecture guidance
- Morpheus is the lead architecture voice for application/platform tradeoffs, governance gates, and cross-agent synthesis. Keep recommendations explicit about risks, rejected alternatives, and Product Owner decisions.
- Azure deployment direction remains Container Apps + private Blob + managed identities + Bicep/azd. Prefer fail-closed application boundaries and least-privilege identities; do not expose Blob URLs or rely on UUID secrecy.
- For PR-environment work, branches must follow `squad/{issue}-{slug}`. `AZURE_ENV_NAME` is capped at 40 chars from the current ARM deployment-name budget; re-derive if Bicep module prefixes grow. Bicep `existing` references need explicit `dependsOn` when ordering matters.

### Durable project decisions and corrections
- Foundry `gpt-image-2` contract: opt-in configuration, OpenAI v1 Azure endpoint, managed identity token scope `https://ai.azure.com/.default`, strict endpoint and PNG validation, bounded timeout, no retries, and safe errors. Live Azure invocation moved from initially pending to dev-approved after Product Owner approval.
- Storage policy blocks authenticated public endpoints; the accepted recovery path is VNet-integrated Container Apps with Blob private endpoint/private DNS.
- Application Insights with local auth disabled requires explicit UAMI-backed `ManagedIdentityCredential` and component-scoped Monitoring Metrics Publisher.
- Dev Azure infrastructure is deployed in `rg-fantasy-cards-dev-8f327f8c`; `gpt-image-2-dev` succeeded. CI exists, but branch protection is not enabled.
- Benoit accepted GlobalStandard non-EU inference for `gpt-image-2` in dev and production; data at rest/artifacts remain in France Central/customer-designated storage.
- Production remains gated by user-facing AI notice, retention/deletion policy, likeness/IP/minors/content policy, and RAI/provider enforcement follow-up.
- Coordinator canary checks apply only to Squad coordinator sessions; worker sessions do not receive `squad.agent.md` and must not be halted by that rail.

### Review and remediation history
- Under strict reviewer lockout, Morpheus reviewed or coordinated independent repairs for `gpt-image-2`, artifact persistence, PR preflight, PR environment phases, green-background accessibility, and production-gating docs.
- Phase 3 PR-environment architecture: app URL resolution must use the deployed private app service URI (`SERVICE_WEB_URI`), not the public Container App placeholder.
- Phase 4 lifecycle closed per-PR environment provisioning/teardown/janitor loops; deletion remains tag-scoped and malformed input exits must be concrete and tested.

### Issue #61 artifact authorization
- Current risk: `/api/artifacts/{uuid}` is publicly reachable through the app; Blob is private, but the app has no user/owner concept and artifact UUID possession is the only authorization factor.
- Initial recommendation favored Container Apps Easy Auth plus owner-bound app-streamed reads. The Product Owner later rejected Easy Auth and selected app-owned single-tenant Entra OIDC with app-managed session cookies.
- Revised #61 architecture: Entra ID single tenant; in-app OIDC authorization-code flow with PKCE; signed/encrypted session cookie; session key from Key Vault; anonymous usage denied except agreed health probes; owner identifier is the Entra `sub` claim; pre-existing ownerless artifacts age out via the existing 30-day lifecycle; cache policy remains open with `private, no-store` recommended.
- Use `authlib` rather than hand-rolled OAuth/OIDC. The high-effort/error-prone risk still applies to in-app auth, but is bounded by a maintained library and single-tenant scope.
- Per-PR redirect-URI friction is not eliminated by app-owned OIDC; PR auth strategy remains open. A fail-closed artifact-store guard would currently break PR environments because `FANTASY_CARD_ARTIFACT_STORE` is hardcoded to `blob`.
- Concrete OIDC/session risks to keep in design and tests: state/nonce replay, PKCE downgrade, ID-token signature/audience/issuer/expiry bypass, open redirects, session fixation/replay/tampering/expiry, and CSRF on cookie-authenticated POST routes.
- 2026-07-29T11:11:09+02:00: PO closed final open items. Cache policy decided: `private, no-store`. PR environments: per-PR Entra app registrations (Tank Option B); `local-anonymous` rejected — my guard was self-defeating (`web.bicep:368-369`/`:500-501` hardcode `blob`, PR envs deploy same module). Consequence: `FANTASY_CARD_AUTH_MODE` eliminated entirely — no mode switch, no bypass surface, Switch's no-bypass requirement met by construction. Local dev: dedicated Entra app registration with `http://localhost:8000/auth/callback`. Session signing key: maintained Key Vault position over Tank's Container App secrets (rotation audit, soft-delete, RBAC justify the marginal complexity); Tank's two-key ring is correct but should read from KV versions. Superseded D-issue-61-auth-design-revised with D-issue-61-design-closed. Lesson: the fail-closed guard instinct was right, but the environment-model assumption behind it was unchecked against the actual Bicep.

- 2026-07-29T11:16:00+02:00: Corrected two errors in D-issue-61-design-closed after coordinator review. (1) Registration model: my decision said "per-PR registrations" in one clause and described a shared registration with dynamic redirect URIs in another — contradictory. Corrected to consistently describe per-PR registrations with per-PR client secrets, because a shared client secret across prod and ephemeral PR environments contradicts the blast-radius principle. Lifecycle: create at deploy, patch redirect URI after SERVICE_WEB_URI resolves, delete at teardown, janitor sweeps orphans via Graph. (2) Key Vault cost: I claimed "marginal complexity" but there is zero Key Vault in `infra/` today — the real cost is a new resource, private endpoint, RBAC, and granting the managed identity secret-read permission (exactly what Tank wanted to avoid). Conceded: Tank is right for MVP. Container App secrets with a two-key ring are adequate for a single-tenant internal tool. Key Vault is the right hardening step if the tool grows to multi-tenant or external-facing, but the infrastructure cost is disproportionate now. Honest error: I understated the cost to win the argument.

📌 Team update (2026-07-29T11:11:09+02:00): LESSON from issue #61 closure: a proposed guard must be checked against the actual environment model before using it in architecture. The fail-closed guard instinct was sound, but it assumed PR environments could opt out of Blob, while `FANTASY_CARD_ARTIFACT_STORE` is hardcoded at `infra/web.bicep:369` and `:501` and PR environments provision the same module via `main.bicep:173`. Also verify cost claims against the repo before using them in an argument; Key Vault was not already present, so the real MVP cost was a new vault, private endpoint, RBAC, and managed-identity secret-read surface. — recorded by Scribe
