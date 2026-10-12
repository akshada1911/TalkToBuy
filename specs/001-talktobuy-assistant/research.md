# Research: TalkToBuy Conversational Shopping Assistant (MVP)

**Date**: 2026-10-09 · **Plan**: [plan.md](./plan.md)

Findings were gathered from official Google, UCP, AP2 and Open Food Facts sources on 2026-10-09.
Items marked **(unverified)** could not be confirmed from a primary source and need a hands-on
spike before we depend on them.

## R1. Live conversation and avatar

**Decision**: `gemini-3.8-live` on **Gemini Enterprise Agent Platform (Vertex AI)**, region
`us-central1`, reached from the Python session server through `google-genai`
(`client.aio.live.connect`, `vertexai=True`, service-account credentials). Avatar via `responseModalities: ["VIDEO"]` and
`avatarConfig: { avatarName: "<preset>" }` plus a prebuilt voice in `speechConfig` with
`languageCode: "hi-IN"`. The session server proxies all media; no ephemeral tokens.

**Rationale**:

- Live Avatar (video output) is only on the Enterprise platform; the Gemini API (AI Studio) model
  card lists text and audio output only. Enterprise needs a GCP bearer token, so a server proxy is
  the only realistic option, and it also satisfies "the browser never holds keys" (Principle III).
- Avatar video arrives as base64 **MP4 chunks** in `serverContent.modelTurn.parts[].inlineData`
  over the same WebSocket (24 fps, ≥ 704×1280 portrait). Preset avatars are GA (e.g. Jay, Paul,
  Sam, Ingrid, Kira, Vera, Ben, Kai, Leo, Carmen, Piper); custom avatars need allowlisting, so
  we use a preset.
- Input audio: 16 kHz 16-bit mono PCM, 20–100 ms chunks. Output audio: 24 kHz PCM. Camera frames:
  JPEG ≤ 1 fps, ~768×768. Because 3.8 keeps every video frame in context by default, the widget
  sends camera frames **only while the camera button is held/active** (User Story 4).
- Captions: `inputAudioTranscription: {}` and `outputAudioTranscription: {}`; native-audio models
  return no text, matching FR-009. Enterprise `customVocabulary` (≤ 1,000 terms) is loaded with
  product names, brands and Hindi local names to help transcription.
- Interruptions: `serverContent.interrupted` → server sends `interrupted` to the widget, which
  flushes its audio/video queue (FR-004, < 300 ms).
- Hindi: `hi-IN` is listed for Enterprise with `languageCode`; we also pin Hindi in the system
  instruction. English translation lines are produced by a separate fast text model call on each
  final caption (not by the Live model). FR-009 allows this: English lines are labelled machine
  translations of the transcribed Hindi captions.
- Session limits: audio+video sessions are ~2 min without compression and each connection ~10 min
  (`goAway` ~60 s before close). We enable `contextWindowCompression: { slidingWindow: {} }` and
  `sessionResumption` and reconnect transparently on `goAway`. The product cap is 10 min (FR-043).
- SynthID watermarking is applied to avatar audio and video by default.

**Spike first (Day 1, highest risk)**:

1. Confirm our GCP project can open a `gemini-3.8-live` avatar session at all (open question in
   the source document).
2. Live playback of streamed MP4 chunks in the browser via Media Source Extensions, and whether
   audio is muxed into the MP4 or sent separately as PCM **(unverified)**. Fallback: buffer
   per-turn segments, or audio-only.
3. Real avatar session length with compression enabled **(unverified)**.

**Alternatives considered**: Gemini API + ephemeral tokens, which is lower-latency but has no
avatar; a chained speech model plus a third-party avatar service, which has more hops and harder
lip-sync and interruption (see source document, Portability); audio-only `gemini-3.8-live` with an
illustrated shopkeeper, which is the documented fallback if avatar access fails.

## R2. Tool calling without dead air

**Decision**: Declare the nine tools from [contracts/tools.schema.json](./contracts/tools.schema.json)
as Live API `functionDeclarations`, converted by the adapter. Default to `NON_BLOCKING` (the 3.8
default). Only `start_checkout` is explicitly `BLOCKING`, so the model waits for the real total
before reading it back; it returns in well under a second. `confirm_checkout` stays
**`NON_BLOCKING`**. The call stays open while the shopper uses the payment step, and the model keeps
talking ("कृपया उंगली लगाइए"). The function response is sent only when the payment resolves,
with `scheduling: INTERRUPT` (the server downgrades it to `WHEN_IDLE` if the shopper is speaking).
This matters because a `BLOCKING` call is cancelled when the user speaks, and an older shopper
is likely to talk during the fingerprint step. Other responses use `WHEN_IDLE` for cart updates and
`SILENT` for `show_products`.

