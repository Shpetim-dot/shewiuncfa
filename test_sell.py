import hashlib
import hmac
import json
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import billing, main
from app import cfa_core as pf


def client(tmp_path, monkeypatch, keys="", **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "s.db")
    for k in ("CFA_MODEL_API_KEY", "HF_TOKEN", "CFA_HF_TOKEN", "CFA_ENV", "CFA_BILLING", "CFA_PLAN", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_PRO", "STRIPE_PRICE_TEAM", "CFA_LOGO_CDN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys)
    monkeypatch.setenv("CFA_DEMO_DELAY", "0")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    main.init_db()
    return TestClient(main.app)


def fake_hf(seen):
    f = FastAPI()

    @f.post("/v1/chat/completions")
    async def chat(req: Request):
        body = await req.json()
        seen.append({"auth": req.headers.get("authorization"), "model": body["model"], "max_tokens": body.get("max_tokens")})
        if body["model"] == "x/out-of-credits":
            return JSONResponse({"error": "credits"}, status_code=402)
        return {"choices": [{"message": {"content": "Hello from the open model.\nSTANCE: support"}}]}
    return f


def test_hugging_face_agents_use_their_own_provider_and_report_errors(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, HF_TOKEN="hf_test")
    seen: list = []
    monkeypatch.setattr(pf, "LLM_TRANSPORT", httpx.ASGITransport(app=fake_hf(seen)))
    assert c.put("/api/bots/strategist/model", json={"model": "hf:MiniMaxAI/MiniMax-M2"}).json()["live"] is True
    r = c.post("/api/bots/strategist/messages", json={"content": "hello there"}).json()
    assert r["mode"] == "live" and "Hello from the open model" in r["reply"]
    assert seen[0] == {"auth": "Bearer hf_test", "model": "MiniMaxAI/MiniMax-M2", "max_tokens": 700}
    assert c.post("/api/bots/skeptic/messages", json={"content": "hello there"}).json()["mode"] == "demo"  # default provider has no key
    assert any(b["id"] == "strategist" and b["model"] == "hf:MiniMaxAI/MiniMax-M2" for b in c.get("/api/bots").json())
    t = c.post("/api/models/test", json={"model": "hf:MiniMaxAI/MiniMax-M2"}).json()
    assert t["ok"] and t["provider"] == "hf" and t["model"] == "MiniMaxAI/MiniMax-M2"
    bad = c.post("/api/models/test", json={"model": "hf:x/out-of-credits"}).json()
    assert not bad["ok"] and "credits" in bad["message"]
    assert c.post("/api/models/test", json={"model": "openai:gpt-4o-mini"}).json()["ok"] is False  # no default key
    assert c.put("/api/bots/strategist/model", json={"model": "bad model!"}).status_code == 422
    assert c.get("/api/models").json()["providers"][1]["configured"] is True
    assert c.put("/api/bots/strategist/model", json={"model": ""}).json()["model"] is None


def test_plans_enforce_monthly_limits_and_counts(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_BILLING="on")
    monkeypatch.setitem(billing.PLANS["free"]["limits"], "messages", 2)
    for _ in range(2):
        assert c.post("/api/bots/strategist/messages", json={"content": "hello"}).status_code == 200
    r = c.post("/api/bots/strategist/messages", json={"content": "hello"})
    d = r.json()["detail"]
    assert r.status_code == 402 and d["code"] == "limit_reached" and d["metric"] == "messages" and d["limit"] == 2 and "Upgrade" in d["message"]
    b = c.get("/api/billing").json()
    assert b["enabled"] and b["plan"] == "free" and b["usage"]["messages"] == 2 and b["usage"]["agents"] == 0
    for i in range(4):
        assert c.post("/api/bots", json={"template": "custom", "name": f"Mine{i}"}).status_code == 201  # free allows 4 own agents
    assert c.post("/api/bots", json={"template": "custom", "name": "Fifth"}).status_code == 402
    monkeypatch.setenv("CFA_PLAN", "team")
    assert c.post("/api/bots/strategist/messages", json={"content": "hello"}).status_code == 200
    assert c.post("/api/bots", json={"template": "custom", "name": "Fifth"}).status_code == 201
    assert c.get("/api/billing").json()["plan_locked"] is True


