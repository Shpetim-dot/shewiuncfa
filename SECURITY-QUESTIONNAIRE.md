# Pre-written security answers (honest, as of v0.6)

Use these as a starting point for buyer questionnaires. Answer "no" where it is no.

| Question | Answer |
|---|---|
| Do you hold SOC 2 / ISO 27001? | No. We publish what is enforced on /trust. |
| Is there SSO / SAML / SCIM? | No. Role-based access keys (admin, member, viewer), stored hashed. |
| Is customer data isolated? | Each customer runs an isolated instance and database. No shared multi-tenant store. |
| Where is data stored? | In the SQLite database on the host the customer chooses. Region = host region. |
| Encryption at rest? | MCP tokens are encrypted with a customer-held key. The database file relies on volume or disk encryption of the host. |
| Encryption in transit? | HTTPS terminated by the host or proxy. HSTS is sent in production. |
| Do you train models on customer data? | No. The product does not train models. The configured model provider's terms apply to prompts. |
| Which sub-processors? | Hosting provider, the configured model provider, Stripe (if enabled), Brave Search (if enabled). |
| How is access controlled? | Per-key roles; per-agent capabilities and tool grants; admin-only changes; all audited. |
| Is there an audit log? | Yes: hash-linked, tamper-evident, exportable as NDJSON. It is not externally signed. |
| Can agents take actions? | Only through granted tools. Write tools require human approval. Secret-looking tools cannot be granted. |
| Do agents run code? | No. |
| Protection against prompt injection? | Untrusted text is delimited; instruction-like memory is quarantined; no automatic trust of tool text. Detection is pattern based and not a guarantee. |
| Memory poisoning? | Agent memory is a draft until an admin verifies it; versions and rollback exist. |
| SSRF protection? | MCP URLs to private, loopback and link-local addresses are blocked; redirects are not followed. |
| Backups? | Online backups on demand, retention configurable. Customers keep copies off-host. |
| Incident response? | Incident switch suspends all agents; audit log preserved. A written IR plan is customer-specific. |
| Penetration test? | Not yet. |
| Vulnerability disclosure? | Contact on /trust. |
| Data deletion? | Retention job and full JSON export. Deleting the instance deletes all data. |
| Uptime / SLA? | None for the beta. |