**Rationale**: Non-blocking calls let the model keep talking while products load (FR-005). A
blocking call is cancelled if the user speaks. That is acceptable for `start_checkout`, which
returns in under a second and can simply be called again, and it is exactly why
`confirm_checkout`, which waits on the shopper's fingerprint, is non-blocking. Every
response includes `status` and `retryable`, never an empty body, and its `id` matches the call.
The holding line (> 2 s) comes from the system instruction plus a server-side timer that injects a
short client-content hint if a tool has not returned in 2 s.

**Alternatives considered**: All-blocking calls, which create dead air and break C9; client-side
tool execution, which puts store calls in the browser and breaks Principle III.

## R3. Commerce: demo store on UCP

**Decision**: Fork the Python FastAPI merchant server from `Universal-Commerce-Protocol/samples`
into `mvp/services/demo-store` (Python 3.12, SQLite), pinned to UCP spec version
**`2026-08-25`**. This matches Google's UCP + AP2 codelab, which is also Python and uses
`ucp-sdk`. Implement:

- `GET /.well-known/ucp` declaring `dev.ucp.shopping` over `rest`, capabilities
  `dev.ucp.shopping.checkout`, `.catalog.search`, `.catalog.lookup`, `.fulfillment`,
  `dev.ucp.common.payment.ap2_mandate`, one mock payment handler, and a JWK Set.
- `POST /catalog/search`, `POST /catalog/lookup`.
- `POST /checkout-sessions`, `GET|PUT /checkout-sessions/{id}`,
  `POST /checkout-sessions/{id}/complete`, `POST /checkout-sessions/{id}/cancel`.
- Statuses used: `incomplete → ready_for_complete → complete_in_progress → completed`,
  `canceled`. `requires_escalation` is not used.
- Required headers honoured: `UCP-Agent`, `Request-Id`, `Idempotency-Key` (cached replay; 409 on
  reuse with a different body). RFC 9421 request signing is off (sample default).
- Fulfillment extension with delivery slots as `options` (e.g. "6–7 pm").
- Validate payloads with the `ucp-sdk` Python models. The sample's catalogue and AP2 coverage is
  not yet checked; if catalogue endpoints are missing, we add them, as the codelab's mock merchants
  do.

The cart is a UCP checkout session in `incomplete` state; `start_checkout` sets the delivery
option and moves it to `ready_for_complete`. "My usual" and the family contact are non-UCP demo
endpoints on the same service (`GET /demo/shoppers/{id}/last-order`).

**Money**: UCP amounts are integers in **minor units** (INR paise). The store and contracts use
paise; the tool adapter converts to whole rupees for the model and the read-back sentence. This
supersedes the whole-rupee note in an earlier draft of the data model. INR has not been seen in
any UCP sample **(unverified)**, but nothing in the spec restricts currency.

**Fallback**: If UCP slips past Tue 13 Oct, the same service exposes plain REST with the same
shapes and the `CommercePort` adapter switches. The tools don't change.

**Alternatives considered**: A Shopify development store, which the team ruled out; the Python
FastAPI sample, which would mean a second language; MCP transport, which is fine but REST is
simpler to debug.

## R4. One-approval payment (AP2, test mode)

**Decision**: The store signs every checkout response with an ES256 detached-JWS
`ap2.merchant_authorization` over the JCS-canonicalised checkout, using the AP2 Python SDK
(installed from GitHub `main`, v0.2, pinned to a commit), with `jwcrypto` + `rfc8785` for anything
the SDK doesn't cover. The **payment step** in the shopping app is the AP2 "trusted surface". It shows
the order and calls WebAuthn `navigator.credentials.get()` (platform authenticator, i.e.
fingerprint) with the SHA-256 of the merchant-authorised checkout as the challenge. The shop
backend verifies the assertion and issues the checkout mandate (SD-JWT + key binding,
`vct: mandate.checkout.1`) and the payment mandate (`vct: mandate.payment.1`, mock instrument
`com.example.card`) signed with a demo test key. The session server passes both into
`/complete`; the store verifies signature, expiry, its own `merchant_authorization`, and that
totals and lines match.

