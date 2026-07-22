# Azure Deployment Design

Status: proposed for validation; no infrastructure implementation is authorized by this document.

## Decision Summary

Use a single **Azure Container Apps** HTTP application as the initial production host, backed by **Azure Blob Storage** for generated images and artifact metadata. Give the app a system-assigned managed identity for Azure access, keep the external image-model credential in **Azure Key Vault**, and send platform logs to an **Azure Monitor Log Analytics workspace**. Instrument application traces and metrics with OpenTelemetry and export them to **Azure Monitor Application Insights**.

Start with synchronous orchestration only while measurements support it. Keep the existing job-shaped application contract and cloud-neutral ports for model invocation, artifact storage, and job state. If the queue trigger below is reached, split request intake from generation by adding a queue and a separately scaled worker; do not move orchestration logic into Azure SDK bindings or hosting-framework callbacks.

This recommendation is conditional on the assumptions below. It is not a claim that Container Apps is always cheaper or faster than the alternatives.

## Assumptions to Validate

The initial topology assumes all of the following:

- The service is CPU orchestration: it validates requests, calls an external image model over HTTPS, and stores results. It does not run the image model or require a GPU in Azure.
- A generated image is binary object data suitable for block blobs. Request and status records are small JSON documents.
- Initial traffic is low and bursty: development is mostly idle, initial production averages fewer than 100 jobs per day, and expected concurrent model calls are no more than two until provider limits are measured.
- Typical end-to-end generation finishes within 60 seconds and the provisional application deadline is 120 seconds. Clients and every proxy in front of the service can tolerate that synchronous wait.
- The external provider supports bounded request timeouts and either idempotency keys or safe application-level deduplication. Its rate and spend limits are known before production.
- A cold start is acceptable in development. Initial production can either tolerate cold starts or fund one minimum replica.
- A single Azure region and locally redundant storage are acceptable initially. Recovery point, recovery time, residency, and zone requirements remain open.
- Images are private by default. The application returns short-lived, narrowly scoped access URLs only if direct client download is required.
- The team accepts containers and a registry as deployment artifacts. If it does not, Functions Flex Consumption or App Service becomes more attractive.

Before provisioning, replace these assumptions with measured values for generation latency percentiles, payload and image sizes, arrival rate, concurrency, provider quotas, retention, availability target, and monthly budget.

## Compute Options

| Option | Why it is credible | Main constraints and costs | Fit for this service |
| --- | --- | --- | --- |
| **Azure Container Apps, Consumption plan** | Runs the normal Python HTTP container, supports HTTPS ingress, revisions, managed identity, HTTP/KEDA scaling, and scale to zero. The same environment can later host a queue-driven worker or Container Apps job. | Requires building and scanning an image and normally an image registry. Scale-to-zero adds cold-start latency. Active and idle resource usage, requests, registry, logs, and network egress can all contribute to cost. Replica targets are bounded by configured minimum/maximum values and available quota, not guaranteed capacity. | **Recommended default.** It keeps Azure at the adapter and deployment boundary and offers the least disruptive synchronous-to-asynchronous path. |
| **Azure Functions, Flex Consumption plan** | GA serverless Functions host for Linux code deployments with event-driven scale, managed identity, VNet integration, configurable per-instance concurrency, and pay-as-you-go execution. Microsoft recommends Flex Consumption for new dynamic-scale function apps rather than the legacy Consumption plan. | Adopting HTTP and queue triggers introduces the Functions programming model and host configuration at the entry point. HTTP-triggered work still has a documented 230-second response ceiling even where function execution time can be longer. Flex instances have fixed memory choices and regional subscription quotas. Always-ready instances add cost. | Good alternative if the team wants minimal container operations and expects queue-triggered execution early. Keep triggers as thin adapters around the same core. Not the default because the current application is a general Python service, not yet an event-function workload. |
| **Azure App Service on Linux** | Mature hosting for Python web apps and custom containers, with managed identity, deployment slots on eligible tiers, health checks, VNet options, and predictable dedicated capacity. It can share an existing underused App Service plan. | An App Service plan bills for provisioned workers even while this app is idle. Scaling and worker sizing require more deliberate capacity management. Long HTTP requests remain vulnerable to client, proxy, and platform idle timeouts; a web worker timeout is not an end-to-end guarantee. | Prefer when the organization already pays for suitable spare capacity, needs App Service operational features, or requires predictable always-on compute. Otherwise it is larger than this initial workload needs. |

Do not select legacy Azure Functions Consumption for a new Python service. Microsoft documents the Consumption plan as legacy for new serverless function apps and the Linux Consumption hosting option as retiring on September 30, 2028.

