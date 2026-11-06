# Deploying Shewiun CFA (single-node beta)

This is built for **one instance per customer** with SQLite on a persistent volume. It is production-ready for a closed beta,
not for multi-tenant SaaS. Run exactly one worker: the rate limiter and SQLite writer assume one process.

## 1. Before the first start
1. Generate the encryption key: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` and store it **apart from backups**.
2. Choose the first admin token (a long random string) and set `CFA_API_KEYS=<token>:admin:You`. Create further keys in Settings later.
3. Set `CFA_ENV=production`. The app then refuses to start without access keys, `CFA_SECRET_KEY` and a database outside `/tmp`.
4. Mount a volume at `/data` and set `CFA_DATABASE_PATH=/data/cfa.db`.
5. Put the app behind HTTPS (Fly, Render or your own proxy). Set `FORWARDED_ALLOW_IPS=*` only behind a proxy you control: rate limits read `X-Forwarded-For`.

## 2. Models
- Any OpenAI-compatible endpoint: `CFA_MODEL_BASE_URL`, `CFA_MODEL_API_KEY`, `CFA_MODEL_NAME`.
- Free open models: create a Hugging Face token (`HF_TOKEN`) and give an agent a model such as `hf:MiniMaxAI/MiniMax-M2` (Settings shows suggestions and a connection test). The free tier has monthly credits and rate limits.
- `CFA_MAX_TOKENS` caps the length of every reply (cost control).

## 3. Selling it
1. `CFA_BILLING=on` enforces the Free plan limits. Set `CFA_PLAN=pilot` on an invoiced customer's instance.
2. Stripe **test mode** first: create two recurring prices, set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_TEAM`, `APP_URL`.
3. Add a webhook endpoint `https://<your-host>/api/billing/webhook` for `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`; set `STRIPE_WEBHOOK_SECRET`. Locally: `stripe listen --forward-to localhost:8000/api/billing/webhook`.
4. Walk through a test purchase, a plan change and a cancellation before taking real money. The Stripe code is covered by unit tests, not yet exercised against the live service.
5. `/welcome` is your public page, `/trust` your trust page. Set `CFA_LEADS_WEBHOOK` to get leads in Slack and `CFA_CONTACT_URL` / `CFA_SECURITY_CONTACT`.

## 4. Operating it
- **Readiness:** `/api/health/ready` (200 or 503 with reasons). Logs are one JSON line per request with a request id; share links are masked.
- **Backups:** Settings > Backups and data, or `POST /api/admin/backup`. Keep copies off the host. Restore: stop the app, replace `/data/cfa.db` with the backup, start.
- **Retention:** Settings > Run retention deletes old chats, activity, calls and research. The audit log is never purged.
- **Incident:** Control > Incident switch suspends every agent. Revoke keys in Settings.
- **Upgrades:** deploy the new image; the schema migrates itself on start. Take a backup first.
- **Key rotation:** create a new admin key, sign in with it, revoke the old one. Changing `CFA_SECRET_KEY` makes stored MCP tokens unreadable: re-add those servers.

## 5. Known limits
Single node and SQLite. Tokens, not user accounts or SSO. Pattern-based injection detection. No code execution by agents. Prompts go to your model provider.
