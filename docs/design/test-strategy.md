# Initial Test Strategy

## Purpose

This strategy is the executable quality contract for the first vertical slice. The
implementation must remain an importable Python package with domain, application,
port, and adapter boundaries. Its default test path must run with in-memory adapters,
without network access, Azure credentials, or an image-provider SDK.

Test names below are stable acceptance IDs. Trinity may map package imports to the
scaffold's final package name, but should preserve the behavior and test IDs.

## Test Harness

Use `pytest` and keep tests under these layers:

```text
tests/
  unit/                 # Pure domain and application behavior
  contract/             # Every adapter checked against its port contract
  smoke/                # In-memory vertical slice
  evaluation/           # Bounded nondeterministic image checks
```

The default command must be deterministic and offline:

```bash
python -m pytest -m "not live and not image_eval"
```

The curated image evaluation command is explicit and opt-in:

```bash
python -m pytest -m image_eval --image-eval-manifest tests/evaluation/fixtures/manifest.json
```

Tests marked `live` are never part of the initial acceptance gate. Unit, contract,
and smoke tests must fail if they attempt DNS, sockets, subprocesses, or cloud
credential discovery. Freeze time and inject deterministic ID generators where IDs
or timestamps are asserted.

Shared fixtures should expose only provider-neutral ports:

- `generator`: records a normalized generation request and returns deterministic
  image bytes plus provider-neutral provenance.
- `artifact_store`: stores bytes in memory and returns an opaque artifact reference.
- `job_store`: records state transitions and supports lookup by job and idempotency
  key.
- `id_source`, `clock`, and `correlation_id`: deterministic injected values.
- `valid_request`: the smallest valid fantasy-card image request, using fictional
  names and no sensitive data.

## Executable Matrix

