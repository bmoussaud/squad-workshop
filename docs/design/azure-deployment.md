# Azure Deployment Design

Status: implemented locally; awaiting Azure Validate and separate deployment approval.

## Implemented Deployment Contract

The approved web-hosting slice is represented by `azure.yaml`, `infra/main.bicep`, `infra/web.bicep`, `infra/main.bicepparam`, and the repository-root `Dockerfile`.

- The azd service name is `web`, with repository-root project/build context and Azure Container Apps hosting.
- The Container Apps environment contains only a dedicated workload profile named `dedicated`; its exact type and instance bounds remain required validation inputs and cannot fall back to Consumption.
- The Container App exposes HTTPS ingress on port 8000, runs one Uvicorn worker with total HTTP concurrency limited to 16, keeps one to two replicas, scales at one concurrent HTTP request per replica, and probes `/health/live` and `/health/ready`.
- The existing application user-assigned identity is attached to the app and receives deterministic `AcrPull` at registry scope, `Storage Blob Data Contributor` at the private artifact-container scope, and `Monitoring Metrics Publisher` at the Application Insights component scope. Explicit ARM dependencies make the registry assignment wait for the registry AVM deployment and the container assignment wait for the Storage AVM deployment, which creates `artifacts`. Registry admin credentials, Storage shared keys, anonymous image pull, anonymous Blob access, storage connection strings, and SAS tokens are disabled or absent.
- `infra/scripts/retire_legacy_storage_blob_role.py` is an explicitly invoked **after-deployment maintenance** action, not an `azd` hook. Bicep/ARM incremental deployments do not delete an omitted resource, and the old Storage AVM assignment has a different account-scope GUID from the new container-scope assignment. The private Blob route is delivered by the Bicep container-scope assignment; deployment is never blocked if an operator cannot enumerate or delete the legacy account-scope assignment.
- An authorized operator runs the cleanup separately in PowerShell after `azd up`, with Azure CLI set to the deployment subscription:

  ```powershell
  $subscription = azd env get-value AZURE_SUBSCRIPTION_ID
  az account set --subscription $subscription
  $env:AZURE_RESOURCE_GROUP = azd env get-value AZURE_RESOURCE_GROUP
  $env:AZURE_STORAGE_ACCOUNT_URL = azd env get-value AZURE_STORAGE_ACCOUNT_URL
  $env:APPLICATION_IDENTITY_PRINCIPAL_ID = azd env get-value APPLICATION_IDENTITY_PRINCIPAL_ID
  python infra\scripts\retire_legacy_storage_blob_role.py
  ```

  The operator needs least-privilege permission to read and delete `Microsoft.Authorization/roleAssignments` at the Storage account and `artifacts` container scopes (plus read access needed to resolve the Storage account). The script queries the direct `Storage Blob Data Contributor` assignment only at those exact scopes, using Azure CLI's supported `--assignee` object-ID filter. It fails closed if Azure CLI cannot run, enumeration or deletion fails, the container assignment is absent or ambiguous, the account-scope legacy assignment is absent or ambiguous, or post-delete verification fails. It deletes only after finding exactly one verified direct legacy assignment for the application principal; errors include redacted Azure CLI diagnostics and never report retirement as successful. Successful cutover validation shows exactly one direct role assignment on `.../blobServices/default/containers/artifacts`, none on the storage-account scope, and successful private-app Blob read/write. The original app/environment remains available for traffic rollback, but rollback must not redeploy the pre-migration Storage AVM role configuration because that would reintroduce account-wide Blob access. Any emergency regrant is a separate, approved break-glass action.
- Storage is general-purpose v2 `Standard_LRS`; the private `artifacts` container deletes block blobs 30 days after creation. Storage public network access is disabled. A parallel `-private` Container Apps environment is created with an external dedicated workload profile on a delegated `/27` infrastructure subnet; its `-private` app keeps public HTTPS ingress while resolving Blob through a private endpoint on a separate `/28` subnet. The private endpoint explicitly waits for the Storage AVM deployment because its Blob service ID comes from an existing-resource reference, and its `blob` connection is associated with `privatelink.blob.core.windows.net` through a private DNS zone, VNet link, and zone group.
- The original Container Apps environment and app remain unchanged for rollback. The `-private` app retains the application UAMI and its exact registry, artifact-container, and Application Insights RBAC scopes. `azd` outputs select the `-private` app for validation and deployment preparation; changing external traffic or deleting the original resources requires separate approval after private Blob connectivity is validated.
- Existing Log Analytics and Application Insights resources are reused. Application Insights keeps local authentication disabled; Azure Monitor OpenTelemetry uses the application UAMI selected by `AZURE_CLIENT_ID`, while its connection string supplies telemetry routing metadata. Container Apps environment/app, registry, and Blob diagnostics target the existing workspace.
- A resource-group monthly budget sends actual-spend notifications at 50%, 80%, and 100% through one action group. Budget amount and recipients remain mandatory environment inputs.
- Alert resources cover HTTP 5xx, readiness, provider, Blob, and replica-ceiling conditions. FastAPI request spans populate `AppRequests`; structured application logs populate `AppTraces` properties `dependency`, `success`, and `error_code`. Provider alerts select the `provider` dependency and authentication, throttle, timeout, and unavailable codes; Blob alerts select failed `blob` dependency events. Application-signal alerts remain disabled until Azure Validate confirms these tables and KQL property projections in the target workspace. The replica alert is enabled but still requires metric availability validation.

