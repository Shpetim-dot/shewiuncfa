"""Demo workspace content. Everything here is sample data, clearly marked source='demo'."""
BOTS = [("finance-analyst", "Ledger", "Finance desk", "coins"), ("compliance-reviewer", "Sentinel", "Finance desk", "shield"),
        ("research-analyst", "Scout", "Research", "book"), ("support-lead", "Nova", "Support", "chat")]
CONNECTED = ["datadog", "notion", "atlassian"]
GRANTS = [("Ledger", "notion", ["search_pages"]), ("Scout", "notion", ["search_pages"]), ("Scout", "atlassian", ["search_issues"]),
          ("Scout", "datadog", ["query_metrics"]), ("Nova", "atlassian", ["search_issues", "create_issue"]), ("Builder", "datadog", ["list_monitors"])]
NOTES = [
    ("Start here", "note", "shared", "This demo workspace shows governed agent memory. Hubs: [[Agent permissions model]], [[Memory governance]], [[Payment approval policy]], [[Council protocol]]."),
    ("Payment approval policy", "rule", "finance", "All payment proposals need human approval. See [[Spend caps]], [[Four-eyes principle]] and [[Audit trail]].\n\n- Agents only propose, they never execute\n- See [[Agent permissions model]] for what each agent may do"),
    ("Spend caps", "rule", "finance", "Per-action cap EUR 5,000, per-day cap EUR 20,000. Raising a cap needs [[Four-eyes principle]].\n\nRelated: [[Payment approval policy]], [[Vendor onboarding checklist]]."),
    ("Four-eyes principle", "rule", "finance", "Two different humans approve payments above the cap. The proposing agent never counts as an approver.\n\nSee [[Payment approval policy]] and [[Least privilege]]."),
    ("Vendor onboarding checklist", "note", "finance", "# Checklist\n- Verify the legal entity\n- Confirm bank details by call-back\n- Run sanctions screening\n\nLinks: [[Fraud signals]], [[Spend caps]], [[Supplier risk register]]."),
    ("Fraud signals", "fact", "finance", "Typical signals: changed bank details, urgency, invoices split below the cap. Split invoices evade [[Spend caps]].\n\nSee [[Prompt injection patterns]] for manipulated invoices and [[Incident response playbook]]."),
    ("Supplier risk register", "note", "finance", "Track concentration, financial health and country risk. Review quarterly.\n\nFeeds [[Decision: Q4 supplier payments pilot]]."),
    ("Incident response playbook", "rule", "shared", "# Steps\n- Stop the agent with the kill switch\n- Revoke app grants, see [[Agent permissions model]]\n- Preserve the [[Audit trail]]\n- Roll back memory, see [[Memory governance]]\n- Write the post-mortem"),
    ("Prompt injection patterns", "fact", "shared", "Hidden text in emails, tickets, documents or tool output can steer an agent.\n\nDefenses: [[Memory governance]], [[Least privilege]], approval for every write. Example: an invoice that asks the agent to change bank details ([[Fraud signals]])."),
    ("Agent permissions model", "rule", "shared", "Each agent holds capabilities and per-app tool grants. Write tools create approval requests. Secrets are never grantable.\n\nSee [[Least privilege]], [[Council protocol]], [[Audit trail]]."),
    ("Least privilege", "fact", "shared", "An agent should hold only the access its role needs. Review grants monthly.\n\nSee [[Agent permissions model]] and [[Four-eyes principle]]."),
    ("Memory governance", "rule", "shared", "Agent-written memory is a draft until an admin verifies it. Notes with instruction-like text need explicit acknowledgement. Every version is kept and can be rolled back.\n\nSee [[Prompt injection patterns]] and [[Audit trail]]."),
    ("Audit trail", "fact", "shared", "Every decision, denial and memory change is written to a hash-linked log. It detects edits, it is not an external signature.\n\nSee [[Incident response playbook]]."),
    ("Council protocol", "rule", "shared", "Agents answer independently first, then respond to each other. Dissent stays in the record. The Chair writes the decision, pre-mortem and kill criteria.\n\nExample: [[Decision: Q4 supplier payments pilot]]."),
    ("Decision: Q4 supplier payments pilot", "decision", "finance", "Recommendation: pilot propose-only payments for suppliers under EUR 5,000.\n\nDissent: the Skeptic wanted a smaller cap.\nKill criteria: any payment outside policy, or two unexplained rejections.\n\nBased on [[Payment approval policy]], [[Spend caps]] and [[Supplier risk register]]."),
]
TEAMS = [("Finance desk", "Propose, review and audit payments", ["Ledger", "Sentinel"]),
         ("Council", "Strategic decisions and plans", ["Strategist", "Skeptic", "Builder", "Chair"])]
NOTES.append(("Finance desk charter", "rule", "team:finance-desk", "The Finance desk proposes and reviews payments. Policy: [[Payment approval policy]]. Limits: [[Spend caps]]. Approval: [[Four-eyes principle]]."))
