### D-pr78-smoke-404-warmup-grace: Bounded retry window for transient health 404 during ACA revision warm-up
**ID:** D-pr78-smoke-404-warmup-grace
**Decided At:** 2026-07-29T15:45:00+02:00
**By:** Tank
**Status:** active
**Supersedes:** []
**What:** `infra/scripts/pr_smoke_test.py` now treats early `/health/live` and `/health/ready` HTTP 404 responses as retryable only inside a strict warm-up envelope (max 6 attempts and <45 seconds from smoke start). Outside that envelope, 404 remains fail-fast as `unexpected_status`.
**Why:** In PR environment deploys, ACA ingress/revision propagation can briefly route to no matching health path right after deploy/update, yielding short-lived 404 before the endpoint stabilizes to 200. Immediate fail-fast on first 404 creates false negatives that block downstream trusted auth configuration. A bounded grace preserves fail-closed behavior for persistent misroutes while absorbing startup jitter.