The Bicep parameter file intentionally reads unresolved deployment facts from environment variables:

| Variable | Validation purpose |
| --- | --- |
| `AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_TYPE` | Exact France Central dedicated profile type/SKU |
| `AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_MIN_COUNT` / `AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_MAX_COUNT` | Approved profile capacity bounds |
| `AZURE_CONTAINER_APP_CPU` / `AZURE_CONTAINER_APP_MEMORY` | App allocation compatible with the selected profile |
| `AZURE_MONTHLY_BUDGET_AMOUNT` | Approved monthly amount in billing currency |
| `AZURE_BUDGET_START_DATE` | Deterministic ISO 8601 budget start aligned to the first day of a month |
| `AZURE_ALERT_CONTACT_EMAILS` | Semicolon-separated notification recipients |
| `AZURE_ENABLE_APPLICATION_SIGNAL_ALERTS` | `true` only after alert query/table validation; otherwise `false` |

No tenant, subscription, profile capacity, budget, alert support, model capacity, or pricing value is inferred by the implementation. Provisioning and deployment remain prohibited until Azure Validate confirms those inputs and a non-mutating preview, and the user separately approves the billable action.

## Decision Summary

Use a single **Azure Container Apps** HTTP application as the initial production host in a Container Apps environment with a **dedicated workload profile**, backed by **Azure Blob Storage** for generated images and artifact metadata. Prefer **France Central** for application and platform resources, subject to service and SKU availability, quota, data-residency, latency, and recovery validation. Assign a **user-assigned managed identity** for Azure access, keep any model-provider credential that cannot use Microsoft Entra authentication in **Azure Key Vault**, and send platform logs to an **Azure Monitor Log Analytics workspace**. Instrument application and agent traces and metrics with OpenTelemetry and export them to **Azure Monitor Application Insights**.

Use **Microsoft Foundry** as the approved platform for agent capabilities and model access without selecting a final model in this design. Prefer **Sweden Central** for the Foundry project and deployments, but revalidate the required Foundry features, model and version, deployment SKU, quota, and available capacity immediately before provisioning. The application-to-Foundry path is therefore cross-region by default; production approval requires measured and accepted latency, data-residency behavior, network path, egress cost, and failure coupling between France Central and Sweden Central.

Start with synchronous orchestration only while measurements support it. Keep the existing job-shaped application contract and cloud-neutral ports for model invocation, artifact storage, and job state. If the queue trigger below is reached, split request intake from generation by adding a queue and a separately scaled worker; do not move orchestration logic into Azure SDK bindings or hosting-framework callbacks.

This recommendation is conditional on the assumptions below. It is not a claim that Container Apps is always cheaper or faster than the alternatives.

## Infrastructure as Code Standard

Configure all Azure resources through Bicep. Every project-owned `.bicep` file must declare `targetScope = 'resourceGroup'`; `ressourceGroup` is not valid Bicep syntax. The deployment orchestrator or calling context must create or select the containing resource group before invoking the templates.

Use Azure Verified Modules (AVM) first for all project-owned infrastructure. Check both AVM resource and pattern modules, pin every selected module to an exact stable version, and preserve the intended security, lifecycle, dependency, and output contracts when mapping module parameters. Native Bicep is allowed only when no suitable maintained AVM preserves the required contract; each fallback is documented below. Do not switch to ARM JSON, Terraform, or imperative CLI provisioning scripts, except for the narrowly scoped, manually invoked RBAC retirement maintenance action above: ARM incremental mode has no declarative delete for an omitted legacy role assignment. Use `.bicepparam` files for environment-specific parameter values.