| Layer | Test ID | Setup and action | Acceptance signal |
|---|---|---|---|
| Unit | `test_valid_request_normalizes_domain_values` | Build a request with surrounding whitespace and supported optional values. | A validated immutable request contains canonical values; no provider-specific fields or imports are present. |
| Unit | `test_invalid_request_reports_all_actionable_field_errors` | Submit missing title, empty prompt, and out-of-range dimensions in one request. | Validation fails before any port call and reports stable field paths with human-readable reasons; raw payload values are not echoed. |
| Unit | `test_generate_card_records_ordered_job_transitions` | Run the use case with deterministic in-memory ports. | Exactly `pending -> generating -> storing -> completed` is persisted, with one stable job ID and correlation ID across all states. |
| Unit | `test_completed_job_exposes_provider_neutral_result` | Complete generation with fake provenance. | Result contains job status, opaque artifact metadata, and approved provenance fields; provider SDK objects, deployment URLs, credentials, and vendor exceptions are absent. |
| Unit | `test_application_depends_on_ports_not_concrete_adapters` | Import the application use case while blocking imports from provider and Azure adapter namespaces. | Import and construction succeed using fakes; no credentials or network access are attempted. |
| Contract | `test_generator_adapter_contract` | Run the shared generator contract against the deterministic in-memory generator. | One normalized request produces non-empty image bytes and provider-neutral provenance; malformed requests raise the declared port error. |
| Contract | `test_artifact_store_adapter_contract` | Store known bytes twice under distinct job IDs and retrieve metadata. | Returned references are opaque and stable, metadata has content type and byte length, and no filesystem/Azure implementation detail leaks. |
| Contract | `test_job_store_adapter_contract` | Create, transition, and reload a job. | Legal transitions round-trip without loss; illegal transitions fail atomically; lookup of an unknown ID returns the declared not-found result. |
| Contract | `test_all_adapter_errors_translate_to_port_errors` | Parameterize generator, artifact, and job adapters with implementation-level failures. | Callers receive only documented port/application errors; vendor exception types, response bodies, hosts, and account names do not escape. |
| Smoke | `test_in_memory_generation_completes_without_cloud_credentials` | Clear Azure/provider environment variables, disable network access, compose all in-memory adapters, and submit `valid_request`. | The call returns `completed`; one artifact exists with non-empty bytes; one job has the full ordered transition history; process exit is zero. |
| Smoke | `test_smoke_flow_covers_validation_generation_storage_and_completion` | Spy on the validator and each port during the in-memory flow. | Calls occur once in the order validate, create job, generate, store, complete; returned job ID, stored owner ID, and correlation ID agree. |
| Idempotency | `test_same_idempotency_key_returns_original_completed_job` | Submit the same normalized request twice with one idempotency key. | Both responses have the same job and artifact references; generator and artifact store are each called exactly once. |
| Idempotency | `test_idempotency_key_with_different_payload_is_rejected` | Reuse a key with a materially different prompt or dimensions. | A stable conflict error is returned; the original job and artifact remain unchanged; no generation occurs for the second request. |
| Idempotency | `test_retry_after_transient_failure_resumes_without_duplicate_artifact` | Fail storage once after successful generation, then retry with the same key. | The job reaches `completed`; at most one committed artifact exists; transition history records the failure/retry without creating a second job. |
| Failure | `test_validation_failure_has_no_side_effects` | Submit an invalid request with recording fakes. | No job, generator, or artifact-store call occurs; error identifies invalid fields without including the complete input payload. |
| Failure | `test_generation_failure_marks_job_failed_and_skips_storage` | Generator raises the declared transient port error. | Job ends `failed` with a stable safe error code and correlation ID; artifact store is not called; original exception text is not returned. |
| Failure | `test_storage_failure_marks_job_failed_without_false_completion` | Generator succeeds and artifact storage raises its declared error. | Job ends `failed`, never `completed`; response has no artifact reference; generated bytes do not appear in the error or logs. |
| Failure | `test_job_state_write_failure_does_not_report_success` | Make the final job-state persistence fail. | Use case returns a persistence failure rather than a completed response; logs identify the job and correlation ID for reconciliation. |
| Configuration | `test_in_memory_configuration_requires_no_external_secrets` | Load explicit in-memory mode with all cloud/provider variables removed. | Composition succeeds and selects only in-memory adapters; no `DefaultAzureCredential` or provider client is constructed. |
| Configuration | `test_missing_required_configuration_lists_safe_variable_names` | Load an external-adapter mode without required settings. | Startup fails before serving work; one configuration exception lists missing variable names and remediation, but never values. |
| Configuration | `test_invalid_configuration_rejects_unknown_mode_and_bad_numbers` | Parameterize unknown adapter names and malformed timeout/size values. | Each case fails at startup with a stable field-specific message; no silent default or network call occurs. |
| Configuration | `test_secret_values_are_redacted_from_configuration_errors` | Set sentinel secrets and trigger a related configuration error. | Exception text, captured stdout/stderr, and logs contain none of the sentinel values. |
| Logging privacy | `test_success_logs_include_job_and_correlation_ids` | Capture structured logs for a completed smoke flow. | Every lifecycle event contains `job_id` and `correlation_id`; event names and final status are queryable; no full prompt or image bytes are logged. |
| Logging privacy | `test_failure_logs_are_correlatable_and_payload_safe` | Trigger validation, generation, and storage failures with sentinel prompt, secret, and byte content. | Logs include safe error code, job ID when allocated, and correlation ID; sentinels, authorization headers, provider response bodies, and image data are absent. |
| Logging privacy | `test_log_schema_does_not_expose_provider_details` | Capture all records from in-memory and fake external adapters. | Public log fields contain no provider class, SDK exception, endpoint, deployment, account, bucket/container, or credential-chain detail. |
| Boundary | `test_package_import_has_no_environment_or_network_side_effects` | Import every public package module in a clean subprocess with network blocked and environment empty. | Imports exit zero, emit no logs, create no files/clients, and do not read cloud credentials. |
| Boundary | `test_domain_and_application_import_graph_respects_boundaries` | Inspect imports with an AST-based rule. | Domain imports only standard library/domain modules; application may import domain and ports; ports do not import adapters; adapters may depend inward. |