Do not introduce AKS, Azure Batch, a virtual machine, Durable Functions, or Azure Container Apps Jobs for the first synchronous slice. They solve requirements not currently demonstrated. Reconsider Container Apps Jobs only if generation becomes discrete run-to-completion work rather than a continuously available queue consumer.

### Initial Container Apps Limits

Use explicit application and platform bounds instead of unconstrained autoscaling:

- Development: `minReplicas = 0`, `maxReplicas = 1`.
- Initial production: `minReplicas = 1` only if the latency objective cannot tolerate cold starts; otherwise start at `0`. Set `maxReplicas = 2` until the external provider's concurrency and spend controls are verified.
- Start with one in-flight generation per process. Increase only after load tests show that Python worker behavior, memory, outbound connections, Blob writes, and provider quotas remain healthy.
- Keep the HTTP scaling threshold aligned with useful per-replica concurrency. Container Apps' documented default HTTP concurrent-request threshold is 10, which is too permissive if each request can launch a costly model call; configure it deliberately rather than relying on the default.
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

- Assign the compute host a system-assigned managed identity. Use `DefaultAzureCredential` in Azure adapters so local developer credentials and hosted managed identity use the same code path.
- Grant data-plane roles at resource or container scope. Azure resource ownership does not itself grant Blob data access.
- Put only non-secret settings in Container Apps environment variables.
- Store the external model API key in an Azure Key Vault Standard vault dedicated to this application and environment. Grant the host identity **Key Vault Secrets User** at vault scope. Container Apps can expose a Key Vault-backed secret reference to the container.
- Prefer direct Microsoft Entra authentication for Azure Storage, monitoring integrations, and a future Azure queue. Do not store Azure Storage connection strings when managed identity is supported.
- Separate development and production identities, vaults, storage containers/accounts, and telemetry resources as the eventual environment design requires. Do not let a development identity read production artifacts.
- Define secret rotation and provider-key revocation tests. Key Vault storage alone does not prove that the application picks up a rotated secret safely.

If the external image provider supports Microsoft Entra workload identity or another secretless federation method, prefer it after verifying the provider's documented support. An API key remains the conservative interoperability assumption.

## Logs, Metrics, and Traces

Emit structured JSON to stdout/stderr. Connect the Container Apps environment to a Log Analytics workspace for console and system logs, and enable HTTP logs through Azure Monitor diagnostic settings if their data classification is acceptable. HTTP log fields can contain query strings and client IP addresses, so never place credentials in URLs and set a retention limit.

Instrument the cloud-neutral Python core with OpenTelemetry APIs. Use the Azure Monitor OpenTelemetry Distro or a supported exporter at the composition boundary to send traces and metrics to Application Insights. Propagate one correlation ID across the HTTP request, job record, provider call, and Blob write.

Minimum production signals:

| Signal | Measurement or alert |
| --- | --- |
| Availability | Health endpoint failures and sustained 5xx rate |
| Latency | Request p50/p95/p99 and model-call p50/p95/p99 |
| Work outcome | Jobs started, succeeded, failed, timed out, and abandoned |
| External dependency | Provider latency, status class, throttles, retries, and estimated/actual cost where available |
| Capacity | Replica count, CPU, memory, concurrent generations, and rejected work |
| Storage | Blob write failures, bytes stored, transaction count, and lifecycle/retention failures |
| Cost | Azure Cost Management budget alerts plus a separate provider-spend alert; review Log Analytics ingestion and retention |

Never log full provider credentials, signed URLs, complete prompts by default, generated image bytes, or personal data. Decide prompt and artifact telemetry retention with the product and RAI owners before enabling it.

## Cost Boundaries

Pricing varies by region, agreement, date, workload shape, and telemetry volume; calculate the chosen region in the Azure pricing calculator before provisioning. The first production deployment must define:

- A monthly Azure budget with alerts at 50%, 80%, and 100% of the approved amount.
- An independent monthly and per-minute limit at the external image provider, because provider charges are likely to dominate CPU orchestration costs.
- Maximum replicas and maximum in-flight provider calls. Autoscaling must not bypass the provider budget.
- Log sampling and retention, because verbose request/dependency telemetry can exceed compute cost at low application volume.
- Artifact retention and maximum accepted/generated object sizes.
- A deployment-region check for Container Apps, Functions Flex Consumption, Key Vault, Storage redundancy, and required quotas before final selection.

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
2. A separate Container App worker consumes the message, loads the job through the provider-neutral repository port, calls the model port, stores the Blob artifact, and updates terminal state.
3. Scale the worker on queue depth with `minReplicas = 0` and a small `maxReplicas` capped by provider concurrency and budget. Scale intake independently on HTTP demand.
4. Make processing idempotent by job ID. Assume at-least-once delivery, define message visibility/lock renewal against measured processing duration, bound retries, and monitor oldest-message age and poison/dead-letter work.
5. Return status through the existing job endpoint; add events or webhooks only when polling is insufficient.