Current exact-version AVMs are user-assigned identity `0.6.0`, Log Analytics workspace `0.16.0`, Application Insights component `0.8.0`, Cognitive Services account `0.15.1`, Container Registry `0.9.3`, Storage account `0.9.1`, Container App `0.9.0`, Virtual Network `0.9.0`, Private Endpoint `0.9.1`, and Private DNS Zone `0.8.1`. The Foundry account AVM owns the account, model deployment, diagnostics, and the narrow `Cognitive Services OpenAI User` role assignment. The Storage AVM owns the private artifact container, Blob retention, lifecycle rule, and Blob diagnostics. The network AVMs own the VNet/subnets, Blob private endpoint and its DNS zone group, and the Blob private DNS zone with its VNet link.

<!-- native-bicep-fallback: infra/foundry.bicep/foundryProject | Microsoft.CognitiveServices/accounts/projects | The Cognitive Services account AVM does not create Foundry project child resources; the available Foundry pattern module would replace the approved user-assigned identity design with system-assigned identities. -->
<!-- native-bicep-fallback: infra/web.bicep/containerAppsEnvironment | Microsoft.App/managedEnvironments | The maintained managed-environment AVM requires a Log Analytics shared key for app logs, which violates the approved secretless telemetry contract. -->
<!-- native-bicep-fallback: infra/web.bicep/privateContainerAppsEnvironment | Microsoft.App/managedEnvironments | The maintained managed-environment AVM requires a Log Analytics shared key for app logs, which violates the approved secretless telemetry contract while the private environment must use Azure Monitor logging and an infrastructure subnet at creation. -->
<!-- native-bicep-fallback: infra/web.bicep/acrPullAssignment | Microsoft.Authorization/roleAssignments | The registry AVM supports registry-scoped assignments, but this explicit assignment preserves the existing deterministic name and role-definition-ID contract. -->
<!-- native-bicep-fallback: infra/web.bicep/blobDataAssignment | Microsoft.Authorization/roleAssignments | The Storage AVM does not expose the required artifact-container scope for this least-privilege assignment. -->
<!-- native-bicep-fallback: infra/web.bicep/monitoringMetricsPublisherAssignment | Microsoft.Authorization/roleAssignments | No selected AVM exposes the required Application Insights component scope. -->
<!-- native-bicep-fallback: infra/web.bicep/environmentDiagnostics | Microsoft.Insights/diagnosticSettings | The selected managed-environment AVM is unsuitable because it requires a shared key; this diagnostic setting remains tied to the native environment fallback. -->
<!-- native-bicep-fallback: infra/web.bicep/privateEnvironmentDiagnostics | Microsoft.Insights/diagnosticSettings | The selected managed-environment AVM is unsuitable because it requires a shared key; this diagnostic setting remains tied to the native private-environment fallback. -->
<!-- native-bicep-fallback: infra/web.bicep/appDiagnostics | Microsoft.Insights/diagnosticSettings | The Container App AVM does not expose the required app diagnostic-setting configuration. -->
<!-- native-bicep-fallback: infra/web.bicep/privateAppDiagnostics | Microsoft.Insights/diagnosticSettings | The Container App AVM does not expose the required app diagnostic-setting configuration. -->
<!-- native-bicep-fallback: infra/web.bicep/registryDiagnostics | Microsoft.Insights/diagnosticSettings | The registry diagnostic setting preserves the current dedicated Log Analytics destination and category selection. -->
<!-- native-bicep-fallback: infra/web.bicep/actionGroup | Microsoft.Insights/actionGroups | No suitable selected AVM preserves the approved email-receiver and alert-action contract. -->
<!-- native-bicep-fallback: infra/web.bicep/resourceGroupBudget | Microsoft.Consumption/budgets | No maintained AVM resource module supports the required resource-group budget notification contract. -->
<!-- native-bicep-fallback: infra/web.bicep/http5xxAlert | Microsoft.Insights/scheduledQueryRules | No suitable AVM preserves this application-specific KQL alert query. -->
<!-- native-bicep-fallback: infra/web.bicep/readinessAlert | Microsoft.Insights/scheduledQueryRules | No suitable AVM preserves this application-specific KQL alert query. -->
<!-- native-bicep-fallback: infra/web.bicep/providerAlert | Microsoft.Insights/scheduledQueryRules | No suitable AVM preserves this application-specific KQL alert query. -->
<!-- native-bicep-fallback: infra/web.bicep/blobFailureAlert | Microsoft.Insights/scheduledQueryRules | No suitable AVM preserves this application-specific KQL alert query. -->
<!-- native-bicep-fallback: infra/web.bicep/replicaCeilingAlert | Microsoft.Insights/metricAlerts | No suitable AVM preserves the Container Apps replica metric and approved threshold contract. -->

## Application Deployment Orchestration

