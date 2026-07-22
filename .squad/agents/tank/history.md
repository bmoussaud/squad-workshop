# Project Context

- **Owner:** bmoussaud
- **Project:** Python application on Azure for generating fantasy trading-card-style imagery
- **Stack:** Python, Azure, generative image models
- **Created:** 2026-07-22T11:30:53+00:00

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 Team update (2026-07-22T12:33:43+0000): Azure resources must always be configured through Bicep; prefer Azure Verified Modules when a suitable maintained module exists, with native Bicep as the fallback — decided by bmoussaud

📌 Team update (2026-07-22T12:49:52+0000): Prefer Azure Container Apps with dedicated workload profiles for production hosting in France Central; use Microsoft Foundry in Sweden Central subject to exact region, model, SKU, quota, capacity, and feature validation; prefer user-assigned managed identities with least privilege and separate identities across trust boundaries — decided by bmoussaud
