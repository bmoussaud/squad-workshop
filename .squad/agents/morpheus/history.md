# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T12:49:52+0000): Approved the Azure deployment architecture preference for dedicated-profile Azure Container Apps in France Central, Microsoft Foundry in Sweden Central subject to pre-provisioning validation, and least-privilege user-assigned managed identities separated across trust boundaries — decided by bmoussaud; reviewed by Morpheus

📌 Team update (2026-07-22T13:11:01+0000): The provider-neutral `gpt-image-2` Foundry contract was implemented and approved: opt-in configuration, OpenAI v1 Azure endpoint, managed identity token scope `https://ai.azure.com/.default`, strict endpoint and PNG validation, bounded timeout, no retries, and safe errors. Live Azure invocation remains pending authentication. — decided by Morpheus; approved by Switch

📌 Team update (2026-07-22T16:01:59+0000): The mandatory Foundry design review established a Bicep/azd lifecycle with an explicit billable deployment gate. The Sweden Central target for `gpt-image-2` is prepared and validated, but provisioning awaits bmoussaud's explicit approval and acceptance of cross-geography processing plus default content and abuse monitoring. No Azure resources were created. — decided by Morpheus, Tank, and Neo

📌 Team update (2026-07-23T08:32:26+0000): Facilitated the overdue weekly retrospective. The review captured three rejected revisions as contract-quality lessons, confirmed the deployment delay as a deliberate governance gate, and created retro-action issues #2, #3, and #4. — recorded by Scribe

📌 Team update (2026-07-23T09:03:12+0000): Rejected PR #6 v1 because bare `git diff --check` did not inspect committed CI ranges, strictly locked Switch out, and assigned Tank as independent revision owner. Approved Tank's corrected PR/push/initial-push ranges and pinned action SHAs after all gates and 34 tests passed; GitHub recorded both reviews as `COMMENTED` due author self-review restrictions. — recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Management-group policy enforces Storage `publicNetworkAccess=Disabled`, superseding the authenticated-public-endpoint repair. The approved recovery design is a separately authorized parallel VNet-integrated Container Apps environment with Blob private endpoint and private DNS; bmoussaud chose hold state unchanged, so generation remains safely degraded and D4 charges continue. — decided by Morpheus; recorded by Scribe

📌 Team update (2026-07-23T08:27:28+0000): Application Insights with local authentication disabled requires the Python exporter to receive the explicit user-assigned `ManagedIdentityCredential` and the identity to hold component-scoped Monitoring Metrics Publisher. The repaired revision is healthy at 100% traffic, but ingestion remains propagation pending. — recorded by Scribe