Use Azure Developer CLI (`azd`) as the primary application deployment lifecycle and orchestration path, with a root `azure.yaml` as the declarative project and service contract. The contract points `azd` to the application and the Bicep infrastructure under `infra/`; it orchestrates Bicep and does not replace it.

For an interactive shell, authenticate with `azd auth login` first. Use `az login` only when Azure CLI context is specifically required, not as an alternative imperative provisioning workflow. Configure the target environment and subscription explicitly; authentication alone does not select the deployment subscription.

Prefer `azd` lifecycle commands for application deployment. Run `azd provision --preview` before `azd provision` or `azd up`, then proceed only after reviewing the proposed changes.

## Assumptions to Validate

The initial topology assumes all of the following:

- The service is CPU orchestration: it validates requests, runs agent orchestration, calls a model through a provider-neutral port, and stores results. Microsoft Foundry is the approved agent/model platform, while final model and deployment selection remains open. The application host does not run the model or require a GPU.
- A generated image is binary object data suitable for block blobs. Request and status records are small JSON documents.
- Initial traffic is low and bursty: development is mostly idle, initial production averages fewer than 100 jobs per day, and expected concurrent model calls are no more than two until provider limits are measured.
- Typical end-to-end generation finishes within 60 seconds and the provisional application deadline is 120 seconds. Clients and every proxy in front of the service can tolerate that synchronous wait.
- The selected model endpoint supports bounded request timeouts and either idempotency keys or safe application-level deduplication. Its rate, quota, capacity, and spend limits are known before production.
- A cold start is acceptable for a development app on the Consumption workload profile. Production uses a dedicated workload profile and must fund and validate the selected profile capacity; keep at least one application replica when the latency objective requires it.
- France Central is acceptable for application and platform resources, and Sweden Central is acceptable for Microsoft Foundry, only after service/SKU availability, quota, recovery, data-residency, latency, cross-region network path, egress cost, and failure-coupling requirements are validated.
- Images are private by default. The application returns short-lived, narrowly scoped access URLs only if direct client download is required.
- The team accepts containers and a registry as deployment artifacts. If it does not, Functions Flex Consumption or App Service becomes more attractive.

Before provisioning, replace these assumptions with measured values for generation latency percentiles, payload and image sizes, arrival rate, concurrency, provider quotas, retention, availability target, and monthly budget.

## Compute Options

| Option | Why it is credible | Main constraints and costs | Fit for this service |
| --- | --- | --- | --- |
| **Azure Container Apps environment with a Dedicated workload profile** | Runs the normal Python HTTP container with HTTPS ingress, revisions, managed identity, HTTP/KEDA scaling, and compute reserved in a dedicated pool. The environment can later host a separately scaled queue-driven worker on an appropriate workload profile. | Requires building and scanning an image and normally an image registry. Dedicated profiles bill per running profile instance, so profile size and minimum/maximum instance counts require load and cost validation. Registry, logs, cross-region Foundry calls, and network egress also contribute to cost. Capacity remains subject to regional SKU availability and quota. | **Recommended production default.** It provides an explicit production capacity boundary while keeping Azure at the adapter and deployment boundary and preserving the synchronous-to-asynchronous path. |
| **Azure Container Apps, Consumption workload profile** | Uses the same container and Container Apps control plane with serverless scaling and optional scale to zero. | Scale-to-zero adds cold-start latency. Per-replica resource use, requests, registry, logs, and egress contribute to cost, and available quota bounds scaling. | Useful for development, low-cost validation, and comparison. It is not the recommended production profile for this application. |
| **Azure Functions, Flex Consumption plan** | GA serverless Functions host for Linux code deployments with event-driven scale, managed identity, VNet integration, configurable per-instance concurrency, and pay-as-you-go execution. Microsoft recommends Flex Consumption for new dynamic-scale function apps rather than the legacy Consumption plan. | Adopting HTTP and queue triggers introduces the Functions programming model and host configuration at the entry point. HTTP-triggered work still has a documented 230-second response ceiling even where function execution time can be longer. Flex instances have fixed memory choices and regional subscription quotas. Always-ready instances add cost. | Good alternative if the team wants minimal container operations and expects queue-triggered execution early. Keep triggers as thin adapters around the same core. Not the default because the current application is a general Python service, not yet an event-function workload. |
| **Azure App Service on Linux** | Mature hosting for Python web apps and custom containers, with managed identity, deployment slots on eligible tiers, health checks, VNet options, and predictable dedicated capacity. It can share an existing underused App Service plan. | An App Service plan bills for provisioned workers even while this app is idle. Scaling and worker sizing require more deliberate capacity management. Long HTTP requests remain vulnerable to client, proxy, and platform idle timeouts; a web worker timeout is not an end-to-end guarantee. | Prefer when the organization already pays for suitable spare capacity, needs App Service operational features, or requires predictable always-on compute. Otherwise it is larger than this initial workload needs. |

