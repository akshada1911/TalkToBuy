# Contract: Demo Store (UCP `2026-08-25` subset)

**Service**: `mvp/services/demo-store` (Python 3.12, FastAPI), forked from the Python merchant
server in `Universal-Commerce-Protocol/samples`.
**Consumer**: only the session server's `CommercePort` UCP adapter (the browser never calls the
store for cart or checkout). Field-level shapes follow the UCP spec and the `ucp-sdk` Python
models.
This file records what we implement and our demo-specific choices ([research.md](../research.md)
R3–R5).

## Discovery

`GET /.well-known/ucp` → declares:

- `ucp.version`: `"2026-08-25"`
- `ucp.services["dev.ucp.shopping"]`: `[{ "transport": "rest", "endpoint": "<base>/ucp/v1" }]`
- `ucp.capabilities`:
  - `dev.ucp.shopping.checkout`
  - `dev.ucp.shopping.catalog.search`
  - `dev.ucp.shopping.catalog.lookup`
  - `dev.ucp.shopping.fulfillment`
  - `dev.ucp.common.payment.ap2_mandate`
- `ucp.payment_handlers["com.example.card"]`: one mock handler (test mode)
- `keys`: ES256 JWK Set used for `ap2.merchant_authorization`

## Required request headers

| Header | Notes |
|---|---|
| `UCP-Agent` | `profile="<session-server>/agent-profile.json"` |
| `Request-Id` | UUID per request |
| `Idempotency-Key` | Required on POST/PUT. A replay returns the cached response; reusing a key with a different body returns 409 |

## Endpoints

| Method and path | Used by tool | Notes |
|---|---|---|
| `POST /ucp/v1/catalog/search` | `search_catalog` | `query`, `filters.categories`, `filters.price{min,max}` (paise), `pagination{cursor,limit≤10}`. Hybrid search (R6). Never returns excluded categories (R5) |
| `POST /ucp/v1/catalog/lookup` | `show_products`, `get_usual_order` | Product IDs → products |
| `POST /ucp/v1/checkout-sessions` | first `add_to_cart` | Creates the cart session (`incomplete`, `currency: "INR"`) |
| `GET /ucp/v1/checkout-sessions/{id}` | all cart tools | |
| `PUT /ucp/v1/checkout-sessions/{id}` | `add_to_cart`, `update_cart`, `start_checkout` | Full replacement of `line_items`. Selecting a `fulfillment` option (delivery slot) moves the session to `ready_for_complete` |
| `POST /ucp/v1/checkout-sessions/{id}/complete` | `confirm_checkout` | Body carries `ap2.checkout_mandate` and `payment.instruments[0].credential.token` (payment mandate). Verifies signature, expiry, its own `merchant_authorization`, and that lines and totals match. Errors: `mandate_required`, `mandate_invalid_signature`, `mandate_expired`, `mandate_scope_mismatch`, `merchant_authorization_invalid` |
| `POST /ucp/v1/checkout-sessions/{id}/cancel` | session ended without an order | Never used for cart edits or a "no" to the read-back; those `PUT` updated lines and return the session to `incomplete` |

`totals` always contains exactly one `subtotal` and one `total`; demo delivery is free (a
`fulfillment` total of 0), so `total == subtotal`.

## Demo-only endpoints (not UCP)

| Method and path | Purpose |
|---|---|
| `GET /demo/shoppers/{id}/last-order` | Seeded "usual order" (FR-016) |
| `GET /demo/shoppers/{id}/family` | Seeded family contact (in-app channel only) |
| `POST /demo/reset` | Reset carts and orders between rehearsals (guarded by a demo admin key) |

## Fallback (plain REST, same service)

If UCP slips, the same handlers are exposed without UCP envelopes at `/rest/v1/...` with
identical semantics, and the session server switches `COMMERCE_ADAPTER=rest`. Tools are
unchanged.
