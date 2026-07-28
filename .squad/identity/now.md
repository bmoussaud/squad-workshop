---
updated_at: 2026-07-28T10:14:07+0200
focus_area: Foundry Approved — Non-EU Inference Accepted, Prod Gated on Disclosure
active_issues: [4, 17, 27, 34, 36, 37, 38]
---

# What We're Focused On

The Foundry approval gate is settled, after a correction. On 2026-07-28 Benoit initially approved the `gpt-image-2` deployment for dev on the understanding that inference stayed within the EU. Tank and the Fact Checker, researching independently, both established from Microsoft documentation that this was false: the `GlobalStandard` deployment type processes inference in any Azure region where the model is deployed, including US regions. Issue #2 was reopened, corrected, and re-decided.

Benoit then explicitly accepted non-EU inference processing for both dev and production. This was a deliberate, informed trade: EU-bound inference is not currently purchasable for this model, since `gpt-image-2` is not offered under `DataZoneStandard` or regional `Standard` and the live subscription exposes `GlobalStandard` only. Constraining inference to the EU would mean abandoning the model. Data at rest is unaffected and remains in France Central.

Production is gated on three remaining conditions: #37 (user-facing notice), #36 (retention and deletion policy) and #38 (likeness, IP and minors policy). Issue #37 has grown teeth — the notice must now state that processing may occur outside the EU, so wording that implies EU-only handling would be factually wrong and must not ship.

Separately, branch protection is still not enabled, so CI runs on every PR without gating merges. Default generation paths remain demo stubs, so live Foundry image generation is still unverified end to end.