Do not select legacy Azure Functions Consumption for a new Python service. Microsoft documents the Consumption plan as legacy for new serverless function apps and the Linux Consumption hosting option as retiring on September 30, 2028.

Do not introduce AKS, Azure Batch, a virtual machine, Durable Functions, or Azure Container Apps Jobs for the first synchronous slice. They solve requirements not currently demonstrated. Reconsider Container Apps Jobs only if generation becomes discrete run-to-completion work rather than a continuously available queue consumer.

### Initial Container Apps Limits

Use explicit application and platform bounds instead of unconstrained autoscaling:

- Development on the Consumption workload profile: `minReplicas = 0`, `maxReplicas = 1`.
- Initial production on a dedicated workload profile: select the smallest validated general-purpose profile SKU and set explicit minimum/maximum profile instance counts from load, availability, and cost tests. Set the app to `minReplicas = 1` when required by the latency objective, and initially cap `maxReplicas = 2` until model deployment concurrency, quota, capacity, and spend controls are verified.
- Start with one in-flight generation per process. Increase only after load tests show that Python worker behavior, memory, outbound connections, Blob writes, and provider quotas remain healthy.
- Keep the HTTP scaling threshold aligned with useful per-replica concurrency. Container Apps' documented default HTTP concurrent-request threshold is 10, which is too permissive if each request can launch a costly model or agent call; configure it deliberately rather than relying on the default.
- Enforce a provider-call timeout below the request deadline, leave time to persist terminal job state, and do not retry a model charge blindly. Retry only classified transient failures with a strict attempt and elapsed-time budget.
- Treat platform maximum replica counts as service ceilings, not desired settings. Subscription quotas and downstream capacity are the real limits.

Container Apps ingress does not make a long synchronous exchange reliable by itself. Load balancers, gateways, browsers, SDKs, and the image provider can each impose a shorter timeout. Validate the full deployed path with a request lasting at least the observed p99 before accepting synchronous production behavior.

## Storage

Use a **general-purpose v2 Azure Storage account** and private blob containers:

- Store generated images as block blobs under stable job-derived names, for example `artifacts/{job_id}/result.{format}`.
- Store immutable request/result provenance beside the artifact or as a small JSON blob referenced by the job record. Avoid secrets, raw authorization headers, and unnecessary prompt or user data in blob metadata and logs.
- Use the hosting identity with **Storage Blob Data Contributor** scoped to the artifact container, not storage account keys. Give read-only consumers **Storage Blob Data Reader** at the narrowest practical scope.
- Disable anonymous blob access. Prefer application-mediated access; use a short-lived user-delegation SAS only when a client must download directly.
- Set an explicit retention period before production, then use Blob lifecycle management to cool or delete eligible block blobs. Lifecycle execution is periodic rather than immediate, so it is a retention mechanism, not synchronous deletion.
- Choose redundancy only after recovery requirements are known. LRS is the cost-minimal initial assumption; ZRS or geo-redundancy is an explicit reliability decision, not a default embellishment.

For job state, retain the provider-neutral repository port. A JSON blob per job is acceptable only for the low-volume first slice when updates are simple and guarded by ETags. It is not a general query store. Add Azure Table Storage, Cosmos DB, or a relational database only when required access patterns are known, such as listing jobs by user, multi-record transactions, high update contention, or indexed status queries.

Development should use the filesystem adapter for pure unit tests and **Azurite** for Blob/Queue integration tests. Azurite supports Blob, Queue, and Table APIs but has no production performance guarantee and has functional differences from Azure Storage; retain at least one Azure-hosted integration test before release.

## Identity and Secrets

