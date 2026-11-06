# Billing and subscriptions

Every organisation has its own Stripe customer, subscription and plan. Nothing is shared.
`CFA_BILLING=on` activates limits; without it (self-hosting) every plan is unlimited.

## Plans (`app/billing.py`)

| Plan | Price | Agents | Messages/mo | Calls/mo | Research/mo | Uploads | MCP servers | Seats | API calls/mo | Activity retention |
|---|---|---|---|---|---|---|---|---|---|---|
| Free | 0 € | 4 | 50 | 3 | 3 | 5 | 0 | 3 | 2 000 | 7 days |
| Starter | 29 € | 10 | 1 000 | 30 | 30 | 50 | 1 | 10 | 20 000 | 30 days |
| Professional | 99 € | 25 | 5 000 | 150 | 150 | 300 | 5 | 25 | 100 000 | 90 days |
| Enterprise | on request | 100 | 25 000 | 1 000 | 1 000 | 2 000 | 25 | 200 | 500 000 | 365 days |

Legacy ids (`pro`, `team`, `pilot`) are mapped on read, so rows written before the rename keep working.

Limits are enforced **server-side**: `billing.use()` raises 402 with
`{code: "limit_reached", metric, limit, used, plan, message}` before the work happens, seat limits
block invitations, and the audit-retention endpoint refuses a window longer than the plan allows.

## Environment variables

```
CFA_BILLING=on                    # off = self-hosted, unlimited
CFA_PLAN=                         # operator override (enterprise pilots, invoiced customers)
APP_URL=https://app.example.com   # return URLs for checkout and portal
STRIPE_SECRET_KEY=sk_test_...     # test mode first
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_ENTERPRISE=price_...
CFA_GRACE_DAYS=3                  # how long past_due keeps the plan active
```

## Webhook events handled

`checkout.session.completed` (subscription), `customer.subscription.created|updated|deleted`,
`invoice.paid`, `invoice.payment_failed`, `invoice.payment_action_required`,
`invoice.payment_succeeded`, `customer.subscription.trial_will_end`.

Signature: HMAC-SHA256 over `t.payload`, 300 s tolerance, constant-time compare. Idempotency: the
Stripe event id is stored in `stripe_events`; a duplicate returns 200 and does nothing.
The organisation is resolved from `client_reference_id`, subscription metadata, then the known
customer/subscription rows — never from the request body.

## Test-mode walkthrough (required before going live)

1. `stripe login`, create three products/prices (monthly), copy the price ids into the env.
2. `stripe listen --forward-to localhost:8000/api/billing/webhook`, copy the `whsec_...`.
3. In the app: `/api/billing/checkout` with `{"plan":"starter"}` → pay with `4242 4242 4242 4242`.
4. Verify `/api/billing` shows `plan: starter`, `status: active`, `period_end` set, MRR 29 € in `/api/org/revenue`.
5. `stripe trigger invoice.payment_failed` → status `past_due`, `grace_until` set; after `CFA_GRACE_DAYS` the plan falls back to free.
6. `stripe trigger customer.subscription.deleted` → plan `free`, status `canceled`.
7. `/api/billing/portal` opens the customer portal; cancel there and confirm the webhook updates the row.
8. Open `/api/billing/invoices` and check the invoice list matches the dashboard.

Only after all eight steps pass, switch `STRIPE_SECRET_KEY`/price ids to live mode and repeat 3–8 with a
1 € test product before announcing prices.

## Revenue view

* `GET /api/org/revenue` (admin): plan, price, seats, MRR/ARR, status, period end, grace, customer since.
* `GET /api/admin/revenue` (super admin): every organisation with plan, status and MRR plus the total.
  Revenue is derived from plan price × status. It is **not** an accounting ledger — invoices stay in Stripe.

## Known limits

* Prices are per organisation, not per seat (seat limits are enforced, not billed).
* No usage-based pricing, no proration UI (Stripe prorates on plan change via checkout).
* Dunning emails are not sent by the app; Stripe sends its own if configured.
