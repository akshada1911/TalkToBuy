# Data Model: TalkToBuy Conversational Shopping Assistant (MVP)

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

All shapes are provider-neutral JSON Schemas in `mvp/contracts/` (see [contracts/](./contracts/)).
Pydantic models (Python services) and TypeScript types (widget, shop) are generated from them. **Money**: the store and UCP use integer
minor units (paise, `price_minor: 6500`); the tool adapter converts to whole rupees
(`price: 65`) for the model, matching the source document's product record ([research.md](./research.md)
R3). Totals are computed by the store, never by the model.

## Entities

### Product (owned by the store)

| Field | Type | Rules |
|---|---|---|
| `id` | string | `p-NNNN`, unique, stable across imports |
| `name` | string | English display name, non-empty |
| `local_name` | string | Hindi (Devanagari) name; required for every demo item |
| `brand` | string \| null | Used for exact-match search boost |
| `size` | string | Human label, e.g. `"1 L"`, `"250 g"`, `"7 inch"` |
| `unit_qty` | number | Pack amount in base unit (e.g. `1000`) |
| `unit` | `"g" \| "ml" \| "piece"` | Base unit for unit conversion (FR-012) |
| `price_minor` | integer | INR paise, > 0; exposed to the model as whole-rupee `price`; labelled "demo price" in UI (FR-042) |
| `currency` | `"INR"` | Fixed for MVP |
| `image` | URL | Open Food Facts image or our own photo |
| `image_credit` | string | Attribution line for CC BY-SA images |
| `category` | string | Our normalised category, e.g. `dairy`, `baking`, `produce`, `home` |
| `source_categories` | string[] | Raw source tags, kept for audit of medicine exclusion |
| `listing.description` | string | Only allowed basis for explanations (FR-030) |
| `listing.usage` | string \| null | Only allowed basis for explanations (FR-030) |
| `synonyms` | string[] | Extra spoken names (Hinglish, regional), e.g. `"doodh"` |
| `in_stock` | boolean | Out-of-stock items are returned with `in_stock: false` |

Validation:

- Import MUST keep only products in the grocery category include-list and MUST reject any product
  whose `source_categories` intersect the medicine/supplement denylist ([research.md](./research.md)
  R5); rejected IDs are logged (FR-031).
- `local_name`, `listing.description` and `image` are required for every item the demo touches.

### Shopper (seeded for the demo)

| Field | Type | Rules |
|---|---|---|
| `id` | string | `u-ghanshyam` for the demo persona |
| `display_name` | string | `"Ghanshyam ji"` |
| `language` | `"hi"` | MVP language |
| `address_form` | `"respectful_male" \| "respectful_female" \| "neutral"` | Drives Hindi gendered forms (FR-008); set at onboarding, never inferred |
| `family_contact` | FamilyContact \| null | Seeded |
| `health_notes` | string[] | Written only when `Session.health_consent = true` (FR-038) |

No age field exists anywhere in the model (FR-039).

### FamilyContact

| Field | Type | Rules |
|---|---|---|
| `id` | string | |
| `name` | string | e.g. `"Rohit (son)"` |
| `channel` | `"in_app"` | Only value allowed in MVP (FR-036); shown on the family view |

### Order and UsualOrder (owned by the store)

| Field | Type | Rules |
|---|---|---|
| `order_id` | string | Returned by checkout completion |
| `shopper_id` | string | |
| `lines` | CartLine[] | Snapshot at completion |
| `total` | integer | INR, computed by store |
| `delivery_slot` | DeliverySlot | |
| `placed_at` | ISO datetime | |
| `mode` | `"test"` | Always test in MVP |

`get_usual_order()` returns the shopper's most recent order (one seeded order for the demo).

### CartLine and Cart (owned by the store)

| Field | Type | Rules |
|---|---|---|
| `product_id` | string | Must exist in catalogue |
| `qty` | integer | ≥ 1; `qty = 0` on update means remove |
| `line_total` | integer | Store-computed |
| `source` | `"named" \| "camera" \| "usual" \| "goal"` | How it was added; non-`named` sources require prior approval (FR-015) |

`Cart = { lines: CartLine[], item_count: number, total: integer, currency: "INR" }`.
`item_count` = number of distinct products (spec Assumptions).

### DeliverySlot