**Rationale**: This gives exactly one biometric approval in the app's own payment step (FR-020)
and a real mandate check at the store, in test mode. AP2 does not specify WebAuthn binding, so
this is a documented demo stand-in, not a spec-defined flow.

**Simplification allowed if Day 3 slips**: Skip SD-JWT. The shop backend signs a compact JWS
mandate `{checkout_id, checkout_hash, amount, currency, approved_at}` after the WebAuthn check, and
the store verifies that. The approval UX is the same.

**Risks**: The AP2 Python SDK is pre-1.0 and installed from GitHub `main`, so we pin a commit.
The PyPI package named `ap2` is unrelated and must not be installed. WebAuthn assertions are
verified server-side with the `webauthn` Python package. Demo laptops need a platform authenticator; the
fallback is a device PIN prompt, which still sits in the app's payment step and never in voice.

## R5. Catalogue import (Open Food Facts)

**Decision**: Build a hand-picked catalogue of 300–500 items by barcode.

1. Discover candidates with Search-a-licious (`search.openfoodfacts.org/search?q=… countries_tags:"en:india"`).
2. Curate `mvp/services/demo-store/data/seed_barcodes.json`, then run `scripts/import_off.py`
   (`httpx`).
3. Fetch each with `GET /api/v2/product/{code}?fields=code,product_name,brands,quantity,categories_tags,image_front_url`,
   throttled to about 1 every 5 s with backoff on 503. The User-Agent is
   `TalkToBuy/0.1 (<team contact email from env>)`.
4. Normalise `quantity` into `unit_qty` + `unit`, and map `categories_tags` to our categories.
5. Copy images to our Cloud Storage bucket.
6. Commit the snapshot (`catalog.json`). The demo never calls Open Food Facts live.

**Medicine exclusion (FR-031)**: Apply an **include-list** of grocery categories (dairy, flours,
biscuits, baking, beverages, spices, staples, snacks, produce, home), and additionally a denylist
that rejects any item tagged `en:dietary-supplements`, `en:food-supplements`, `en:vitamins`,
`en:protein-powders`, `en:baby-milks`, `en:infant-formulas`, or `en:non-food-products` (unless it
is a hand-added non-food demo item such as the cake tin). This deliberately drops items like
Bournvita and Chyawanprash, which carry health positioning or are licensed as Ayurvedic
medicines. Rejected IDs are logged for audit.

**Hand-added data**: Hindi `local_name` and `synonyms` for every item, drafted by a model and
checked by a team member. Fresh produce such as tomatoes 250 g, which is missing from Open Food
Facts, uses our own photos. The 7-inch cake tin and the demo biscuit packet use multi-angle photos.
Milkmaid has exactly one India record, 8901058903959 (380 g).

**Licence**: Credit in the app footer and on product detail: "Product data © Open Food Facts
contributors, ODbL. Images CC BY-SA. openfoodfacts.org". Demo prices are labelled "demo price"
(FR-042).

**Alternatives considered**: Bulk filter pulls, which are messy and rate-limited (v2 search
returned 503 about half the time); live API calls during the demo, which are unreliable.

## R6. Product search

**Decision**: Hybrid search in memory inside the store's `/catalog/search`:

- Embed each product once with `gemini-embedding-2` at 768 dimensions. The document text is
  `"{name} | {brand} | {size} | {category} | {local_name} | {synonyms}"`. Vectors are stored with
  the snapshot.
- At query time, embed the query, then score as `0.6·cosine + 0.3·exact name/Hindi/synonym match
  + 0.1·brand match`.
- Ask the shopper to choose if the top two results are within 0.05.

Unit and quantity parsing ("paav kilo") happens in the session server before search, not in
search itself.

**Rationale**: 500 × 768 floats is about 1.5 MB, and a brute-force scan takes under 1 ms. Cost is
negligible. Vertex AI Search for commerce typically takes weeks to integrate, so it is not
realistic in a day.

**Risk**: Availability of `gemini-embedding-2` on Vertex is unverified; the fallback is
`gemini-embedding-001` with `taskType` set.

## R7. Local units and quantities (FR-012)

