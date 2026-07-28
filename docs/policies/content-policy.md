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

The current application has no product-specific validator or denylist and uses
the provider's default policy only. It therefore does **not** yet enforce this
policy. Production is blocked on the dedicated enforcement implementation
issue filed for Tank. That work must be reviewed by Rai before release.

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