## Port Contract Shape

Each port contract should be a reusable pytest suite or parameterized test function.
An adapter is accepted only by supplying an adapter factory to the same contract; do
not duplicate assertions for in-memory and future cloud/provider adapters. Contract
tests must verify successful behavior, declared errors, input immutability, and the
absence of implementation-specific return values.

Future Azure and image-provider adapters must pass the offline contract with mocked
SDK boundaries before any optional `live` tests are introduced. A live test cannot
replace a contract test.

## Bounded Nondeterministic Image Evaluation

Image quality is an explicit release signal, not a pixel snapshot. Keep the initial
evaluation set small, versioned, and provider-neutral:

1. Store 8-12 fictional prompt cases in `manifest.json`, balanced across portrait,
   creature, landscape, dark/light palette, fine detail, and requested aspect ratio.
2. For each case record a stable case ID, request fields, expected dimensions/aspect
   ratio, prohibited tokens/concepts, and applicable semantic rubric items. Do not
   require a fixed provider, seed, or model version in the application contract.
3. Generate at most three samples per case. Preserve only artifact hashes, sanitized
   provenance, evaluator version, numeric results, and reviewer disposition in the
   report; never write credentials or raw provider responses.
4. Run deterministic checks on every sample and bounded semantic checks on the set.

Concrete evaluation tests and gates:

| Test ID | Evaluation | Acceptance signal |
|---|---|---|
| `test_eval_outputs_are_decodable_and_match_requested_geometry` | Decode every output and inspect media type, width, height, and aspect ratio. | 100% decode successfully; media type is allowed; dimensions match exactly or satisfy the manifest tolerance of at most 1%. |
| `test_eval_outputs_are_not_blank_or_corrupt` | Measure luminance variance, alpha coverage, and perceptual hashes. | 100% exceed versioned blank-image thresholds; no sample is a byte/perceptual duplicate of another prompt case. |
| `test_eval_prohibited_content_gate` | Apply the approved safety evaluator to each output and its sanitized prompt. | Zero high-severity prohibited-content findings; any evaluator error is `inconclusive`, never a pass. |
| `test_eval_semantic_rubric_meets_bounded_threshold` | Score subject presence, requested composition, and obvious text/artifact defects with a pinned evaluator/rubric version. | Every case has at least 2 of 3 samples passing all critical rubric items; aggregate pass rate is at least 90%; no critical item may be averaged away. |
| `test_eval_report_is_reproducible_and_provider_neutral` | Re-read the generated JSON report without provider SDKs installed. | Schema validation passes and includes case/evaluator versions, hashes, sanitized provenance, scores, and dispositions; it contains no endpoints, credentials, provider response bodies, or SDK types. |

Nondeterministic evaluation gets one controlled rerun only when infrastructure or the
evaluator returns `inconclusive`. A quality failure is not rerun until it passes.
Threshold or rubric changes require a reviewed manifest/version change and a written
rationale; they must not be adjusted inside a failing CI run.

## Initial Quality Gates

The first vertical slice is accepted when:

- `python -m pytest -m "not live and not image_eval"` passes twice from a clean
  environment with network disabled and all Azure/provider credentials absent.
- Coverage includes every domain transition and every declared application/port
  error branch. Line coverage is reported but is not a substitute for those cases.
- The smoke flow proves validation through generation, storage, and a completed job
  using only in-memory adapters.
- Import-boundary, configuration, idempotency, failure, and logging-privacy tests pass.
- The versioned image-evaluation set meets all deterministic gates and the bounded
  semantic threshold, or is explicitly recorded as not yet run because no real image
  adapter is part of the slice. It must never be reported as passing when skipped.

Any flaky deterministic test blocks acceptance. Any nondeterministic result outside
the stated rerun rule is a failed or inconclusive evaluation, not a waived signal.