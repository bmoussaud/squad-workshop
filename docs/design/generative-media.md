# Generative Media Design

## Scope

The first vertical slice generates original **fantasy trading-card-style** imagery through a provider-neutral port. It does not promise imitation of any named game, franchise, studio, or artist. Provider and model selection remain evidence-based deployment decisions.

## Normalized Input

`GenerationInput` contains:

- `request_id`: caller-assigned stable identifier.
- `prompt`: structured prompt with `subject`, `action`, `setting`, `composition`, `lighting`, `palette`, and optional `text_exclusions`. Prompt construction should describe visual properties, not named artists or copyrighted franchises.
- `negative_constraints`: normalized concepts to avoid, including unwanted objects, malformed anatomy, duplicate subjects, logos, signatures, watermarks, borders, and legible text. Adapters may translate these constraints to provider-specific syntax but must preserve the normalized list in metadata.
- `width` and `height`: positive pixel dimensions. Validation applies product limits and adapter capability checks before generation; adapters must not silently resize.
- `output_format`: one of `png`, `jpeg`, or `webp`. Alpha is valid only where the selected format and adapter support it.
- `seed`: optional unsigned integer. Omission means the adapter chooses a seed when supported. The effective seed is returned when disclosed by the provider.
- `sample_count`: requested number of candidates within product limits.
- `safety_context`: product-level content classification and audience setting, without provider-specific policy labels.

Unknown fields are rejected at the application boundary. Provider-specific options are not accepted in the domain contract; controlled experiments may carry them in adapter-owned configuration.

## Result Contract

`GenerationOutput` is the normalized return from the generation port:

- `request_id` and `outcome`: stable correlation and `succeeded`, `partially_succeeded`, `rejected`, or `failed`.
- `artifacts`: zero or more records containing `artifact_id`, storage-neutral `uri`, `media_type`, byte size, pixel dimensions, checksum, and optional width/height-independent provider content identifier.
- `effective_input`: the normalized input after explicit validation or documented adapter translation, including the effective seed when known.
- `provider_record`: opaque adapter metadata containing provider, model, and model-version identifiers plus provider request identifier. Consumers must not branch on this object.
- `timing`: submission and completion timestamps and measured latency.
- `moderation`: pre-generation and post-generation outcomes, policy version, reason codes safe to expose, and whether human review is required.
- `provenance`: application version, adapter version, prompt-template version, generation timestamp, source-asset references and rights declarations, content-credential or watermark state, and transformation history.
- `license`: provider terms/version evaluated, permitted product use, attribution obligations, retention restrictions, and review timestamp. This records the applicable assessment; it is not legal advice.
- `error`: normalized code, retryability, and safe message when no artifact is produced.

The application wraps that output in `GenerationJob`, which owns `job_id`, `request_id`, timestamps, and `status`: `accepted`, `running`, `succeeded`, `partially_succeeded`, `rejected`, or `failed`. Synchronous orchestration normally returns a terminal state; retaining nonterminal states preserves the same application contract if execution later moves to a queue.

Artifact bytes remain behind the artifact-storage port. Logs and client responses must not expose provider credentials, private moderation details, or source assets beyond authorized references.

## Moderation And Rights Boundary

The application owns prompt validation, disallowed imitation requests, source-asset consent and rights declarations, age/audience rules, and the final decision to store or publish an artifact. The generation adapter owns faithful translation to provider controls and returns provider moderation signals without weakening them.

Moderation occurs before generation on normalized text and source assets, then after generation before durable publication. A provider acceptance is necessary but not sufficient: the application can reject an output for logos, signatures, watermark-like marks, unsafe content, or unresolved rights. Rejected bytes use restricted temporary handling and are deleted according to the eventual retention policy. Appeals and human review are application concerns, not adapter behavior.

Every provider candidate requires documented output-use terms, training/input retention behavior, deletion support, region handling, and provenance capabilities. Inputs lacking a rights declaration are rejected when they include source media.

## Reproducibility

Seed, effective prompt, dimensions, format, adapter version, model identifier/version, and generation parameters are captured for diagnosis and comparison. A seed does not guarantee pixel-identical replay: providers may change model weights, schedulers, infrastructure, safety filters, or nondeterministic execution. The product promises traceability, not exact regeneration. Checksums identify returned artifacts; evaluation stores representative outputs and metadata when licensing permits.

## Evaluation Set

Run each candidate model with the same normalized cases, allowed dimensions, and repeated seeds where supported:

| Case | Prompt intent | Primary checks |
| --- | --- | --- |
| Single hero | Armored moonlit ranger, centered portrait composition | Subject fidelity, anatomy, face/hands, usable negative space |
| Creature action | Original crystal-winged drake crossing a storm | Motion coherence, wing count, silhouette, detail |
| Environment | Ancient floating library above a green valley | Perspective, structural coherence, depth, palette |
| Multi-subject | Three distinct adventurers around a glowing map | Subject count, identity separation, occlusion, hands |
| Constraint stress | Crowned knight with no text, logos, border, signature, or watermark | Negative-constraint compliance, artifact detection |
| Safety boundary | Ambiguous conflict scene phrased for a teen audience | Policy consistency, useful rejection codes, safe fallback |

For each case, generate at least three candidates across two runs. Record blind human ratings for prompt adherence, composition, coherence, defects, and suitability for a fantasy trading-card-style crop; automated checks cover dimensions, format, corruption, latency, and moderation outcomes. Keep aesthetic ratings separate from measurable defects. The set must include both accepted and intentionally rejected requests.

## Provider Selection

Select only after a documented comparison weighted for product needs:

- visual quality and normalized-constraint adherence on the evaluation set;
- moderation coverage, consistency, explainability, and application override support;
- output licensing, source-input terms, retention/deletion controls, and commercial-use fit;
- provenance support, stable model/version reporting, and content credentials;
- supported dimensions/formats, seed behavior, availability, latency, failure rate, and retry semantics;
- cost per accepted artifact, regional availability, privacy posture, operational support, and exit portability.

Quality alone cannot override an unacceptable licensing, privacy, provenance, or moderation result. Preserve raw scores, sample metadata, evaluator notes, terms versions, and the selection rationale.

## Contract For Trinity

Trinity can implement a `GenerationPort.generate(input: GenerationInput) -> GenerationOutput` boundary plus an artifact-storage port. Validation must reject unknown/provider-specific fields, unsupported dimensions or format combinations, unsafe prompts, named-artist or franchise-imitation requests, and source media without rights declarations. The application service creates stable `request_id`/`job_id` values, calls exactly one configured adapter, wraps its output in `GenerationJob`, normalizes errors and moderation outcomes, stores only publishable artifacts, and returns the metadata above.

Adapters may translate prompts and constraints but must report `effective_input`; they may not silently resize, change format, discard moderation signals, or claim deterministic replay. No consumer outside the adapter depends on provider SDK types, status names, URLs, or policy labels. This matches the pending modular-monolith decision and preserves a future synchronous-to-queued transition without changing the domain interface.