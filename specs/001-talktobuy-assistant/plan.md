# Implementation Plan: TalkToBuy Conversational Shopping Assistant (MVP)

**Branch**: `001-talktobuy-assistant` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-talktobuy-assistant/spec.md`

## Summary

Build an embeddable web component, `<talktobuy-assistant>`, that gives a shopping app a live,
Hindi-speaking avatar. The avatar hears, sees and speaks, fills the app's cart through nine
tools, and checks out after one fingerprint approval in the app's own payment step.

There are three runtime parts:

1. A **session server** on Cloud Run. It proxies a `gemini-3.8-live` + Live Avatar session on
   Gemini Enterprise Agent Platform (Vertex AI), holds session state, and runs every tool behind
   provider-neutral ports.
2. Our own **demo store**, a fork of the official UCP Python (FastAPI) sample. It covers catalogue
   search, a checkout session as the cart, a fulfillment extension for delivery slots, and AP2
   mandate verification in test mode.
3. A plain **shop app** that embeds the component and provides the WebAuthn "trusted surface"
   payment step.

Deterministic server code owns everything that has to be exact or safe: unit conversion, totals,
the read-back sentence, warning-sign detection and the tool guards. The model owns conversation
and planning. See [research.md](./research.md) for every decision.

## Technical Context

**Language/Version**: **Python 3.12** for the backend (session server, demo store, catalogue
scripts), managed with `uv`. TypeScript 5.x / ES2022 only for the browser parts (widget, shop
app).

**Primary Dependencies**:

| Part | Dependencies |
|---|---|
| Session server (Python) | FastAPI + Uvicorn (WebSockets), `google-genai` (Live API in Vertex mode; Gemini Flash for translation and safety classification; `gemini-embedding-2`), Pydantic v2, `google-cloud-firestore`, `httpx`, `structlog` |
| Demo store (Python) | Fork of the UCP samples Python FastAPI merchant server, `ucp-sdk`, the AP2 Python SDK (GitHub `main`, v0.2), SQLite via `sqlite3`/SQLModel, `jwcrypto` (ES256 JWS), `rfc8785` (JCS canonicalisation) |
| Catalogue scripts (Python) | `httpx` (Open Food Facts import), `google-genai` (embeddings), `numpy` (vectors) |
| Widget (TypeScript) | Lit 3, the Web Audio API (`AudioWorklet`), Media Source Extensions |
| Shop app (TypeScript) | Vite + React 18, plus the WebAuthn browser API for the payment step; a small Python endpoint in the store issues the test mandate after verifying WebAuthn (`webauthn` package) |

**Cross-language contracts**: [contracts/tools.schema.json](./contracts/tools.schema.json) and
the widget message schemas are the single source of truth. Pydantic models are generated with
`datamodel-code-generator` and TypeScript types with `json-schema-to-typescript`, and a CI check
fails if the generated files drift from the schemas.

**Storage**:

- SQLite in the demo-store container, with the catalogue snapshot baked in.
- Firestore for sessions and usage logs.
- Cloud Storage for product images.
- Secret Manager for signing keys.

No audio, video or transcript is persisted (FR-040).

**Testing**:

- pytest (with `pytest-asyncio`) for unit tests: the units parser, pack selection, tool guards and
  the safety detector.
- Contract tests against [contracts/tools.schema.json](./contracts/tools.schema.json) and the UCP
  SDK models.
- Vitest for the widget's protocol and audio helpers.
- A safety regression suite of at least 20 prompts.
- Playwright for one widget smoke flow using the seeded session.
- Manual rehearsal checklist ([quickstart.md](./quickstart.md)).

**Target Platform**: Cloud Run (`us-central1`, the same region as the Live model) and Firebase
Hosting. Demo client is desktop Chrome with a camera, microphone and fingerprint reader (platform
authenticator).

**Project Type**: Web application. It is a monorepo with an embeddable web component and a demo
host app (TypeScript), and two Python services.

**Performance Goals**:

- Reply starts within 1.5 s of the end of speech.
- Playback stops within 300 ms of an interruption.
- A card appears within 1 s of the assistant mentioning it.
- The holding line plays if a tool runs longer than 2 s.

**Constraints**:

- Browser holds no keys.
- Avatar sessions need context compression and session resumption (an audio+video connection
  lasts about 2 minutes without compression; each connection about 10 minutes).
- Sessions are capped at 10 minutes.
- Test-mode payments only.
- Hindi lines are reviewed by a native speaker.
- Card text is at least 20 px with WCAG AA contrast; tap targets are at least 48×48 px.

**Scale/Scope**:

- One demo shopper and a handful of concurrent sessions.
- A 300–500 item catalogue.
- 7 user stories and 44 functional requirements.
- 4 working days to code freeze for a team of three.

All Technical Context unknowns are resolved in [research.md](./research.md). The remaining
**(unverified)** items there are hands-on spikes scheduled for Day 1, not open design questions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-research | Post-design | Evidence |
|---|---|---|---|---|
| I. Approval before money or guesses | Inferred items need a yes; no autonomous order | PASS | PASS | `add_to_cart.source`; GoalList `confirmed` before add; `confirm_checkout` requires a payment-step mandate ([data-model.md](./data-model.md) Checkout) |
| II. No medical claims; safety stops the sale | Category exclusion at import; listing-only explanations; hard stop on warning signs; 20+ prompt suite | PASS | PASS | R5 include-list + denylist; R8 detector + `safety_hold` tool guards; safety suite in CI |
| III. Scam-resistant trust boundaries | In-app only; no OTP/PIN; approval only in payment step; no media stored; no keys in browser | PASS | PASS | `notify_family` in-app only; server proxy (R1); WebAuthn payment step (R4); FR-040 storage rule; OTP/PIN refusal in prompt + transcript redaction |
| IV. Elder-first accessibility | Captions, text box, interruption, pace, 20 px / 48 px, native Hindi review | PASS | PASS | [widget-protocol.md](./contracts/widget-protocol.md) caption/interrupted/state messages; widget design tokens; quickstart rehearsal step |
| V. Portability through owned interfaces | Vendor SDKs only in adapters; neutral tool schemas and prompts | PASS | PASS | `mvp/contracts/` JSON Schemas + Python `Protocol` ports (`LivePort`, `CommercePort`, `SearchPort`, `ApprovalPort`, `StatePort`); prompts in `mvp/prompts/*.md` |
| VI. Protect the gate | Gate path first; cut order respected | PASS | PASS | Delivery sequence below; P1 stories first; cut order mirrors spec priorities |

No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-talktobuy-assistant/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R12
├── data-model.md        # Phase 1: entities, state machines
├── quickstart.md        # Phase 1: run + rehearsal validation guide
├── contracts/
│   ├── tools.schema.json    # The nine tools (provider-neutral JSON Schema)
│   ├── widget-protocol.md   # Web component ⇄ session server, host-app events
│   └── store-ucp.md         # Demo store UCP subset + fallback
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
mvp/
├── contracts/                       # JSON Schemas: source of truth (tools, product, cart, session, widget msgs)
├── prompts/                         # Provider-neutral system instruction, safety rules, Hindi lines (*.md)
├── pyproject.toml                   # uv workspace for the Python services
├── package.json                     # npm workspaces for the browser parts
├── services/
│   ├── session-server/              # Python 3.12, FastAPI
│   │   ├── pyproject.toml
│   │   ├── src/session_server/
│   │   │   ├── core/                # session orchestration, tool router, guards, pace, safety detector
│   │   │   ├── units/               # "paav kilo" lexicon + pack selection (pure, unit-tested)
│   │   │   ├── ports/               # Protocols: LivePort, CommercePort, SearchPort, ApprovalPort, StatePort, TranslatePort
│   │   │   ├── adapters/            # gemini_live/, ucp/, rest_store/, firestore/, gemini_flash/
│   │   │   ├── models/              # Pydantic models generated from contracts/
│   │   │   └── http/                # WebSocket endpoint, tickets, agent-profile.json
│   │   └── tests/ (unit/, contract/, safety/)
│   └── demo-store/                  # Python 3.12, fork of the UCP samples Python FastAPI server
│       ├── pyproject.toml
│       ├── src/demo_store/ (discovery/, catalog/, checkout/, ap2/, payment_surface/, demo/)
│       ├── data/ (seed_barcodes.json, catalog.json, vectors.npy, orders_seed.json)
│       ├── scripts/ (import_off.py, embed_catalog.py)
│       └── tests/
├── packages/
│   └── assistant-widget/            # TypeScript: <talktobuy-assistant> Lit web component
│       └── src/ (audio/, avatar/, camera/, cards/, captions/, protocol/, types/ ← generated from contracts/)
├── apps/
│   └── shop/                        # TypeScript: Vite + React demo shopping app; embeds widget; WebAuthn payment step; family view
└── infra/                           # Dockerfiles, Cloud Run service YAML, deploy scripts, Firebase config
```

**Structure Decision**: This is a monorepo under the existing `mvp/` folder. The backend is Python
(a `uv` workspace with two services) and the browser parts are TypeScript (npm workspaces). The
JSON Schemas in `mvp/contracts/` sit between the two languages, and types for both sides are
generated from them. The browser part, `assistant-widget`, is separate from the host app
(`apps/shop`) so the "embed us in any app" claim is literally true. Core logic in
`session_server/core` imports only `ports/`; vendor SDKs live only in `adapters/` (Principle V).
`prototype/` is left for the Day 1 Live Avatar spike (Python, from Google's Live Avatar sample
notebook).

## Key Design Decisions

1. **Server owns exactness.** Unit conversion (`session_server/units`), totals (store), and the
   read-back sentence (`start_checkout.readback_hi`) are deterministic. The model is told to say
   the read-back verbatim (FR-018, SC-005).
2. **Cards before speech.** The tool router pushes `cards` and `cart` to the widget before it
   returns the tool result to the model (SC-007).
3. **Safety in three layers**: the prompt, a transcript detector that sets `safety_hold`, and tool
   guards that refuse product and checkout tools while the hold is set (R8). The guard is the
   layer the tests rely on.
4. **Approval is out of band.** `confirm_checkout` emits `payment_request`. The host app's payment
   step performs WebAuthn, and the server forwards the mandate to UCP `/complete`. No voice path
   can complete an order (FR-020).
5. **Media resilience.** Sliding-window compression and session resumption run on every Live
   connection. A `goAway` triggers a transparent reconnect. Low bandwidth triggers a reconnect in
   audio-only with the same handle (R12).
6. **Seeded mode.** `SEARCH_MODE=seeded` returns a fixed result map for the demo script phrases,
   so the demo works without live search (FR-044).

## Delivery Sequence and Team Split

There are three tracks, matching the source document's build plan. The **gate** is due at the
end of Tue 13 Oct.

| Day | Avatar & agent (A) | Store & checkout (B) | App & interface (C) |
|---|---|---|---|
| Fri 9 | **Spike**: Live Avatar session on our project (Python); MP4 chunk playback via MSE; Hindi voice | Fork UCP Python sample; OFF barcode discovery; seed_barcodes.json | Monorepo scaffold (uv + npm); shop app shell; widget skeleton (mic → WS) |
| Mon 12 | Session server: LivePort adapter, tool router, `search_catalog`/`add_to_cart`/`update_cart` | Catalogue import + Hindi names + images; `/catalog/search` hybrid; checkout-session cart | Cards, captions, interruption flush |
| Tue 13 | **Gate**: Hindi voice → `add_to_cart` → card on screen; `units` parser | `start_checkout` + fulfillment slots; seeded usual order | Pace UI, translation toggle, AI label |
| Wed 14 | Goal-to-list flow, camera frames, `get_usual_order` | AP2 merchant_authorization + mandate verify with the AP2 Python SDK (R4) | WebAuthn payment step; read-back panel |
| Thu 15 | Pace logic, quick mode, holding lines, compression/resumption | Hardening, idempotency, reset endpoint | Audio-only fallback + net-quality switch |
| Fri 16 | Safety detector + guards + 20-prompt suite; prompt review | Seeded session mode; recorded backup run | Accessibility pass (20 px / 48 px / AA); family view |
| Sat 17 | Deploy + rehearse (everyone); native-speaker sign-off on all Hindi lines | | |
| Sun 18 | Submit | | |

If a day slips, cut in this order: quick mode (the quick half of US6; the opening pace question and
guided pace are never cut), then problem suggestions (US7), then the
safety scene (US5, which keeps its rules and guards), then the camera reorder (US4). The gate is
never cut.

## Risks Carried From Research

| Risk | Mitigation |
|---|---|
| No Live Avatar access on our GCP project | Day 1 spike; fallback to audio-only `gemini-3.8-live` + illustrated shopkeeper (widget supports both from day one) |
| MSE playback of streamed MP4 chunks unproven | Day 1 spike; fallback to per-turn segment playback |
| AP2 Python SDK is installed from GitHub `main` (v0.2) and may change | Pin a commit hash; simplified compact-JWS mandate fallback (R4) with the same UX |
| Two languages across the team | Shared JSON Schemas with generated Pydantic and TypeScript types; CI drift check |
| OFF data gaps (produce, maida, Hindi names) | Hand-added items and photos; snapshot committed |
| Hindi `languageCode` honoured only on Enterprise | We are on Enterprise; also pinned in the system instruction |
| Avatar pricing unpublished | Per-session usage logging; 10-min cap |

## Complexity Tracking

> No Constitution Check violations, so there is nothing to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
