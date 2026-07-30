---
updated_at: 2026-07-30T09:50:34+02:00
focus_area: Production Content Policy Gated on Foundry Verification
active_issues: [4, 17, 27, 34, 36, 37, 38, 82, 83]
---

# What We're Focused On

Production content-policy work moved forward, but the gate changed shape. Issue #49 is closed because the application enforcement layer landed in PR #79: production traffic now has a shared pre-provider validation gate.

The Foundry policy-hardening artifact is PR #82. It is separate from Tank's locked-out application-enforcement work and is in review with Rai's 🟡 Yellow assessment: no blocker on #82 itself, but production still needs live deployment/read-back evidence.

The new critical blocker is issue #83: verify the custom RAI controls against the live target Foundry resource and close Rai's remaining findings. The expected target account `fnd-fantasy-cards-dev-8f327f8c` is currently absent from the active subscription, so acceptance criterion 2 from #49 remains unmet.

Branch protection is still disabled. That allowed PR #79 to merge without the Rai review gate required by its own acceptance criteria, so review requirements must be enforced outside convention before production release.

The earlier production gates still matter: #37 user-facing notice, #36 retention/deletion policy, #38 likeness/IP/minors policy, and the accepted non-EU `GlobalStandard` inference risk must remain visible in any production readiness call.
