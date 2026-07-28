# Runbook: Azure/GitHub setup for per-PR ephemeral environments

Reproducible configuration that unblocks the `PR Azure Environment` workflows
(deploy, teardown, janitor). This is **configuration only** — no application or
infra code depends on running these steps, but the workflows are inert without
them. Ref: issue #29.

## What consumes this

All three workflows run their OIDC-authenticated job under GitHub Environment
`azure-pr-app`:

- `.github/workflows/pr-environment.yml` (deploy, `id-token: write`)
- `.github/workflows/pr-environment-teardown.yml` (close-time teardown)
- `.github/workflows/pr-environment-janitor.yml` (daily TTL janitor)

Because all three declare `environment: azure-pr-app` on the job holding
`id-token: write`, a **single** federated credential covers all three.

## 1. Entra app registration + federated credential

- App registration display name: `squad-workshop-pr-envs`
- A service principal is created for that app.
- **No client secret** — federated credentials only.

Federated credential:

| Field     | Value                                                       |
|-----------|-------------------------------------------------------------|
| name      | `github-pr-app-environment`                                 |
| issuer    | `https://token.actions.githubusercontent.com`               |
| subject   | `repo:bmoussaud/squad-workshop:environment:azure-pr-app`    |
| audiences | `api://AzureADTokenExchange`                                |

The subject must match GitHub's OIDC claim exactly: `repo:{owner}/{repo}:environment:{env}`.

```bash
az ad app create --display-name squad-workshop-pr-envs
az ad sp create --id <appId>
# fedcred.json holds the four fields in the table above
az ad app federated-credential create --id <appId> --parameters fedcred.json
```

## 2. RBAC (subscription scope)

Assign to the service principal at `/subscriptions/9479b396-5d3e-467a-b89f-ba8400aeb7dd`:

| Role                                      | Why                                                                                          |
|-------------------------------------------|----------------------------------------------------------------------------------------------|
| `Contributor`                             | Create/delete the per-PR resource group and the app-tier resources inside it.                |
| `Role Based Access Control Administrator` | The Bicep creates role assignments (ACR pull, Foundry access) for the app managed identities.|

Subscription scope is required because every PR provisions a brand-new resource
group. **Owner is deliberately NOT granted** — Contributor + RBAC Admin is the
minimum that lets Bicep both create resources and grant the identities their roles.

```bash
SP=<sp-object-id>; SUB=/subscriptions/9479b396-5d3e-467a-b89f-ba8400aeb7dd
az role assignment create --assignee-object-id $SP --assignee-principal-type ServicePrincipal --role "Contributor" --scope $SUB
az role assignment create --assignee-object-id $SP --assignee-principal-type ServicePrincipal --role "Role Based Access Control Administrator" --scope $SUB
```

## 3. GitHub Environment

Create `azure-pr-app` with **no required reviewers and no branch restrictions**.
A reviewer gate would block the automated teardown and janitor — the opposite of
what we want.

```bash
echo '{}' | gh api --method PUT repos/bmoussaud/squad-workshop/environments/azure-pr-app --input -
```

## 4. Repository Actions variables (not secrets)

These are variables because none is sensitive and the workflows read `vars.*`.

| Variable                                        | Value                                    |
|-------------------------------------------------|------------------------------------------|
| `SHARED_CONTAINER_REGISTRY_NAME`                | `acrfantasycardsnrp2z4rl3jd32`           |
| `SHARED_CONTAINER_REGISTRY_RESOURCE_GROUP_NAME` | `rg-fantasy-cards-dev-8f327f8c`          |
| `SHARED_FOUNDRY_ACCOUNT_NAME`                   | `fnd-fantasy-cards-dev-8f327f8c`         |
| `SHARED_FOUNDRY_PROJECT_NAME`                   | `prj-fantasy-cards-dev-8f327f8c`         |
| `SHARED_FOUNDRY_RESOURCE_GROUP_NAME`            | `rg-fantasy-cards-dev-8f327f8c`          |
| `SHARED_MODEL_DEPLOYMENT_NAME`                  | `gpt-image-2-dev`                        |
| `AZURE_ALERT_CONTACT_EMAILS`                    | `bmoussaud@microsoft.com`                |
| `AZURE_CLIENT_ID`                               | `<appId from step 1>`                    |
| `AZURE_TENANT_ID`                               | `be38c437-5790-4e3a-bb56-4811371e35ea`   |
| `AZURE_SUBSCRIPTION_ID`                         | `9479b396-5d3e-467a-b89f-ba8400aeb7dd`   |
| `AZURE_LOCATION`                                | `swedencentral`                          |

`AZURE_ALERT_CONTACT_EMAILS` is split on `;` by `infra/main.bicepparam`; a single
address needs no separator. `AZURE_LOCATION` is `swedencentral` to match
`param location` and the shared resource group. The remaining ~10 Bicep params
(workload profile, CPU/memory, budget, alert flags) are written at runtime by
`pr-environment.yml`, so they are not repo variables.

```bash
gh variable set <NAME> --repo bmoussaud/squad-workshop --body "<value>"
```

## 5. Verifying the preflight gate

`infra/scripts/pr_preflight.py` computes environment names **before** checking the
ACR name. A branch that does not follow `squad/{issue}-{slug}` fails closed with
`reason_code=invalid_names` and never reaches the ACR check. A conforming branch
with the real ACR name returns `decision=proceed`:

```bash
python infra/scripts/pr_preflight.py \
  --repo bmoussaud/squad-workshop --pr-number <n> --branch squad/<n>-<slug> \
  --is-fork false --is-draft false \
  --base-repo bmoussaud/squad-workshop --head-repo bmoussaud/squad-workshop \
  --referenced-acr-name acrfantasycardsnrp2z4rl3jd32 \
  --active-app-env-count 0 --format env
# -> decision=proceed / reason_code=ok
```

With an empty ACR name (the pre-configuration state) the same command returns
`reason_code=invalid_service_name` — that was the original blocker.