Start with **Azure Queue Storage** when the need is a single inexpensive work backlog, messages fit its 64-KB limit, and the application can implement poison-message handling and idempotency. Store payloads and sensitive data in protected storage and enqueue references, not image bytes or credentials.

Choose an **Azure Service Bus queue** instead when built-in dead-lettering, duplicate detection, sessions/ordering, scheduled delivery, transactions, topics/subscriptions, or richer broker operations are requirements. Service Bus is the safer default if reliable workflow semantics matter more than the smallest service count. Verify the selected tier's current feature, quota, and message-size limits before implementation.

## Recommended Topologies

### Development

- Run the cloud-neutral Python service locally in its normal web process.
- Use a fake model adapter by default; opt into the real provider only with a developer-scoped key and hard spend limit.
- Use filesystem artifact/job adapters for fast tests and Azurite for Blob and future Queue integration tests.
- Emit local structured logs and OpenTelemetry to a console or local collector. Do not require Azure to run unit tests.
- Optionally deploy one shared development Container App with scale-to-zero, one development storage account/container, a development Key Vault, and short telemetry retention for end-to-end validation.

### Initial Production

- One Azure Container Apps environment and one externally accessible HTTP Container App on the Consumption plan.
- One general-purpose v2 Storage account with a private artifact container; use block blobs and an explicit lifecycle policy.
- One system-assigned managed identity with container-scoped Blob data access and Key Vault secret-read access.
- One Key Vault Standard vault for the external provider credential.
- One Log Analytics workspace and workspace-based Application Insights resource, with structured logs, OpenTelemetry, actionable alerts, sampling, and retention limits.
- No queue initially, provided every assumption and synchronous acceptance test passes. Keep `maxReplicas` and provider concurrency low and explicit.

If production cannot tolerate cold starts, set one minimum replica and accept the idle cost. If it cannot tolerate synchronous failure coupling, add the queue before launch rather than using a longer timeout.

## Alternatives and Re-evaluation

- Choose Functions Flex Consumption if thin trigger adapters, code-only deployment, and an early queue-triggered worker are preferred over container portability.
- Choose App Service if suitable paid capacity already exists, deployment slots and mature web-app operations are decisive, or predictable always-on workers are required.
- Add Front Door or API Management only for demonstrated edge routing, WAF, global distribution, client policy, or API governance needs; each introduces another timeout, cost, and operational boundary.
- Add private endpoints, VNet integration, NAT, or firewall egress controls when threat modeling, compliance, provider IP allowlisting, or data-exfiltration controls require them. Validate Container Apps environment/networking constraints before selecting a network topology.
- Revisit storage redundancy, regional failover, and multi-region compute after recovery objectives and data residency are approved.
- Revisit a dedicated job-state database when query and consistency requirements exceed guarded JSON blobs.

## Validation Gates Before Infrastructure Code

1. Measure model latency, output size, failure modes, throttling, idempotency support, and price with representative requests.
2. Define synchronous client deadline, availability target, retention/deletion requirements, recovery objectives, region, data classification, and approved monthly budgets.
3. Load-test the selected container locally and in a temporary Azure deployment with the intended CPU/memory, concurrency, min/max replicas, and full ingress path.
4. Prove managed-identity Blob access and Key Vault-backed secret retrieval without Azure connection strings.
5. Prove correlation from request through provider dependency and Blob write, and test alerts for failure, latency, throttling, and budget thresholds.
6. Exercise shutdown during a generation. Confirm terminal state is recoverable and duplicate execution does not cause an uncontrolled second charge.
7. Re-evaluate the queue trigger from measured p95/p99 and burst behavior. Record the final compute, redundancy, retention, and queue decisions before writing infrastructure as code.

## Verified Service References

Service names and material behavior were checked against Microsoft Learn on 2026-07-22. Limits and availability can change; re-check them for the selected region and SKU during implementation.

- [Azure Container Apps overview](https://learn.microsoft.com/azure/container-apps/overview)
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
- [Introduction to Azure Queue Storage](https://learn.microsoft.com/azure/storage/queues/storage-queues-introduction)
- [Introduction to Azure Service Bus](https://learn.microsoft.com/azure/service-bus-messaging/service-bus-messaging-overview)
- [Best practices for background jobs](https://learn.microsoft.com/azure/architecture/best-practices/background-jobs)