- Assign the application a user-assigned managed identity and attach it to each Container App component that needs the same access. Its stable lifecycle keeps the principal and RBAC assignments intact across app revisions, replacement, and approved multi-component reuse. Use `DefaultAzureCredential` with the configured client ID in Azure adapters so local developer credentials and hosted managed identity follow the same code path.
- Grant data-plane roles at resource or container scope. Azure resource ownership does not itself grant Blob data access.
- Put only non-secret settings in Container Apps environment variables.
- Use Microsoft Entra authentication and Azure RBAC for Microsoft Foundry where supported. Store only model-provider credentials that cannot use federation in an Azure Key Vault Standard vault dedicated to this application and environment. Grant the application identity **Key Vault Secrets User** at vault scope. Container Apps can expose a Key Vault-backed secret reference to the container.
- Prefer direct Microsoft Entra authentication for Azure Storage, monitoring integrations, and a future Azure queue. For Application Insights ingestion with local authentication disabled, pass `ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)` to Azure Monitor OpenTelemetry and grant `Monitoring Metrics Publisher` only at the component scope. Do not store Azure Storage connection strings when managed identity is supported.
- Separate development and production identities, vaults, storage containers/accounts, Foundry projects/deployments, and telemetry resources as the eventual environment design requires. Do not let a development identity read production artifacts or invoke production model deployments.
- Use separate user-assigned identities when components need materially different permissions or isolation boundaries; stable reuse is not a reason to broaden access. Preserve least privilege and scope each role assignment as narrowly as the service supports.
- Define secret rotation and provider-key revocation tests. Key Vault storage alone does not prove that the application picks up a rotated secret safely.

If an approved non-Foundry model provider supports Microsoft Entra workload identity or another secretless federation method, prefer it after verifying the provider's documented support. An API key remains the conservative fallback interoperability assumption.

## Agentic Platform and Regions

Microsoft Foundry is validated and approved as the agent/model platform. Keep the application model and agent ports provider-neutral so model choice, deployment type, or a future provider change does not leak into domain orchestration. Evaluate Microsoft Agent Framework for the agent implementation, and require quality evaluation, tracing, safety testing, and versioned rollout before production; this design does not select a model or authorize a Foundry deployment.

Prefer Sweden Central for the Foundry project, Agent Service capabilities, and model deployments. That preference is not evidence that every required model, tool, agent feature, deployment SKU, or capacity allocation is available there. Before provisioning, verify the exact model/version and deployment type, required Agent Service tools and features, subscription quota, live capacity, networking support, and data-processing geography in current Microsoft documentation and the target subscription.

With the application in France Central and Foundry in Sweden Central, validate and explicitly accept:

- End-to-end p50/p95/p99 latency and timeout budgets across the inter-region path.
- Data residency and processing locations for prompts, outputs, agent state, traces, evaluation data, and the selected model deployment type.
- Network routing, DNS, private connectivity or public egress controls, and failure behavior when either region or the path between them is impaired.
- Inter-region data-transfer and egress charges under representative request and response sizes.
- Failure coupling, retry amplification, and whether recovery requires a second Foundry deployment, a different supported region, queue buffering, or a degraded application mode.

## Logs, Metrics, and Traces

Emit structured JSON to stdout/stderr. Connect the Container Apps environment to a Log Analytics workspace for console and system logs, and enable HTTP logs through Azure Monitor diagnostic settings if their data classification is acceptable. HTTP log fields can contain query strings and client IP addresses, so never place credentials in URLs and set a retention limit.

Instrument the cloud-neutral Python core with OpenTelemetry APIs. Use the Azure Monitor OpenTelemetry Distro or a supported exporter at the composition boundary to send traces and metrics to Application Insights. Propagate one correlation ID across the HTTP request, agent and tool calls, model invocation, job record, and Blob write.

Minimum production signals:

| Signal | Measurement or alert |
| --- | --- |
| Availability | Health endpoint failures and sustained 5xx rate |
| Latency | Request p50/p95/p99 and model-call p50/p95/p99 |
| Work outcome | Jobs started, succeeded, failed, timed out, and abandoned |
| Agent/model dependency | Foundry and model latency, tool-call outcomes, status class, throttles, retries, token or unit use, and estimated/actual cost where available |
| Capacity | Replica count, CPU, memory, concurrent generations, and rejected work |
| Storage | Blob write failures, bytes stored, transaction count, and lifecycle/retention failures |
| Cost | Azure Cost Management budget alerts plus a separate provider-spend alert; review Log Analytics ingestion and retention |

Never log full provider credentials, signed URLs, complete prompts by default, generated image bytes, or personal data. Decide prompt and artifact telemetry retention with the product and RAI owners before enabling it.

## Cost Boundaries

Pricing varies by region, agreement, date, workload shape, and telemetry volume; calculate France Central application/platform resources and Sweden Central Foundry usage, including cross-region transfer, with current pricing before provisioning. The first production deployment must define:

- A monthly Azure budget with alerts at 50%, 80%, and 100% of the approved amount.
- Independent monthly and per-minute limits for Foundry model/tool usage and any external provider, because agent/model charges can dominate CPU orchestration costs.
- Maximum replicas and maximum in-flight agent/model calls. Autoscaling must not bypass model quota, capacity, or budget controls.
- Log sampling and retention, because verbose request/dependency telemetry can exceed compute cost at low application volume.
- Artifact retention and maximum accepted/generated object sizes.
- A deployment-region check for the dedicated Container Apps workload profile SKU, Functions Flex Consumption alternatives, Key Vault, Storage redundancy, Microsoft Foundry features, the selected model deployment SKU, and required quota/capacity before final selection.

