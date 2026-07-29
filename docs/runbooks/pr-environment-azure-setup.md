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

The deploy workflow also references GitHub Environment
`azure-foundry-provisioning` for detector-positive Foundry exception PRs. That
job is an approval checkpoint only; it does **not** request `id-token: write` and
does not need a second Entra federated credential.

The optional `validate:live-foundry` job runs under `azure-pr-app`, requests
OIDC, and reads the target Foundry account, deployment, and RAI policy. It needs
`Microsoft.CognitiveServices/accounts/read`,
`Microsoft.CognitiveServices/accounts/deployments/read`, and
`Microsoft.CognitiveServices/accounts/raiPolicies/read` on the target account
or resource group. Without those permissions, the job must fail and no live
binding claim may be made.

## 1. Entra app registration + federated credential

- App registration display name: `squad-workshop-pr-envs`
- A service principal is created for that app.
- **No client secret** — federated credentials only.

Federated credential:

| Field     | Value                                                                            |
|-----------|----------------------------------------------------------------------------------|
| name      | `github-pr-app-environment`                                                      |
| issuer    | `https://token.actions.githubusercontent.com`                                    |
| subject   | `repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`       |
| audiences | `api://AzureADTokenExchange`                                                     |

The subject must match GitHub's OIDC claim exactly. This repository was created after GitHub's immutable OIDC subject rollout, so GitHub emits the owner/repository-id form shown above (`repo:bmoussaud@283453/squad-workshop@1308580663:environment:azure-pr-app`), not the shorter legacy `repo:{owner}/{repo}:environment:{env}` form. Verify against the `subject claim` line printed by `Azure/login` if GitHub changes its default subject behavior.

```bash
az ad app create --display-name squad-workshop-pr-envs
az ad sp create --id <appId>
# fedcred.json holds the four fields in the table above
az ad app federated-credential create --id <appId> --parameters fedcred.json
# If an old credential used repo:bmoussaud/squad-workshop:environment:azure-pr-app,
# add or replace it with the owner/repository-id subject above; otherwise
# Azure returns AADSTS700213 before any provision/teardown action runs.
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

## 3. GitHub Environments

Create `azure-pr-app` with **no required reviewers and no branch restrictions**.
A reviewer gate would block the automated teardown and janitor — the opposite of
what we want.

```bash
echo '{}' | gh api --method PUT repos/bmoussaud/squad-workshop/environments/azure-pr-app --input -
```

Create `azure-foundry-provisioning` with a required reviewer gate. Approving
this environment authorizes a rare, billable Foundry-per-PR exception: the run may
provision or change scarce `gpt-image-2` capacity/model/RBAC/region/safety paths,
subject to the workflow's one-active-Foundry-environment preflight cap. It does
not authorize prompts, generated image bytes, provider internals, tenant-bearing
endpoints, or credentials to be printed in logs or PR comments.

Design deviation: the design originally said required reviewers should be
"Benoit plus Tank or Morpheus". GitHub required reviewers must be real users or
teams; Tank and Morpheus are AI agents, and `bmoussaud` is currently the only
collaborator. Configure `bmoussaud` as the sole required reviewer and **do not**
enable "prevent self-review"; otherwise Benoit's own PRs would be permanently
unapprovable.

```bash
USER_ID=$(gh api users/bmoussaud --jq .id)
cat > foundry-environment.json <<EOF
{
  "wait_timer": 0,
  "reviewers": [
    { "type": "User", "id": ${USER_ID} }
  ],
  "prevent_self_review": false
}
EOF
gh api --method PUT repos/bmoussaud/squad-workshop/environments/azure-foundry-provisioning --input foundry-environment.json
rm foundry-environment.json
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
  --active-app-env-count 0 \
  --requires-foundry false --foundry-authorized false --active-foundry-env-count 0 \
  --format env
# -> decision=proceed / reason_code=ok
```

With an empty ACR name (the pre-configuration state) the same command returns
`reason_code=invalid_service_name` — that was the original blocker.

For a Foundry-scoped PR, the first preflight pass should return
`reason_code=foundry_unauthorized`; the workflow treats only that reason as
approval-pending and routes to `azure-foundry-provisioning`. After approval and
Azure login, the second preflight pass uses `--foundry-authorized true` plus the
live count of existing `environment-type=pr-foundry` resource groups. That second
pass is the authoritative no-bypass gate before `azd provision`.

Important trust boundary: the deploy workflow currently checks out PR head code,
so preflight and detector outputs are not trusted by themselves. Jobs that hold
OIDC credentials, approval authority, live validation, or PR-comment write access
also require GitHub event-context guards at the job level:

- `github.event.pull_request.head.repo.fork == false`
- `github.event.pull_request.head.repo.full_name == github.repository`
- `github.event.pull_request.draft == false`

Do not remove those guards when refactoring preflight. A future hardening issue
may run detector/preflight from base-ref content, but the job-level guards remain
the immediate non-forgeable boundary for forks and drafts.

The deploy workflow sets `DEPLOY_FOUNDRY=true` only when the
`azure-foundry-provisioning` approval job succeeds. Detection alone never
provisions Foundry; a detector false positive can at most request approval. Before
`azd provision`, the workflow also verifies the PR-controlled IaC has not
neutralized the switch: `infra/main.bicepparam` must read `deployFoundry` from
`DEPLOY_FOUNDRY` with default `'false'`, and `infra/main.bicep` must pass that
parameter through to `foundry.bicep`.

## 6. Foundry exception teardown and cap recovery

Foundry exception resource groups are tagged `environment-type=pr-foundry` so the
deploy workflow can enforce `FOUNDRY_CONCURRENCY_CAP=1` by counting active
exception groups. That cap only works if the count can return to zero.

Teardown policy:

- **Close-time teardown deletes both `pr-app` and `pr-foundry` groups** for the
  exact closed PR number. PR closure is an explicit lifecycle event, so this is
  the deterministic reclaim path for billable/scarce Foundry capacity.
- **The daily TTL janitor auto-deletes only `pr-app` groups.** It deliberately
  does not infer deletion of `pr-foundry` groups from TTL alone, because
  cost-bearing Foundry/model/RBAC resources deserve operator review before an
  inferred cleanup action.
- The janitor still queries `pr-foundry` groups and emits workflow warnings plus a
  step-summary table when one is expired, has malformed expiry metadata, or is
  tied to a recently closed PR. Treat those warnings as manual cleanup tickets.

If a Foundry exception PR was closed and future exceptions remain blocked by
`foundry_concurrency_cap`, first inspect the close-time teardown run for that PR.
If the run failed, delete only the resource group tagged with that PR's
`pr-number`, `ephemeral=true`, and `environment-type=pr-foundry`; then rerun the
preflight.

## 7. Non-PR Foundry provisioning is explicit

`infra/main.bicepparam`, `infra/main.bicep`, and `infra/foundry.bicep` all fail
closed for Foundry provisioning. Manual dev/main/prod runs that intentionally
create or update the long-lived Foundry account/project/model deployment must set:

```bash
export DEPLOY_FOUNDRY=true
azd provision --preview
azd provision
```

No current GitHub workflow depends on the old permissive default. The only
automated workflow that runs `azd provision` is the PR environment workflow, and
it now derives `DEPLOY_FOUNDRY` from the Foundry approval job rather than from
path/label detection.