**Decision**: Deterministic parser `session_server/units` (pure Python) with a lexicon. The model passes the
shopper's phrase. The `add_to_cart` result echoes the interpreted pack so the model can say it.
Starting lexicon:

| Phrase | Base amount |
|---|---|
| paav / पाव kilo | 250 g |
| aadha / आधा kilo | 500 g |
| sava kilo | 1,250 g |
| dedh kilo | 1,500 g |
| dhai kilo | 2,500 g |
| aadha litre | 500 ml |
| do litre | 2,000 ml |
| darjan | 12 pieces |
| packet | 1 piece |

Pack selection uses the fewest packs that are ≥ the amount, and the smallest pack when the amount
is below any pack (FR-025).

**Rationale**: Exactness is a demo pass criterion ("250 g for paav kilo"), so it must not depend
on model arithmetic. The parser is unit-tested.

## R8. Safety detection (FR-032–FR-035)

**Decision**: Defence in depth, all on the session server.

1. The system instruction holds the safety rules.
2. A server-side **warning-sign detector** runs on every final input transcript and typed text:
   - first a Hindi + English + Hinglish keyword and phrase list (गिर गया, सुन्न, numb, fever, बुखार, …);
   - then, only if a keyword hits or a health word appears, a fast Gemini Flash classification.

   On a positive result it sets `session.safety_hold = true` and sends the model a client-content
   note ("Warning sign detected: show no products; suggest a doctor; offer to tell family").
3. Tool guards refuse `show_products`, `add_to_cart` and `start_checkout` while `safety_hold` is
   set. This makes "no products shown" true even if the model errs.
4. A claims check: before `show_products` results go to the model, each product's explanation
   context is limited to `listing.description` and `listing.usage`.
5. A regression suite of at least 20 prompts in `mvp/services/session-server/test/safety/` runs in
   CI and before every demo build.

`safety_hold` clears only when the shopper explicitly moves on to a non-health request, after the
assistant has given the doctor suggestion.

**Rationale**: A prompt alone is not a guarantee, and Principle II is non-negotiable. A
deterministic tool guard makes SC-006 testable.

## R9. Health-detail consent (FR-038)

**Decision**: The MVP stores **no** health details. With nothing persisted, consent is trivially
satisfied. `health_consent` stays in the session model for forward compatibility, and the
assistant never claims to remember health details.

**Rationale**: This is the simplest option that complies. Problem-based suggestions are P5 and
the first to be cut.

## R10. English translation lines

**Decision**: Each final Hindi caption, from either side, is translated to English by a fast text
model call (Gemini Flash) on the session server and sent as `text_en` on the same caption
`turn_id`. This happens asynchronously, so captions show Hindi first and English follows within
about 1 s. Translations are display-only and never fed back to the Live model.

**Alternatives considered**: Cloud Translation API, which adds another service with no quality
gain at this scale.

## R11. Hosting, state and cost

**Decision**:

- **Cloud Run**:
  - `session-server` uses WebSockets, a 3,600 s request timeout, session affinity and
    `min-instances=1` for the demo.
  - `demo-store` uses SQLite on the container. The catalogue snapshot is baked in and orders are
    reset on deploy.
- **Firebase Hosting** for the shop app and widget bundle.
- **Firestore** for session state and usage logs.
- **Cloud Storage** for product images.
- **Secret Manager** for store signing keys and the demo mandate key.
- **Service account** with `roles/aiplatform.user` for the session server.

Usage per session (audio-in seconds, audio-out seconds, video seconds, tokens from
`usageMetadata`, estimated USD) is written at session end (FR-043). A hard 10-minute timer gives a
spoken warning at 9 minutes.

**Pricing note**: Avatar pricing is not published **(unverified)**. Audio is about
$0.005/min in and $0.018/min out per Google's developer post. We log tokens and reconcile against
billing after the first day.

## R12. Low bandwidth and the audio-only fallback (FR-006)

**Decision**: The widget reports `net_quality` every 5 s from the Network Information API (where
available) plus WebSocket RTT and buffer underruns. The server switches to audio-only by
reconnecting the Live session with `responseModalities: ["AUDIO"]` and a session-resumption
handle, so the conversation continues. The widget shows the illustrated shopkeeper. Manual toggle
is always available.

**Rationale**: Changing modality needs a new connection; resumption keeps context.