| Field | Type | Rules |
|---|---|---|
| `id` | string | e.g. `slot-1800` |
| `label_hi` / `label_en` | string | `"शाम 6 से 7 बजे"` / `"6–7 pm"` |
| `start` / `end` | ISO datetime | |

### Checkout (owned by the store)

| Field | Type | Rules |
|---|---|---|
| `checkout_id` | string | |
| `status` | enum | see state machine |
| `lines`, `item_count`, `total` | | Frozen snapshot of the cart at start |
| `delivery_slot` | DeliverySlot | |
| `approval` | `{ mandate_id, approved_at } \| null` | Set only by the payment step |

State machine (UCP checkout statuses, [research.md](./research.md) R3):

```text
              ┌──(cart edited / shopper says no / payment declined or timed out)──┐
              ▼                                                                  │
incomplete ──(start_checkout: slot chosen, totals valid)──▶ ready_for_complete ──┘
                                                                │
                                              (complete with valid AP2 mandate)
                                                                ▼
                                    complete_in_progress ──▶ completed

any state ──(session ended without an order, or 6 h expiry)──▶ canceled
```

- The cart is a checkout session in `incomplete`. A cart edit, a "no" to the read-back, or a
  declined or timed-out payment returns it to `incomplete` with every line kept. It is never
  cancelled while the shopper is still shopping. `confirm_checkout` MUST fail unless the status
  is `ready_for_complete` **and** a valid mandate from the payment step is attached (FR-020,
  Principle III). A spoken "yes" alone never moves the state to `completed`.
- Any cart edit while the session is `ready_for_complete` returns it to `incomplete`, so a new
  `start_checkout` and read-back are required and the read-back always matches (FR-018).

### GoalList (session-scoped, owned by the session server)

| Field | Type | Rules |
|---|---|---|
| `goal_id` | string | |
| `goal_text` | string | e.g. "small eggless chocolate cake" |
| `questions_asked` | integer | ≤ 2 (FR-023) |
| `items` | GoalItem[] | |
| `status` | `"proposed" \| "confirmed" \| "discarded"` | Items are added to cart only on `confirmed` |

`GoalItem = { need: string, product_id: string | null, qty: number, struck: boolean,
struck_reason: "on_hand" | "in_cart" | null }`. When the needed amount is below the smallest pack,
`product_id` is the smallest pack (FR-025).

### Session (owned by the session server, Firestore)

Matches the source document's session state, extended with fields the plan needs:

| Field | Type | Rules |
|---|---|---|
| `session_id` | string | |
| `shopper_id` | string | |
| `pace` | `"guided" \| "quick"` | Default `guided` until the opening question is answered (FR-027) |
| `language` | `"hi"` | |
| `show_translation` | boolean | Default `true` (FR-003) |
| `cart_ref` | string | Store cart ID |
| `on_hand` | string[] | Items the shopper said they already have |
| `health_consent` | boolean | Default `false` (FR-038) |
| `safety_hold` | boolean | `true` after a warning sign; while true, `show_products` and `add_to_cart` are refused (FR-032) |
| `checkout_id` | string \| null | Same ID as `cart_ref` (the cart is the checkout session) |
| `checkout_ready` | boolean | `true` only between a successful `start_checkout` and the next cart edit or payment outcome |
| `pending_confirmation` | `{kind: "usual" \| "camera" \| "goal", product_ids: string[], armed_at, confirmed: boolean}` \| null | Armed when the server proposes inferred items; set to confirmed by the next affirmative shopper input; cleared after one add or 60 s. Required for any non-`named` add (FR-015) |
| `pending_goal` | GoalList \| null | |
| `correction_count` | integer | Two corrections or a repeat request → switch to guided (FR-029) |
| `media_mode` | `"avatar" \| "audio_only"` | (FR-006) |
| `started_at`, `ended_at` | ISO datetime | Session capped at 10 min (FR-043) |
| `usage` | `{ audio_in_s, audio_out_s, video_in_s, tokens_in, tokens_out, est_cost_usd }` | Logged per session (FR-043) |

No audio, video or transcript is persisted after the session ends (FR-040); only `usage`, cart,
order and consented health notes survive.

## Relationships

```text
Shopper 1─* Session      Session 1─1 Cart (store)      Session 0..1 Checkout (store)
Shopper 1─* Order        Order *─* Product (via lines) Session 0..1 GoalList
Shopper 0..1 FamilyContact
```
