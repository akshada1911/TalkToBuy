# Store wire format (demo store ⇄ session server)

The concrete JSON both sides implement. Refines `specs/001-talktobuy-assistant/contracts/store-ucp.md`.
UCP spec version **`2026-08-25`** (`ucp-sdk` 0.5.x). Money is integer **paise** everywhere on the
wire; only the session server converts to rupees for the model and the UI.

## Common

- Base path: `/ucp/v1`. Discovery: `GET /.well-known/ucp`.
- Required request headers on every `/ucp/v1/*` call: `UCP-Agent: profile="<url>"`,
  `Request-Id: <uuid>`. `Idempotency-Key: <uuid>` is required on every POST/PUT. A replay with
  the same key and body returns the cached response; the same key with a different body returns
  409 `IDEMPOTENCY_CONFLICT`.
- Errors use the UCP envelope:
  `{"ucp":{"version":"2026-08-25","status":"error"},"messages":[{"type":"error","code":"…","content":"…","severity":"…"}]}`.
- Every response has a top-level `"ucp": {"version": "2026-08-25", ...}`.

## Product (UCP catalog product + our metadata)

```json
{
  "id": "p-0112",
  "title": "Toned Milk 1 L",
  "description": {"plain": "Pasteurised toned milk."},
  "categories": [{"value": "dairy"}],
  "price_range": {"min": {"amount": 5400, "currency": "INR"}, "max": {"amount": 5400, "currency": "INR"}},
  "media": [{"type": "image", "url": "https://…"}],
  "variants": [{"id": "p-0112", "title": "1 L", "price": {"amount": 5400, "currency": "INR"},
                "availability": {"available": true}}],
  "metadata": {"talktobuy": { /* full domain Product, exactly per mvp/contracts/domain.schema.json#/$defs/Product */ }}
}
```

The session server reads **only** `metadata.talktobuy` (validated against the domain `Product`).
The UCP fields are filled for spec conformance.

## Catalogue

`POST /ucp/v1/catalog/search`

```json
{"query": "पाव किलो टमाटर", "filters": {"categories": ["produce"], "price": {"min": 0, "max": 50000}},
 "pagination": {"limit": 10}}
```

→ `{"ucp":{…}, "products":[Product…], "pagination":{"has_next_page":false},
"metadata":{"talktobuy":{"ambiguous":false,"scores":{"p-0007":0.91}}}}`

- At most 10 products, in-stock first. Out-of-stock products are returned with
  `in_stock:false`.
- Medicine and supplement categories never exist in the catalogue (excluded at import).
- `ambiguous` is true when the top two scores are within 0.05.

`POST /ucp/v1/catalog/lookup` takes `{"ids":["p-0112","p-0007"]}` → `{"ucp":{…},"products":[Product…]}`,
in request order. Unknown IDs are omitted.

## Checkout session = the cart

`POST /ucp/v1/checkout-sessions` takes `{"currency":"INR","line_items":[{"item":{"id":"p-0112"},"quantity":2}]}`.
It accepts an empty `line_items` and returns 201 with a Checkout.

`GET /ucp/v1/checkout-sessions/{id}` returns the Checkout.

`PUT /ucp/v1/checkout-sessions/{id}` is a full replacement:
`{"currency":"INR","line_items":[…],"fulfillment":{"selected_option_id":"slot-1800"}|null}`

- **Changing `line_items` always clears the fulfillment selection**, which returns the session
  to `incomplete`.
- Selecting an option with a non-empty cart sets the status to `ready_for_complete`.
- A PUT on a `completed` or `canceled` session returns 409 `CHECKOUT_NOT_MODIFIABLE`.
- Unknown product → 400 `INVALID_REQUEST`. Selecting a slot while any line is out of stock → 400
  `OUT_OF_STOCK`, naming the product.

Checkout response:

```json
{
  "ucp": {"version": "2026-08-25"},
  "id": "chk_…",
  "status": "incomplete | ready_for_complete | complete_in_progress | completed | canceled",
  "currency": "INR",
  "line_items": [{"id": "li_1", "item": {"id": "p-0112", "title": "Toned Milk 1 L", "price": 5400},
                  "quantity": 2, "totals": [{"type": "subtotal", "amount": 10800}, {"type": "total", "amount": 10800}]}],
  "totals": [{"type": "subtotal", "amount": 101600}, {"type": "fulfillment", "amount": 0}, {"type": "total", "amount": 101600}],
  "fulfillment": {
    "methods": [{"id": "m_delivery", "type": "shipping", "line_item_ids": ["li_1"],
      "groups": [{"id": "g1", "selected_option_id": "slot-1800",
        "options": [{"id": "slot-1800", "title": "6–7 pm",
                     "metadata": {"label_hi": "शाम 6 से 7 बजे", "label_en": "6–7 pm",
                                  "start": "2026-10-17T18:00:00+05:30", "end": "2026-10-17T19:00:00+05:30"},
                     "totals": [{"type": "total", "amount": 0}]}]}]}]
  },
  "links": [],
  "ap2": {"merchant_authorization": "<detached JWS header..signature>"},
  "order": null,
  "metadata": {"talktobuy": {"item_count": 10, "out_of_stock": []}}
}
```

- `item_count` is the number of distinct products.
- `totals` holds exactly one `subtotal` and one `total`, and `total` equals the sum of the
  others. Delivery is free.
- `ap2.merchant_authorization` is present on every checkout response: an ES256 detached JWS over
  the RFC 8785 canonical JSON of the checkout with `ap2` removed.
- Slot `"earliest"` is accepted in `selected_option_id` and resolves to the first open slot.

`POST /ucp/v1/checkout-sessions/{id}/complete`:

```json
{"ap2": {"checkout_mandate": "<compact JWS or SD-JWT>"},
 "payment": {"instruments": [{"handler_id": "com.example.card", "credential": {"token": "<payment mandate>"}}]}}
```

- On success it moves the session `ready_for_complete → complete_in_progress → completed`,
  returns the Checkout with `"order": {"id": "ord_…", "delivery": {…slot…}, "mode": "test"}`,
  and records the order for `/demo/shoppers/{id}/last-order`.
- On failure it returns 402 with a code of `mandate_required`, `mandate_invalid_signature`,
  `mandate_expired`, `mandate_scope_mismatch` or `merchant_authorization_invalid`.
- If the status is not `ready_for_complete` it returns 409.
- An Idempotency-Key replay returns the same order.

`POST /ucp/v1/checkout-sessions/{id}/cancel` → `canceled`. It is only used when a session ends
without an order.

## Payment trusted surface (called by the shop app in the browser, not the session server)

| Method and path | Body → Response |
|---|---|
| `POST /payment/webauthn/register/options` | `{shopper_id}` → WebAuthn `PublicKeyCredentialCreationOptions` (JSON) |
| `POST /payment/webauthn/register/verify` | `{shopper_id, credential}` → `{ok:true}` |
| `POST /payment/webauthn/assert/options` | `{shopper_id, checkout_id}` → `PublicKeyCredentialRequestOptions`; challenge = SHA-256 of the merchant-authorised canonical checkout |
| `POST /payment/approve` | `{shopper_id, checkout_id, credential}` → `{checkout_mandate, payment_mandate, expires_at}` (test mode) |

## Demo endpoints

| Method and path | Response |
|---|---|
| `GET /demo/shoppers/{id}` | `Shopper` (domain schema): `{id:"u-ghanshyam", display_name:"Ghanshyam ji", language:"hi", address_form:"respectful_male"}` |
| `GET /demo/shoppers/{id}/last-order` | `{"order_id":"…","lines":[{"product":Product,"qty":1}…]}` (seeded until a real order exists) |
| `GET /demo/shoppers/{id}/family` | `FamilyContact` `{id, name:"Rohit (son)", channel:"in_app"}` or 404 |
| `POST /demo/family/notifications` | `{shopper_id, message}` (≤ 280 chars) → `{delivered:true, contact_name}` |
| `GET /demo/family/notifications?shopper_id=` | `[{id, message, created_at}]` |
| `POST /demo/reset` | header `X-Demo-Admin-Key` → clears carts, checkouts, orders (except the seed), notifications |
