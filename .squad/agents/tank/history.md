# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T12:33:43+0000): Azure resources must always be configured through Bicep; prefer Azure Verified Modules when a suitable maintained module exists, with native Bicep as the fallback — decided by bmoussaud

📌 Team update (2026-07-22T12:49:52+0000): Prefer Azure Container Apps with dedicated workload profiles for production hosting in France Central; use Microsoft Foundry in Sweden Central subject to exact region, model, SKU, quota, capacity, and feature validation; prefer user-assigned managed identities with least privilege and separate identities across trust boundaries — decided by bmoussaud

📌 Team update (2026-07-22T13:28:52+0000): Use `azd` and `azure.yaml` for Azure application deployment; authenticate with `azd auth login`, with `az login` as a fallback — decided by bmoussaud

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Neo's second `gpt-image-2` revision because PNG validation accepts valid PNG data with trailing bytes and the ignored egg-info directory remains on disk. Trinity and Neo may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank completed the independent final `gpt-image-2` revision without participation from locked-out authors. Switch approved it with no findings after 22 tests, `compileall`, `uv lock --check`, `git diff --check`, and egg-info absence validation passed. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank updated `create_foundry_client` endpoint normalization to support user-supplied `https://<resource>.services.ai.azure.com/openai/v1` endpoints while retaining `*.openai.azure.com`, added `size=1024x1024`, and preserved Azure identity, token scope, timeout, and zero-retry behavior. Switch approved with no findings after 24 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank fixed Foundry 500 `Unable to get resourceinformation` by removing unsupported extra `output_format`, matching the user's working `images.generate` request body, normalizing the base URL without changing the outbound route, and making 5xx errors provider-neutral without body leakage. Switch approved after 25 tests and repository checks passed; no live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank repaired user-edited Foundry regressions by restoring scope `https://ai.azure.com/.default`, bounded timeout, and `max_retries=0`, removing debug prints, retaining the exact request shape, and covering real `openai.InternalServerError` through adapter and CLI without traceback or body leakage. Switch approved after 27 tests and repository checks passed. Runtime used `*.openai.azure.com` while the authoritative sample uses `*.services.ai.azure.com/openai/v1`; endpoint/deployment pairing remains the service-side fix. No live Azure call or commit was made. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Switch rejected Trinity's artifact persistence revision because UUID collisions can overwrite existing finalized artifacts and failed temporary writes can leave partial temp files. Trinity may neither revise nor advise; Tank owns the next revision independently. — decided by Switch

📌 Team update (2026-07-22T13:11:01+0000): Tank independently completed the artifact persistence revision. Artifacts expose `file_path`; `InMemoryArtifactStore` writes beneath the configured output directory using exact artifact-ID filenames, a png/txt/bin allowlist, atomic exclusive publication, collision no-overwrite, guaranteed temporary cleanup, and memory updates only after publication succeeds. `FANTASY_CARD_OUTPUT_DIR`, CLI JSON, and README support were included. Switch approved after 33 tests and repository checks passed; no commit was made. — decided by Switch

📌 Team update (2026-07-22T16:01:59+0000): Prepared `azure.yaml` and Bicep for subscription `external-bmoussaud-ms`, Sweden Central, resource group `rg-fantasy-cards-dev-8f327f8c`, Foundry account/project `fnd-fantasy-cards-dev-8f327f8c` / `prj-fantasy-cards-dev-8f327f8c`, and deployment `gpt-image-2-dev`. Bicep and azd validation passed; provisioning remains blocked on explicit user approval and no Azure resources were created. — decided by Morpheus, Tank, and Neo
