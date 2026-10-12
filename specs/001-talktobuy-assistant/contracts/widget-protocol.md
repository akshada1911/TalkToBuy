# Contract: Assistant Widget ⇄ Session Server

**Transport**: one WebSocket per session, `wss://<session-server>/v1/session`, opened by the
`<talktobuy-assistant>` web component. Binary frames carry media; text frames carry JSON
messages with a `type` field. The browser never receives model or store credentials
(Principle III); it authenticates with a short-lived session ticket. In production the host app's
backend gets it server-to-server (`POST /v1/tickets`, with a key). The demo shop uses the keyless,
origin-restricted, rate-limited `POST /v1/demo-ticket`, which only issues tickets for the demo
shopper, so no key is ever bundled into a frontend.

Avatar video arrives from the model as MP4 chunks over the Live session ([research.md](../research.md)
R1). The server relays them unchanged as binary `0x12` frames, and the widget plays them through
Media Source Extensions. If the Day 1 spike shows that audio is not muxed into the MP4, the server
also sends `0x11` PCM and the widget syncs the two.

## Embedding API (host app ⇄ web component)

```html
<talktobuy-assistant
  ticket="…"                 <!-- from host backend -->
  language="hi"
  show-translation="true"
  media-mode="avatar">       <!-- or audio_only -->
</talktobuy-assistant>
```

DOM events the component emits to the host app (the host keeps its own cart UI and payment step):

| Event | `detail` | Host responsibility |
|---|---|---|
| `ttb:cart-changed` | `{ cart: UiCart }` | Optional: refresh host cart badge |
| `ttb:payment-requested` | `{ checkout_id, total, currency, item_count, delivery }` | Open the app's **own** payment step (fingerprint); then call `component.resolvePayment(result)` |
| `ttb:order-placed` | `{ order_id, delivery }` | Optional: navigate to order page |
| `ttb:session-ended` | `{ reason }` | Optional |

`resolvePayment({ checkout_id, approved: boolean, mandate?: { checkout_mandate, payment_mandate } })` — `mandate` holds the signed
test-mode approval produced by the payment step (research R4). The server verifies it before
completing (FR-020).

## Client → server messages

| Binary/JSON | Payload | Notes |
|---|---|---|
| binary `0x01` + PCM | 16 kHz 16-bit LE mono PCM microphone audio, 20–100 ms chunks | R1 |
| binary `0x02` + JPEG | camera frame, ~768×768 | ≤ 1 fps, only while the "show item" camera is active (every frame enters model context) |
| `{"type":"text","text":"…"}` | typed input | FR-003 alternative to speech |
| `{"type":"set_media_mode","mode":"avatar"\|"audio_only"}` | | Manual switch (FR-006) |
| `{"type":"set_translation","on":bool}` | | FR-003 |
| `{"type":"payment_result","checkout_id","approved","mandate?"}` | | From `resolvePayment` |
| `{"type":"net_quality","downlink_kbps":n,"rtt_ms":n}` | | Every 5 s; server may force audio-only |
| `{"type":"end"}` | | Shopper closed the assistant |

## Server → client messages

| Binary/JSON | Payload | Drives |
|---|---|---|
| binary `0x11` + PCM | assistant audio, 24 kHz 16-bit mono | Playback (audio-only mode, or when avatar audio is not muxed) |
| binary `0x12` + MP4 chunk | avatar video, 24 fps | Avatar `<video>` via Media Source Extensions |
| `{"type":"caption","who":"shopper"\|"assistant","text_hi","text_en?","final":bool,"turn_id"}` | | Captions (FR-003, FR-009) |
| `{"type":"interrupted","turn_id"}` | | Client flushes queued audio within 300 ms (FR-004) |
| `{"type":"cards","products":[Product],"mode":"suggest"\|"added"}` | | Product cards (FR-013) |
| `{"type":"goal_list","goal_text","items":[GoalItem]}` | | Goal list with strike-through (FR-026) |
| `{"type":"cart","cart":Cart}` | | Cards-on-screen = cart (FR-013) |
| `{"type":"readback","checkout_id","item_count","total","delivery"}` | | Read-back panel (FR-018) |
| `{"type":"payment_request", …}` | | Component re-emits as `ttb:payment-requested` |
| `{"type":"order","order_id","delivery"}` | | Confirmation (FR-021) |
| `{"type":"family_notified","contact_name"}` | | Confirmation (FR-033) |
| `{"type":"state","pace","media_mode","safety_hold","remaining_s"}` | | Pace indicator, timer, AI label always shown (FR-010) |
| `{"type":"working","on","label_hi?","label_en?"}` | | Visual "working…" while a tool runs (FR-005) |
| `{"type":"error","code","message_hi","message_en"}` | | Friendly errors |

Captions: every `caption` message carries the **full text of that turn so far** in `text_hi` (replace, don't append); `text_en` is a labelled machine translation that may arrive later on the same `turn_id`. Close codes 4401 (bad ticket), 4429 (busy) and 4503 (not configured) mean "don't reconnect".

Ordering rule: `cart` and `cards` messages are sent **before** the tool result is returned to the
model, so a card is on screen before the assistant finishes mentioning it (SC-007, < 1 s).