Do not claim a fixed monthly price until request rate, duration, memory, minimum replicas, image size, retention, transactions, logs, registry, and egress are entered into current calculators.

## Queue Adoption Trigger

Add a queue when **any** of these conditions is observed in a production-like test or sustained production window:

- End-to-end p95 exceeds 60 seconds or any supported client/proxy timeout leaves less than a two-times safety margin over p99.
- More than 1% of otherwise valid jobs fail because a client disconnects, the host restarts/scales in, or the provider has a transient outage or throttle.
- Arrival bursts exceed the safe provider concurrency, or maintaining synchronous headroom requires more always-on replicas than a queue-backed worker would.
- Product requirements change to accepted/pending responses, progress polling, cancellation, scheduled work, retries beyond one request, or completion webhooks.
- A job needs durable retry, poison-message isolation, independent worker deployment/scaling, or processing longer than the synchronous request budget.

Do not wait for customer-visible timeouts if load testing already crosses a trigger.

### Asynchronous Topology

Preserve the public job resource and change submission to return `202 Accepted` with a status URL:

1. The HTTP Container App validates the request, creates the durable job record, and enqueues only the job ID plus minimal routing metadata.
2. A separate Container App worker consumes the message, loads the job through the provider-neutral repository port, runs the agent/model ports, stores the Blob artifact, and updates terminal state.
3. In production, place the worker on a validated dedicated workload profile. Scale it on queue depth with an explicit small `maxReplicas` capped by model concurrency, quota, capacity, and budget; choose `minReplicas` and dedicated profile instance counts from latency and cost requirements. Scale intake independently on HTTP demand.
4. Make processing idempotent by job ID. Assume at-least-once delivery, define message visibility/lock renewal against measured processing duration, bound retries, and monitor oldest-message age and poison/dead-letter work.
5. Return status through the existing job endpoint; add events or webhooks only when polling is insufficient.

Start with **Azure Queue Storage** when the need is a single inexpensive work backlog, messages fit its 64-KB limit, and the application can implement poison-message handling and idempotency. Store payloads and sensitive data in protected storage and enqueue references, not image bytes or credentials.

Choose an **Azure Service Bus queue** instead when built-in dead-lettering, duplicate detection, sessions/ordering, scheduled delivery, transactions, topics/subscriptions, or richer broker operations are requirements. Service Bus is the safer default if reliable workflow semantics matter more than the smallest service count. Verify the selected tier's current feature, quota, and message-size limits before implementation.

## Recommended Topologies

### Development

- Run the cloud-neutral Python service locally in its normal web process.
- Use fake agent and model adapters by default; opt into a development Foundry deployment or other real provider only with developer-scoped access and a hard spend limit.
- Use filesystem artifact/job adapters for fast tests and Azurite for Blob and future Queue integration tests.
- Emit local structured logs and OpenTelemetry to a console or local collector. Do not require Azure to run unit tests.
- Optionally deploy one shared development Container App on the Consumption workload profile with scale-to-zero, one development storage account/container, a development Key Vault, a development Foundry project/deployment, and short telemetry retention for end-to-end validation.

### Initial Production

- France Central as the preferred region for application/platform resources, after service/SKU availability, quota, data-residency, latency, and recovery validation.
- One Azure Container Apps environment with a validated dedicated workload profile and one externally accessible HTTP Container App assigned to that profile.
- One general-purpose v2 Storage account with a private artifact container; use block blobs and an explicit lifecycle policy.
- One user-assigned managed identity with container-scoped Blob data access, Foundry invocation access, and Key Vault secret-read access where required. Add separate user-assigned identities for components whose permissions must be isolated.
- One Key Vault Standard vault for credentials that cannot use Microsoft Entra authentication.
- Sweden Central as the preferred region for a Microsoft Foundry project and the selected agent/model deployments, only after exact feature, model, deployment SKU, quota, capacity, networking, and data-residency validation.
- One Log Analytics workspace and workspace-based Application Insights resource, with structured logs, OpenTelemetry, actionable alerts, sampling, and retention limits.
- No queue initially, provided every assumption and synchronous acceptance test passes. Keep `maxReplicas` and provider concurrency low and explicit.

