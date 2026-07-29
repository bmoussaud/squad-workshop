# Content Policy for Generated Imagery

Effective: 2026-07-28

This product generates original fantasy trading-card-style imagery. It does not
offer imitation of real people, artists, games, franchises, brands, or other
protected properties. This policy governs every text prompt, title, and
generation request.

## Prohibited Requests

The service must reject requests that include any of the following:

| Category | Policy |
| --- | --- |
| Real-person likeness | Do not request a recognizable real person, living or deceased, by name or identifying description. This includes public figures, private individuals, impersonation, and lookalike requests. |
| Copyrighted characters and protected properties | Do not request a named fictional character, franchise, game, film, book, studio, logo, uniform, or other protected property. Users must describe an original character, setting, and visual elements instead. |
| Trademarks and brands | Do not request brand names, logos, trade dress, product packaging, or other marks. The product does not generate commercial endorsement, affiliation, or counterfeit-style imagery. |
| Named-artist style imitation | Do not request work "in the style of" a named living or deceased artist, studio, or illustrator. Users may request general visual characteristics such as painterly lighting, inked line art, or a high-fantasy palette. |
| Minors | Do not request any depiction of a minor, including child, teen, age-regressed, school-age, or ambiguous youthful persons. Sexualized, exploitative, or nude depictions of minors are categorically prohibited. This product takes the simpler and safer production boundary of prohibiting all minor depictions. |
| Harmful or evasive content | Do not request hateful, sexual, violent, self-harm, exploitative, illegal, or deceptive imagery; do not attempt to bypass safety controls or transform a prohibited request into an allowed one. |

## Required Enforcement

Provider filtering alone is not sufficient for this policy. `Microsoft.DefaultV2`
provides baseline harmful-content, jailbreak, and protected-material controls,
but it does not establish this product's rules for real-person likeness,
copyrighted properties, named-artist imitation, or all minor depictions.

Production enforcement is a required combination:

1. **Application-level pre-generation validation** rejects the product-specific
   classes above before the request reaches Microsoft Foundry.
2. **A custom Microsoft Foundry RAI policy** preserves or strengthens the
   baseline provider controls and is deployed, versioned, and verified for the
   production resource.
3. **Provider safety filtering** remains enabled as defense in depth. A provider
   acceptance never overrides an application-policy rejection.

The application enforces this policy in `GenerationService` before idempotency
lookup, artifact writes, or any image-generator/provider call. The validator
normalizes Unicode, strips zero-width formatting characters, and compares both
normalized and compacted forms to resist simple spacing, confusable-character,
and leetspeak evasion. Recognized protected-name collisions are denied before
any generic-word interpretation; no title or phrase allowlist can override a
deny decision. Unsupported-script and indeterminate named-entity/style forms
fail closed.
It is intentionally a conservative product boundary, not a claim that lexical
matching alone solves semantic or multilingual content classification.

## Foundry RAI Policy Configuration

The Bicep deployment defines and binds `fantasy-cards-content-policy-v1`
(repository configuration version `1`) to a newly provisioned image deployment.
It inherits `Microsoft.DefaultV2` and retains blocking Medium thresholds for
Hate, Sexual, Violence, and Self-harm on both prompt and completion paths.
Jailbreak and Protected Material Text controls are explicitly retained. The
policy also binds the versioned prompt blocklist
`fantasy-cards-protected-names-v1`, whose canonical properties and exact items
are deployed from Bicep.
The deployed Container Apps receive the non-secret
`FANTASY_CARD_RAI_POLICY_NAME` and `FANTASY_CARD_RAI_POLICY_VERSION` values;
Foundry-mode application composition refuses to start if either is missing.

### Operational Verification and Updates

This repository cannot prove the state of a live Foundry resource. Before a
production release, an authorized operator must run
`infra/scripts/verify_rai_policy.py`. The `azd` post-provision hook makes this a
blocking gate whenever `DEPLOY_FOUNDRY=true`. The verifier uses the canonical
2024-10-01 ARM GET resources for the deployment, RAI policy, blocklist, and
blocklist items. It requires the deployment's `properties.raiPolicyName`, the
policy's exact `properties.contentFilters` and `properties.customBlocklists`,
and the blocklist's canonical description/item properties. Missing access,
missing properties, aliases, or drift fail the deployment gate. Environment
configuration alone is never accepted as live evidence.

Record the non-secret policy/deployment identifiers and verification timestamp
in the release evidence; do not record prompts, credentials, or endpoint
secrets. If canonical ARM reads are unavailable, production acceptance remains
blocked.

To update the policy, create a new versioned policy name, update the Bicep
parameter/default and app configuration together, run the adversarial suite,
preview the deployment, bind the new policy to the deployment, then repeat the
operational verification. Do not change an existing version in place.

## User-Facing Refusal

For an application-policy rejection, the product must return this stable,
non-judgmental message without echoing the submitted text:

> This request can't be used to create an image. Please describe an original,
> fictional subject without real people, protected characters or brands, named
> artists, or any depiction of minors.

For a provider safety rejection, retain the existing generic message:

> This description could not be generated. Revise it and try again.

The user interface must surface this policy and the refusal message before
production launch. Raw rejected prompts must not be written to telemetry.

## Review and Change Control

Rai review is required for the implementation and for any change that broadens
or narrows these categories. Reassess the policy when the model, RAI policy,
target audience, input types, or rights/licensing commitments change.

This product policy complements, and does not replace, Microsoft terms and
provider safety controls.
