# Security review (v7)

Verified by tests: payload tampering, expiry, permission change after approval, double execution, unapproved execution, admin-only provider/price/budget/accountability changes, SSRF rejection for provider URLs (http, loopback, link-local), provider key never in API output, audit log or usage rows, per-agent space filtering in Brain search, suspended agents refused, computer use refused without a provider.

Not verified or not built: tenant isolation (single tenant), MFA/SSO, dependency scan, penetration test, DNS-rebinding protection at call time, rate limits tied to cost, prompt-injection test corpus beyond the existing instruction-like flag. Treat the list in KNOWN_LIMITATIONS.md as release blockers for multi-customer hosting.