Set at least one application replica when the latency objective requires it, and include dedicated workload profile instance charges in the approved baseline cost. If production cannot tolerate synchronous or France Central-to-Sweden Central failure coupling, add the queue or an approved regional recovery/degraded-mode design before launch rather than using a longer timeout.

## Alternatives and Re-evaluation

- Choose Functions Flex Consumption if thin trigger adapters, code-only deployment, and an early queue-triggered worker are preferred over container portability.
- Use the Container Apps Consumption workload profile for development or a measured non-production comparison, not as the recommended production default.
- Choose App Service if suitable paid capacity already exists, deployment slots and mature web-app operations are decisive, or predictable always-on workers are required.
- Add Front Door or API Management only for demonstrated edge routing, WAF, global distribution, client policy, or API governance needs; each introduces another timeout, cost, and operational boundary.
- Add private endpoints, VNet integration, NAT, or firewall egress controls when threat modeling, compliance, provider IP allowlisting, or data-exfiltration controls require them. Validate Container Apps environment/networking constraints before selecting a network topology.
- Revisit storage redundancy, regional failover, multi-region compute, and Foundry recovery placement after recovery objectives, cross-region failure behavior, and data residency are approved.
- Revisit a dedicated job-state database when query and consistency requirements exceed guarded JSON blobs.

## Validation Gates Before Infrastructure Code

1. Select candidate agent/model capabilities before implementation, then measure model and tool latency, output size, failure modes, throttling, idempotency support, quality, safety, and price with representative requests. Do not finalize a model from this document alone.
2. Define synchronous client deadline, availability target, retention/deletion requirements, recovery objectives, data classification, and approved monthly budgets. Validate France Central for application/platform resources and Sweden Central for Foundry against service/SKU availability, quota, capacity, data residency, latency, network path, egress cost, and recovery requirements.
3. Load-test the selected container in a temporary Azure deployment with the intended dedicated workload profile SKU and instance bounds, CPU/memory, concurrency, min/max app replicas, full ingress path, and cross-region Foundry path.
4. Prove user-assigned managed-identity Blob and Foundry access plus Key Vault-backed secret retrieval without Azure connection strings. Verify least-privilege RBAC survives app revisions/replacement and that components with different trust boundaries use separate identities.
5. Prove correlation from request through agent/tool/model dependencies and Blob write, and test evaluations and alerts for failure, latency, throttling, quality regression, safety, and budget thresholds.
6. Exercise shutdown during a generation. Confirm terminal state is recoverable and duplicate execution does not cause an uncontrolled second charge.
7. Re-evaluate the queue trigger from measured p95/p99 and burst behavior. Record the final compute, redundancy, retention, and queue decisions before writing infrastructure as code.
8. Revalidate the exact Foundry model/version, deployment SKU/type, Agent Service features and tools, Sweden Central support, subscription quota, and live capacity immediately before provisioning; document any fallback region and its data-residency implications.

## Verified Service References

Service names and material behavior were checked against Microsoft Learn on 2026-07-22. Limits and availability can change; re-check them for the selected region and SKU during implementation.

- [Azure Container Apps overview](https://learn.microsoft.com/azure/container-apps/overview)
- [Workload profiles in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/workload-profiles-overview)
- [Scaling in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/scale-app)
- [Manage secrets in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/manage-secrets)
- [Azure Functions scale and hosting](https://learn.microsoft.com/azure/azure-functions/functions-scale)
- [Azure Functions best practices](https://learn.microsoft.com/azure/azure-functions/functions-best-practices)
- [Azure App Service overview](https://learn.microsoft.com/azure/app-service/overview)
- [Introduction to Azure Blob Storage](https://learn.microsoft.com/azure/storage/blobs/storage-blobs-introduction)
- [Assign an Azure role for Blob data access](https://learn.microsoft.com/azure/storage/blobs/assign-azure-role-data-access)
- [Azure Blob Storage lifecycle management](https://learn.microsoft.com/azure/storage/blobs/lifecycle-management-overview)
- [Azure Key Vault overview](https://learn.microsoft.com/azure/key-vault/general/overview)
- [Azure Monitor Application Insights OpenTelemetry overview](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)
- [What is Microsoft Foundry Agent Service?](https://learn.microsoft.com/azure/foundry/agents/overview)
- [Feature availability across cloud regions in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/reference/region-support)
- [Foundry Models sold by Azure](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure)
- [Introduction to Azure Queue Storage](https://learn.microsoft.com/azure/storage/queues/storage-queues-introduction)
- [Introduction to Azure Service Bus](https://learn.microsoft.com/azure/service-bus-messaging/service-bus-messaging-overview)
- [Best practices for background jobs](https://learn.microsoft.com/azure/architecture/best-practices/background-jobs)