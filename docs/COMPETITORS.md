# Competitive analysis — deep research and agent platforms

Snapshot: November 2026. Sources: [Presenc AI Deep Research comparison (May 2026)](https://presenc.ai/research/deep-research-mode-comparison-2026),
[CrewAI review](https://geekflare.com/open-source/crewai/), [agent framework analysis (CrewAI)](https://raw.githubusercontent.com/larsderidder/framework-analysis/refs/heads/main/tier-1/crewai.md),
[agent observability comparison](https://www.morphllm.com/ai-agent-observability-tools), [Langfuse vs LangSmith](https://github.com/langfuse/langfuse-docs/blob/8ffb78684e3c135320683101531aa714f8c2cd60/content/compare/langsmith.mdx),
[OWASP Top 10 for Agentic Apps 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/).

## 1. Deep research modes (what "ChatGPT Deep Research" means)

| Mode | Runtime | Sources | Strength | Weakness |
|---|---|---|---|---|
| OpenAI Deep Research | 10–30 min | 50–200 | Most comprehensive, longest synthesis | Slow, over-cites, needs $200 Pro tier |
| Gemini Deep Research | 5–15 min | 30–150 | Fast, best freshness, Google index | Weaker academic synthesis |
| Perplexity Deep Research | 3–10 min | 40–100 | Best citation-first UX, click-through verification | Summary over synthesis |
| Claude Research | 5–20 min | 20–100 | Best reasoning over contradictions | Fewer sources, expensive |
| Grok DeepSearch | 3–12 min | 30–80 | Real-time / X sources | Citation rigor inconsistent |

**What they all do well:** long-running background job, visible progress, structured report, inline citations, follow-up questions.
**What none of them does:** prove that the *agent* behaved correctly while researching, or let you govern it (approvals, memory gating, audit). That is exactly Shewiun's lane.

### What Shewiun's research needs to match (gap list)

| # | Gap in `app/research.py` today | What the leaders do | Effort |
|---|---|---|---|
| R1 | Single planning call, 2–6 fixed sub-questions | Iterative re-planning from gaps between rounds | M |
| R2 | Search only via Brave + own Brain | Source diversity check, domain dedupe, recency weighting | M |
| R3 | Report is prose + sources, no per-claim mapping | Claim → source binding, "unsupported" flags | L |
| R4 | No contradiction handling | Explicit conflict section (Claude's strength) | M |
| R5 | Fixed depth presets | Budget-aware depth (time/token cap per run) | S |
| R6 | Progress is a stream, not resumable | Durable runs (the runtime queue already exists) | S |
| R7 | No reader/citation UI | Source list with snippets and links | S |
| R8 | **Unique chance** | No competitor ties research to a governed agent (per-agent audit + approvals + memory gating) | — |

## 2. Agent frameworks

| Framework | Does well | Does badly | Shewiun position |
|---|---|---|---|
| **CrewAI** | Fastest from idea to working crew; role/goal/task vocabulary; big template gallery; large community | Governance is not the product: no approval queue tied to payloads, no per-agent audit chain; durability and resume are bolt-ons; enterprise features (control plane, RBAC) are paid/managed | We are slower to prototype, but we ship what a fintech needs: propose-only actions, approval binding, audit |
| **LangGraph** | Real durable graphs, checkpoints, human-in-the-loop interrupts, LangSmith integration | Steep learning curve, heavy config, governance left to the builder; nothing out of the box for policy or evidence | Our runtime queue is simpler, but we own the governance semantics |
| **AutoGen / AG2** | Research-friendly multi-agent conversation, good for experiments | Production story weak (state, observability, deployment) | Not our market |
| **OpenAI Agents SDK** | Clean primitives, tracing, handoffs | Vendor lock-in, no EU-first governance, no approval evidence | We are model-agnostic |
| **n8n / low-code** | Integrations, non-developers | No agent governance semantics | Partner, not competitor |

**Read:** every framework optimises *building* agents. Nobody optimises *proving* what an agent did and *stopping* it at the right moment. Shewiun should not compete on "build faster" — it should compete on "sign off without reading logs".

## 3. Observability and governance players

| Player | Strength | Weakness Shewiun can exploit |
|---|---|---|
| LangSmith / Langfuse / AgentOps | Traces, evals, cost per call | They observe; they do not *decide*. No approval queue, no memory quarantine |
| TrueFoundry / Kong / Portkey | MCP/LLM gateway, policy at the proxy, scale | Platform teams only; no per-agent memory governance, no evidence report |
| HumanLayer | Human-in-the-loop approvals | Approval without memory model or audit evidence |
| Modulos / Saidot / Trustible / Monitaur / VerifyWise | Regulatory frameworks, control mapping, agent inventory | Heavy compliance tooling, little day-to-day agent operation |

## 4. Where Shewiun wins (and must stay)

1. **Evidence, not logs.** The 44-probe self-test plus a shareable report is a sales artefact, not a dashboard.
2. **Approval bound to the action** (payload hash + policy version + TTL + atomic claim). Most competitors approve a *tool name*, not a *payload*.
3. **Memory governance** — draft → verified, spaces, instruction quarantine, versioning, rollback. Nobody in the comparison has this as a product surface.
4. **Per-agent audit chain (new).** Every agent has its own hash-linked log with export. Frameworks give you traces; we give you a chain you can hand to an auditor.
5. **EU-first, single-tenant deployable.** Finance and security buyers cannot put agent traces into a US SaaS on day one.

## 5. Where Shewiun loses today

| Weakness | Consequence | Fix |
|---|---|---|
| Research quality below the big five | "Why not just use ChatGPT?" | R1–R5 above, plus a "verified sources only" mode |
| No SDK / no proxy into *existing* agents | Customer must rebuild agents here | `/v1` OpenAI-compatible proxy + MCP proxy (planned) |
| No SSO/SAML, no SOC 2 | Enterprise procurement blocks | Roadmap 6–9 months |
| Single-node SQLite | Scale ceiling ~50 orgs | Postgres + durable queue |
| No eval harness | Cannot prove quality over time | Reuse the self-test runner for prompt evals |

## 6. Production gaps (what an app like this still needs)

**Blocking a paid production customer**
1. Durable rate limiting (per org/API key), currently in-process per IP.
2. Backup/restore drill + documented RPO/RTO; backups are instance-wide.
3. Observability: structured logs are there, no metrics/traces, no alerting.
4. Stripe live walkthrough (test mode only so far), dunning mails, invoice emails.
5. GDPR: deletion endpoint that also covers audit/agent logs under a retention policy.
6. Email delivery (SMTP exists, no templates, no bounce handling).
7. SSO/SAML + SCIM for ≥50 seats.
8. Status page + incident process + SLA text.
9. Postgres migration path + horizontal worker.
10. Security review: external pentest, dependency scanning in CI, secret scanning.

**Differentiating but not blocking**
11. Eval harness with regression gates per agent.
12. Cost forecasting per org (trend + budget alerts).
13. Agent-to-agent message signing (OWASP inter-agent risk).
14. Computer-use provider (contract exists, no implementation).
15. Marketplace with versioning and signatures.

## 7. Announcements (implemented)

`app/announcements.py`: platform-wide notices for super admins, organisation notices for admins,
audiences `engineering`/`all`, expiry, no HTML, audit event on create. This is the notice board an
engineering team expects inside the tool ("we changed the approval TTL", "new model available").
