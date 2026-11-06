# Per-agent audit trail

`app/agent_audit.py` — implemented, 6 tests in `tests/test_agent_audit.py`.

## Why

The organisation-wide audit log answers "what happened in this workspace". A reviewer asking
"what did *this agent* do, and can I prove it was not edited afterwards?" needs a per-agent chain.
Every agent now has its own append-only, hash-linked log.

## Model

```
agent_audit(seq PK AUTOINCREMENT, id, org_id, bot_id, ts, kind, actor, summary,
            payload_json, prev_hash, hash)
```

`hash = sha256(id, org_id, bot_id, ts, kind, actor, summary, payload, prev_hash)` — the first entry
of an agent starts at `GENESIS`, every later entry chains to the previous hash **of that agent**.
Editing or deleting one row breaks the chain for that agent only (tested).

## What is recorded

| kind | written by |
|---|---|
| `message`, `reply` | chat (`cfa_core.send_message`), including which notes were used |
| `tool.denied` | tool call without grant / suspended agent (`mcp_apps.call_tool`) |
| `tool.call` | executed read tool (live or demo) |
| `tool.requested` | write tool that became an approval request |
| `action` | propose-only agent action (`governance.agent_action`) |

Further hooks are intentionally cheap to add: `agent_audit.append(bot_id, kind, actor, summary, payload)`
never raises, so a failing log can not break a business request.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/bots/{id}/audit?limit=&before=` | newest first, with `integrity` block and `total` |
| `GET /api/bots/{id}/audit/verify` | walks the chain, returns `{valid, checked, head}` |
| `GET /api/bots/{id}/audit/export` | NDJSON download for auditors |

All three are scoped to the caller's organisation and 404 for unknown agents.

## Operations

* The trail is not purged by the retention job today; it follows the data-retention policy of the
  deployment (documented in `docs/TENANCY.md`).
* Export + verify together are the evidence package: hand over the NDJSON and the verification
  result, not screenshots.
