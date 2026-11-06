"""Starter presets: a team of agents with roles, rights, a shared memory and sample work for a kind of user."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app import cfa_core as pf

router = APIRouter()
R = ["memory.read", "call.join"]
W = ["memory.read", "memory.write", "call.join"]
F = W + ["approval.request", "payments.propose"]


def A(name: str, role: str, icon: str, color: str, scopes: list[str], system: str) -> dict[str, Any]:
    return {"name": name, "role": role, "icon": icon, "color": color, "scopes": scopes, "system": system}


PRESETS: dict[str, dict[str, Any]] = {
    "freelancer": {"name": "Freelancer", "tagline": "Win clients, price work, get paid", "audience": "Solo consultants, designers, developers", "team": "My practice", "mission": "Win and deliver client work",
        "agents": [A("Scout", "Client research", "book", "#3D7A4F", W, "You research prospects and clients from the verified notes, list what is known and unknown and never invent facts."),
                   A("Proposal Writer", "Proposals and offers", "pen", "#2F5BD3", W, "You draft clear proposals. State scope, assumptions and price logic. Never promise dates you were not given."),
                   A("Invoice Clerk", "Invoices, propose-only", "coins", "#1F6F8B", F, "You prepare invoices and reminders. You only propose payments or actions; a human approves.")],
        "notes": [("Pricing rules", "rule", "Hourly floor is EUR 90. Fixed offers add a 20% risk buffer. Payment terms are 14 days. See [[Client onboarding checklist]]."),
                  ("Client onboarding checklist", "note", "# Before work starts\n- Signed scope and price, see [[Pricing rules]]\n- Named contact and approver\n- First invoice date agreed")],
        "topic": "Should I take a fixed-price project at EUR 4,000 for a client who changed the scope twice?"},
    "startup": {"name": "Startup founder", "tagline": "Decide faster with a skeptical co-founder", "audience": "Founders and small product teams", "team": "Founding team", "mission": "Make good product and growth decisions",
        "agents": [A("Product Strategist", "Direction and priorities", "compass", "#2F5BD3", W, "You find the opportunity, the outcome and the priorities. Be concrete and name trade-offs."),
                   A("Growth Marketer", "Acquisition experiments", "rocket", "#B5543C", W, "You propose small, measurable acquisition experiments with a stop rule."),
                   A("Engineering Lead", "Build and scope", "wrench", "#1B7F79", W, "You turn ideas into an MVP scope, dependencies and risks."),
                   A("Skeptic CFO", "Runway and risk", "scales", "#B7791F", W, "You challenge assumptions about cost, runway and demand. Name what would make this fail.")],
        "notes": [("Runway rule", "rule", "Keep 12 months of runway. Any new recurring cost above EUR 500 per month needs a decision note. See [[Experiment rule]]."),
                  ("Experiment rule", "rule", "Every growth experiment has a budget, a metric and a stop date. See [[Runway rule]].")],
        "topic": "Should we raise prices by 20% or add a cheaper plan?"},
    "agency": {"name": "Agency", "tagline": "Deliver client work with a QA loop", "audience": "Small agencies and consultancies", "team": "Client delivery", "mission": "Deliver client projects on time and on quality",
        "agents": [A("Account Lead", "Scope and client comms", "chat", "#2F5BD3", W, "You keep scope, expectations and client communication clear. Flag scope creep."),
                   A("Researcher", "Market and client research", "book", "#3D7A4F", W, "You summarize verified sources and separate evidence from assumptions."),
                   A("Deck Builder", "Structure and storyline", "chart", "#7A4E9C", W, "You structure decks and reports around one message per slide."),
                   A("QA Reviewer", "Quality gate, read-only", "shield", "#5B6B88", R, "You review work against the verified standards and list gaps. You never edit.")],
        "notes": [("Delivery standard", "rule", "Every deliverable states the question, the answer, the evidence and the open risks. See [[Scope change rule]]."),
                  ("Scope change rule", "rule", "A scope change needs a written estimate before work starts. See [[Delivery standard]].")],
        "topic": "The client asks for three extra markets in the same deadline. How do we respond?"},
    "fintech": {"name": "Fintech risk desk", "tagline": "Agents that propose, humans that approve", "audience": "Fintech, payments and banking teams", "team": "Risk desk", "mission": "Review and propose payments without ever executing them",
        "agents": [A("Ledger", "Payments, propose-only", "coins", "#1F6F8B", F, "You review invoices and propose payments. You never execute. Cite the policy for every figure."),
                   A("Sentinel", "Compliance review, read-only", "shield", "#7A4E9C", R, "You check statements against the verified policies and name gaps. You cannot change anything."),
                   A("Policy Analyst", "Policy research", "book", "#3D7A4F", W, "You summarize policies and flag conflicts between them."),
                   A("Incident Lead", "Incident response", "radar", "#B5543C", W, "You coordinate incident steps: contain, preserve evidence, communicate. Escalate to a human.")],
        "notes": [("Payment approval policy", "rule", "Every payment proposal needs human approval. See [[Spend caps]] and [[Four-eyes principle]]."),
                  ("Spend caps", "rule", "Per-action cap EUR 5,000, per-day cap EUR 20,000. See [[Payment approval policy]]."),
                  ("Four-eyes principle", "rule", "Two different humans approve payments above the cap. The proposing agent never counts.")],
        "topic": "Should an AI agent propose supplier payments under EUR 5,000?"},
    "security": {"name": "Security team", "tagline": "Govern the agents your company already runs", "audience": "Security and platform teams", "team": "Agent security", "mission": "Know, limit and prove what agents can do",
        "agents": [A("Threat Triage", "Alert triage", "radar", "#B5543C", W, "You rank alerts by impact, cite the verified playbooks and never take containment actions yourself."),
                   A("Policy Reviewer", "Policy checks, read-only", "shield", "#7A4E9C", R, "You compare an agent's rights with the least-privilege policy and list excess rights."),
                   A("Red Team Planner", "Attack planning, read-only", "bug", "#B7791F", R, "You list how an agent boundary could be crossed. You only plan tests, you never run attacks."),
                   A("Incident Commander", "Incident coordination", "compass", "#2F5BD3", W, "You run the incident checklist and keep a timeline. Escalate to a human.")],
        "notes": [("Agent threat model", "fact", "Main risks: tool misuse, over-broad identity, poisoned memory, hidden instructions in tool text. See [[Least privilege rule]]."),
                  ("Least privilege rule", "rule", "Every agent holds only the tools and memory its job needs. Review grants monthly. See [[Agent threat model]].")],
        "topic": "Which of our agents hold rights they do not need?"},
    "developer": {"name": "Developer", "tagline": "A review board for your code changes", "audience": "Solo developers and small engineering teams", "team": "Code review board", "mission": "Catch bugs, gaps in tests and security issues before merge",
        "agents": [A("Code Reviewer", "Bugs and readability", "terminal", "#2F5BD3", W, "You review code changes for bugs, edge cases and readability. Quote the line you mean."),
                   A("Architect", "Design and boundaries", "graph", "#1B7F79", W, "You assess design, coupling and where the change will hurt later."),
                   A("Test Engineer", "Missing tests", "flask", "#3D7A4F", W, "You list the tests that are missing and which failure each would catch."),
                   A("Security Reviewer", "Security review, read-only", "bug", "#B5543C", R, "You review for injection, secrets, authorization and unsafe defaults. You never run code.")],
        "notes": [("Review standard", "rule", "Every change needs a test for the behavior it changes, no secrets in code and a clear rollback. See [[Security checklist]]."),
                  ("Security checklist", "rule", "Check input validation, authorization on every route, secrets, logging of sensitive data. See [[Review standard]].")],
        "topic": "Review this change for bugs, missing tests and security issues:\n\n<paste your diff here>"},
    "shop": {"name": "Online shop", "tagline": "Support, returns and pricing in one team", "audience": "E-commerce and small retail", "team": "Shop operations", "mission": "Answer customers fast without risky refunds",
        "agents": [A("Support Lead", "Customer replies", "chat", "#B5543C", W + ["approval.request"], "You answer customers from the verified policies. Anything involving money goes to approval."),
                   A("Returns Analyst", "Returns patterns", "table", "#2F5BD3", W, "You find patterns in returns and name likely causes. Mark guesses as assumptions."),
                   A("Pricing Analyst", "Pricing and margin", "chart", "#7A4E9C", W, "You test pricing ideas against margin and demand. Show the arithmetic."),
                   A("Fraud Watcher", "Fraud signals, read-only", "radar", "#B7791F", R, "You flag suspicious orders using the verified signals. You never block orders yourself.")],
        "notes": [("Refund policy", "rule", "Refunds up to EUR 50 within 30 days are approved by the support lead's request. Above that a human decides. See [[Fraud signals]]."),
                  ("Fraud signals", "fact", "Typical signals: new account with a large order, shipping to a different country, repeated failed payments. See [[Refund policy]].")],
        "topic": "A customer asks for a EUR 120 refund after 40 days. What do we do?"},
    "researcher": {"name": "Researcher", "tagline": "Evidence first, with a devil's advocate", "audience": "Analysts, journalists, students", "team": "Research desk", "mission": "Produce findings that survive scrutiny",
        "agents": [A("Desk Researcher", "Find and summarize", "book", "#3D7A4F", W, "You summarize what the verified sources support and separate evidence from assumptions."),
                   A("Source Checker", "Source quality, read-only", "lens", "#2F5BD3", R, "You judge how reliable each source is and what would change your mind."),
                   A("Synthesizer", "Write the finding", "spark", "#7A4E9C", W, "You write the finding in plain language with numbered citations and open questions."),
                   A("Devil's Advocate", "Counterarguments, read-only", "scales", "#B7791F", R, "You argue the strongest opposite case from the same evidence.")],
        "notes": [("Citation rule", "rule", "Every number needs a numbered source. Unsourced claims are marked Assumed. See [[Source quality]]."),
                  ("Source quality", "rule", "Prefer primary sources, then reputable secondary ones. Note the date. See [[Citation rule]].")],
        "topic": "What does the evidence say about whether agents should be allowed to write their own long-term memory?"},
    "legal": {"name": "Contracts", "tagline": "Read contracts faster, with a human decision", "audience": "Small legal teams and operations (not legal advice)", "team": "Contract desk", "mission": "Surface risky clauses for a human to decide",
        "agents": [A("Contract Reader", "Summaries", "doc", "#2F5BD3", W, "You summarize contracts clause by clause. You do not give legal advice and say so when asked."),
                   A("Risk Flagger", "Clause risks, read-only", "shield", "#B5543C", R, "You flag clauses that deviate from the verified playbook and explain why."),
                   A("Clause Librarian", "Playbook and precedents", "book", "#3D7A4F", W, "You keep the playbook of preferred clauses and fallbacks.")],
        "notes": [("Contract playbook", "rule", "Liability cap at 12 months of fees. Termination for convenience with 30 days notice. Governing law named explicitly. See [[Escalation rule]]."),
                  ("Escalation rule", "rule", "Anything outside the playbook goes to a lawyer. The agents never sign or send. See [[Contract playbook]].")],
        "topic": "This vendor contract has unlimited liability. How should we respond?"},
}


# What each preset really changes. Counts below are computed from the preset itself; only "level" and "flow" are written by hand.
# Nothing here promises background automation: a flow is a Council discussion you start yourself.
INFO: dict[str, dict[str, str]] = {
    "freelancer": {"level": "Light", "flow": "No shared flow. You talk to each agent on its own: research a client, write a proposal, prepare an invoice."},
    "startup": {"level": "Team", "flow": "Decision flow: strategy, growth and engineering each give an opening position, the Skeptic CFO challenges cost and runway, the Chair writes the decision. You start it as a Council call."},
    "agency": {"level": "Team", "flow": "Delivery flow with a quality gate: account, research and deck agents work, the read-only QA Reviewer checks against your standard."},
    "fintech": {"level": "Governed", "flow": "Propose-only flow: agents draft payments, a human approves, two humans above the cap. Nothing is executed by an agent."},
    "security": {"level": "Governed", "flow": "Review flow: triage ranks alerts, read-only agents compare rights with policy and plan tests. Containment stays with humans."},
    "developer": {"level": "Team", "flow": "Review board: four agents read the same change and list bugs, missing tests and security issues. Nobody runs code."},
    "shop": {"level": "Team", "flow": "Support flow: replies come from verified policies, anything with money goes to approval, a read-only agent watches fraud signals."},
    "researcher": {"level": "Team", "flow": "Evidence flow: find, check sources, synthesize with citations, then a read-only devil's advocate argues the other side."},
    "legal": {"level": "Governed", "flow": "Contract flow: summarize, flag clauses against your playbook, escalate to a lawyer. Agents never sign or send."},
}


def _public(pid: str, p: dict[str, Any]) -> dict[str, Any]:
    ag = p["agents"]
    info = INFO.get(pid, {"level": "Team", "flow": ""})
    return {"id": pid, "name": p["name"], "tagline": p["tagline"], "audience": p["audience"], "team": p["team"], "topic": p["topic"],
            "agents": [{k: a[k] for k in ("name", "role", "icon", "color", "scopes")} for a in ag], "notes": len(p["notes"]),
            "level": info["level"], "flow": info["flow"],
            "read_only": sum("memory.write" not in a["scopes"] for a in ag),
            "can_request_approval": any("approval.request" in a["scopes"] for a in ag),
            "proposes_payments": any("payments.propose" in a["scopes"] for a in ag)}


@router.get("/api/presets")
def list_presets() -> list[dict[str, Any]]:
    return [_public(k, v) for k, v in PRESETS.items()]


@router.get("/api/onboarding")
def onboarding() -> dict[str, bool]:
    o = pf.org()
    with pf.db() as con:
        done = con.execute("SELECT 1 FROM org_settings WHERE org_id=? AND key='onboarded'", (o,)).fetchone() is not None
        custom = con.execute("SELECT COUNT(*) FROM bots WHERE id NOT IN ('strategist','skeptic','builder','chair') AND org_id=?",
                             (o,)).fetchone()[0] > 0
    return {"done": done or custom, "suggest": not (done or custom)}


@router.post("/api/onboarding/complete")
def onboarding_complete(request: Request) -> dict[str, bool]:
    pf.need_admin(request)
    with pf.db() as con:
        con.execute("INSERT OR REPLACE INTO org_settings (org_id, key, value) VALUES (?,'onboarded','1')", (pf.org(),))
    return {"done": True}


@router.post("/api/presets/{pid}/apply", status_code=201)
def apply_preset(pid: str, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    preset = PRESETS.get(pid)
    if not preset:
        raise HTTPException(404, "unknown preset")
    from app import billing, governance as g
    made: list[str] = []
    with pf.db() as con:
        existing = {r["name"] for r in con.execute("SELECT name FROM bots WHERE org_id=?", (pf.org(),))}
        new = [a for a in preset["agents"] if a["name"] not in existing]
        billing.check_count("agents", billing.agent_count(con), len(new))
        for a in new:
            made.append(g._create_bot(con, "custom", a["name"], a["scopes"], None, p["name"], icon=a["icon"], team=preset["team"], color=a["color"], source="preset", trust="verified", source_ref=pid, system=a["system"], role=a["role"])["id"])
        names = [a["name"] for a in preset["agents"]]
        ids = [r["id"] for r in con.execute("SELECT id FROM bots WHERE name IN (%s) AND org_id=?" % ",".join("?" * len(names)), (*names, pf.org()))]
        team = con.execute("SELECT * FROM teams WHERE name=? AND org_id=?", (preset["team"], pf.org())).fetchone()
        space = team["space"] if team else g._make_team(con, preset["team"], preset["mission"], ids, p["name"])["space"]
        notes = 0
        for title, kind, body in preset["notes"]:
            if not con.execute("SELECT 1 FROM notes WHERE title=? AND org_id=?", (title, pf.org())).fetchone():
                pf.add_note(con, title, body, kind, p["name"], f"preset:{pid}", "verified", space)
                notes += 1
        con.execute("INSERT OR REPLACE INTO org_settings (org_id, key, value) VALUES (?,'onboarded','1')", (pf.org(),))
        con.commit()
    pf._m().append_audit("preset.applied", p["name"], {"preset": pid, "agents": len(made), "notes": notes})
    first = ids[0] if ids else None
    return {"preset": pid, "agents": [a["name"] for a in preset["agents"]], "created": len(made), "team": preset["team"], "notes": notes, "topic": preset["topic"], "first_agent": first}
