# Retention and Deletion Policy

Effective: 2026-07-28

This policy applies to the fantasy-card image-generation service. It describes
the currently implemented system and the accepted limits on deletion. It is not
a promise of EU-only processing: the deployed `gpt-image-2` SKU uses
`GlobalStandard`, so prompts and generated responses may be processed in any
Azure geography where that model is deployed, including outside the EU. Benoit
Moussaud accepted that trade-off for development and production. Application
data at rest remains in the customer-designated Azure geography, currently
France Central.

## Retention Schedule

| Data | Current location and handling | Retention and deletion |
| --- | --- | --- |
| Prompt text and card title | The request and provider-call objects exist only in application-process memory. `GenerationJob` and the in-memory job repository retain the correlation ID, idempotency key, artifact metadata, and status; they do not contain the raw prompt or title. | Discarded when the process terminates. There is no database, queue, or application log retention for raw prompt text. An in-process restart discards all process-local job state. |
| Idempotency key | An SHA-256-derived key based on the title and prompt is held in the in-memory job repository. It is not raw prompt text. | Discarded with the process. It is not a substitute for storing or reconstructing prompts. |
| Generated image | A PNG is stored under an opaque UUID name in the private `artifacts` Blob container. Public Blob access, shared keys, and public Storage networking are disabled. | Azure Storage deletes the base blob 30 days after creation. This 30-day lifecycle is intentional and sufficient for the initial ephemeral-output product: it permits retrieval while avoiding a permanent gallery. |
| Deleted Blob recovery copies | Azure Storage soft delete is enabled for blobs and containers. | A lifecycle-deleted blob or container can remain recoverable for seven additional days before permanent deletion. The effective maximum service-side retention is therefore approximately 37 days, subject to Azure lifecycle scheduling. |
| Application telemetry and logs | Application traces record correlation IDs, outcomes, durations, dependency/error codes, and artifact byte counts. Raw titles, prompts, image bytes, endpoints, credentials, and provider details are deliberately excluded from the application telemetry contract. | The Log Analytics workspace and Application Insights component are configured for 30 days. The 30-day period is intentional: it supports operational investigation without long-lived application telemetry. |
| Microsoft Foundry inference and abuse monitoring | The model is stateless for normal inference; prompt and completion data is not stored in the model or used to train base models. Default abuse monitoring can select samples of prompts and outputs for automated review and, when flagged, human review. | Microsoft documentation describes the monitoring and storage location but does **not** state a retention duration that this product can verify. The duration is an accepted provider-controlled unknown and must not be represented as 30 days. |

## Deletion Commitments and Limits

The service does not have accounts, an artifact owner record, or a user-facing
delete operation. A request is identified by a bearer artifact URL rather than
by a durable user identity. For this first production release, a user-facing
deletion path is therefore **not required**: the private 30-day lifecycle rule
is the deletion mechanism, and the seven-day soft-delete window is part of the
effective Azure retention behavior.

This is an explicit scope decision, not a claim that immediate user deletion is
available. Product must add authenticated ownership and an immediate deletion
path before introducing user accounts, saved galleries, uploads, or any
requirement to delete a specific user's artifact before the lifecycle window
ends.

The 30-day artifact policy does not delete data held by Microsoft under default
abuse monitoring. The service currently uses default monitoring; it does not
have approval for modified abuse monitoring. Microsoft documents that
automated review does not store prompts or completions, while potentially
abusive samples may be stored in a logically separated abuse-monitoring store
in the customer-designated geography for human review. The product has not
independently verified Microsoft's retention duration for that store and
accepts that unknown as a provider-control limitation.

## Operational Controls

- Do not add raw prompt text, titles, image bytes, Foundry responses, endpoint
  URLs, or credentials to application logs, traces, or error reports.
- Before production deployment, validate the actual Azure diagnostic categories
  and workspace tables. The Bicep template sends Foundry diagnostic categories
  to the workspace, but this repository does not prove that every service-side
  diagnostic record excludes prompt or generated-content fields. Do not enable
  a category shown to contain them without a reviewed retention and access
  decision.
- Reassess this policy if the deployment type, model, stateful Foundry feature,
  telemetry configuration, artifact store, retention rule, or abuse-monitoring
  terms change.

## Sources and Evidence

- `src/fantasy_cards/domain.py`, `application.py`, and `adapters.py` show that
  job state has no raw-prompt field and is process-local.
- `src/fantasy_cards/telemetry.py` and the telemetry decision record define the
  application telemetry allowlist.
- `infra/foundry.bicep` configures 30-day Log Analytics and Application
  Insights retention; `infra/web.bicep` configures the private Blob container,
  30-day lifecycle deletion, and seven-day soft delete.
- [Microsoft Foundry data, privacy, and security](https://learn.microsoft.com/azure/foundry/responsible-ai/openai/data-privacy)
  describes Global processing, stateless inference, and default abuse
  monitoring. Microsoft does not publish a retention duration there for the
  abuse-monitoring store.