def test_limits_are_off_by_default_for_self_hosting(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get("/api/billing").json()["enabled"] is False
    for _ in range(3):
        assert c.post("/api/bots", json={"template": "custom", "name": f"A{_}"}).status_code == 201


def sign(payload: bytes, secret: str, t: int | None = None) -> str:
    t = t or int(time.time())
    return f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()


def test_stripe_webhook_signature_plan_changes_and_idempotency(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_BILLING="on", STRIPE_WEBHOOK_SECRET="whsec_t", STRIPE_PRICE_PRO="price_pro", STRIPE_PRICE_TEAM="price_team")

    def send(ev, secret="whsec_t", t=None):
        body = json.dumps(ev).encode()
        return c.post("/api/billing/webhook", content=body, headers={"stripe-signature": sign(body, secret, t), "content-type": "application/json"})
    done = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"mode": "subscription", "customer": "cus_1", "subscription": "sub_1", "metadata": {"plan": "pro"}}}}
    assert send(done, secret="wrong").status_code == 400 and send(done, t=int(time.time()) - 4000).status_code == 400
    assert c.post("/api/billing/webhook", content=b"{}").status_code == 400
    assert send(done).status_code == 200 and c.get("/api/billing").json()["plan"] == "pro"
    upd = {"id": "evt_2", "type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "active", "current_period_end": 1900000000, "items": {"data": [{"price": {"id": "price_team"}}]}}}}
    send(upd)
    assert c.get("/api/billing").json()["plan"] == "team"
    send({"id": "evt_3", "type": "invoice.payment_failed", "data": {"object": {}}})
    assert c.get("/api/billing").json()["status"] == "past_due"
    send({"id": "evt_2", "type": "customer.subscription.deleted", "data": {"object": {}}})  # duplicate id: ignored
    assert c.get("/api/billing").json()["plan"] == "team"
    send({"id": "evt_4", "type": "customer.subscription.deleted", "data": {"object": {}}})
    assert c.get("/api/billing").json()["plan"] == "free"
    assert "billing.plan_changed" in [e["event_type"] for e in c.get("/api/security/audit?limit=60").json()["events"]]


def test_checkout_and_portal_talk_to_stripe_safely(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_BILLING="on", STRIPE_SECRET_KEY="sk_test_x", STRIPE_PRICE_PRO="price_pro", STRIPE_PRICE_TEAM="price_team", APP_URL="https://app.example.com")
    calls: list = []
    st = FastAPI()

    @st.post("/v1/checkout/sessions")
    async def sessions(req: Request):
        form = (await req.body()).decode()
        calls.append((req.headers.get("authorization"), form))
        return {"url": "https://checkout.stripe.com/c/pay/abc"}

    @st.post("/v1/billing_portal/sessions")
    async def portal(req: Request):
        return {"url": "https://evil.example/portal"}
    monkeypatch.setattr(billing, "STRIPE_TRANSPORT", httpx.ASGITransport(app=st))
    assert c.get("/api/billing").json()["checkout"] is True
    r = c.post("/api/billing/checkout", json={"plan": "pro"}).json()
    assert r["url"].startswith("https://checkout.stripe.com/")
    auth, form = calls[0]
    assert auth == "Bearer sk_test_x" and "price_pro" in form and "mode=subscription" in form and "app.example.com" in form
    assert c.post("/api/billing/checkout", json={"plan": "free"}).status_code == 422
    assert c.post("/api/billing/portal").status_code == 409  # no customer yet
    pf_db = __import__("sqlite3").connect(main.DB_PATH)
    pf_db.execute("INSERT OR REPLACE INTO billing (id,plan,status,customer_id) VALUES (1,'pro','active','cus_9')")
    pf_db.commit()
    assert c.post("/api/billing/portal").status_code == 502  # a foreign address is refused


def test_leads_and_funnel_events_are_public_to_write_and_private_to_read(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    h = lambda t: {"Authorization": f"Bearer {t}"}
    assert c.post("/api/leads", json={"name": "Dana Fox", "email": "dana@acme.io", "company": "Acme", "message": "pilot please"}).status_code == 201
    assert c.post("/api/leads", json={"name": "Bot", "email": "x@y.zz", "website": "http://spam"}).status_code == 201  # honeypot: dropped
    assert c.post("/api/leads", json={"name": "Dana Fox", "email": "not-an-email"}).status_code == 422
    assert c.get("/api/leads").status_code == 401 and c.get("/api/leads", headers=h("mem")).status_code == 403
    rows = c.get("/api/leads", headers=h("adm")).json()
    assert len(rows) == 1 and rows[0]["email"] == "dana@acme.io"
    assert c.post("/api/events", json={"name": "welcome_view"}).status_code == 201 and c.post("/api/events", json={"name": "made-up"}).status_code == 422
    c.post("/api/events", json={"name": "welcome_view"})
    s = c.get("/api/events/summary", headers=h("adm")).json()
    assert s["last_30_days"]["welcome_view"] == 2 and s["leads_total"] == 1


def test_presets_create_a_team_with_agents_notes_and_respect_limits(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    pre = {p["id"]: p for p in c.get("/api/presets").json()}
    assert len(pre) >= 9 and {"freelancer", "startup", "fintech", "security", "developer"} <= set(pre)
    assert c.get("/api/onboarding").json() == {"done": False, "suggest": True}
    r = c.post("/api/presets/freelancer/apply").json()
    assert r["created"] == 3 and r["team"] == "My practice" and r["notes"] == 2 and r["first_agent"]
    assert c.post("/api/presets/freelancer/apply").json()["created"] == 0 and c.get("/api/onboarding").json()["done"]
    bots = {b["name"]: b for b in c.get("/api/bots").json()}
    inv = bots["Invoice Clerk"]
    assert "payments.propose" in inv["scopes"] and inv["role"] == "Invoices, propose-only" and inv["team"] == "My practice" and "team:my-practice" in inv["spaces"]
    notes = {n["title"]: n for n in c.get("/api/brain/notes").json()}
    assert notes["Pricing rules"]["status"] == "verified" and notes["Pricing rules"]["space"] == "team:my-practice"
    assert c.post("/api/presets/nope/apply").status_code == 404
    assert c.post("/api/selftest").json()["failed"] == 0
    (tmp_path / "second").mkdir()
    d = client(tmp_path / "second", monkeypatch, CFA_BILLING="on")  # a fresh workspace
    assert d.post("/api/presets/startup/apply").status_code == 201  # a preset fits the free plan
    assert d.post("/api/presets/developer/apply").status_code == 402  # a second preset would exceed 4 own agents


def test_static_assets_revalidate_and_logo_cdn_is_configurable(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    home = c.get("/")
    assert "app.js?v=0.6.0" in home.text and home.headers["cache-control"] == "no-cache"
    assert c.get("/static/app.js").headers["cache-control"] == "no-cache"
    assert "https://cdn.simpleicons.org" in c.get("/api/health").headers["content-security-policy"]
    monkeypatch.setenv("CFA_LOGO_CDN", "")
    assert "simpleicons" not in c.get("/api/health").headers["content-security-policy"]


def test_research_has_a_live_monitor_bound_to_an_agent(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    with c.stream("POST", "/api/research/stream", json={"question": "How should payment approvals and spend caps work?", "depth": "quick"}) as r:
        evs = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in evs]
    assert types[0] == "agent" and evs[0]["agent"]["name"] == "Scout" and types[-1] == "done"
    prog = [e for e in evs if e["type"] == "progress"]
    assert prog[0]["done"] == 1 and prog[-1]["done"] == prog[-1]["total"] and [p["done"] for p in prog] == sorted(p["done"] for p in prog)
    with c.stream("GET", "/api/bots/" + evs[0]["agent"]["id"] + "/screen/stream?once=true") as s:
        kinds = [json.loads(line[6:])["kind"] for line in s.iter_lines() if line.startswith("data: ")]
    assert "research" in kinds
    assert {a["id"]: a for a in c.get("/api/apps").json()}["azure"]["logo"] == "microsoftazure"


def test_public_pages_and_info_need_no_login_and_show_real_prices(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A", CFA_CONTACT_URL="https://example.com/pilot")
    info = c.get("/api/public").json()
    assert {p["id"]: p["price_eur"] for p in info["plans"]} == {"free": 0, "pro": 19, "team": 99, "pilot": None} and info["contact"] == "https://example.com/pilot"
    for path, needle in (("/welcome", "AI agents your security team can sign off"), ("/trust", "What is enforced today")):
        r = c.get(path)
        assert r.status_code == 200 and needle in r.text and "<script>" not in r.text  # no inline scripts: the CSP forbids them
        assert r.headers["cache-control"] == "no-cache" and "script-src 'self'" in r.headers["content-security-policy"]
    assert c.get("/api/bots").status_code == 401
