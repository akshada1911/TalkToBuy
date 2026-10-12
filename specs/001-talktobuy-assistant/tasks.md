---

description: "Task list for TalkToBuy Conversational Shopping Assistant (MVP)"
---

# Tasks: TalkToBuy Conversational Shopping Assistant (MVP)

**Input**: Design documents from `specs/001-talktobuy-assistant/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: These are included only where the constitution requires them: contract tests for the tool
contracts, unit tests for exactness logic (units, packs, guards, checkout), and the safety
regression suite of at least 20 prompts (Constitution II). The other stories are validated with
the rehearsal script in [quickstart.md](./quickstart.md).

**Organization**: Tasks are grouped by user story. Story priorities follow the spec's cut order.
US1 and US2 are P1 and are never cut. Cut order if a day slips: quick mode (the cuttable part of US6;
the opening pace question and guided pace stay) → US7 → US5 scene (its rules and guards stay) → US4.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: User story from spec.md (US1–US7)
- **Track** hints from plan.md: **A** = avatar & agent, **B** = store & checkout, **C** = app & interface

## Path Conventions

All paths are relative to the repository root:

| Path | What it is |
|---|---|
| `mvp/services/session-server/src/session_server/` | Python session server (`ss/` below) |
| `mvp/services/demo-store/src/demo_store/` | Python demo store (`ds/` below) |
| `mvp/packages/assistant-widget/src/` | TypeScript web component (`aw/` below) |
| `mvp/apps/shop/src/` | TypeScript shop app (`shop/` below) |

The abbreviations are for reading only; tasks always give the full path.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Monorepo initialisation and the Day 1 risk spike.

- [X] T001 Create the monorepo directory tree exactly as in plan.md "Source Code": `mvp/contracts/`, `mvp/prompts/`, `mvp/services/session-server/`, `mvp/services/demo-store/`, `mvp/packages/assistant-widget/`, `mvp/apps/shop/`, `mvp/infra/`. Keep the existing `mvp/README.md` and add a short layout section to it.
- [X] T002 Create the uv workspace in `mvp/pyproject.toml`:
  - `requires-python = ">=3.12,<3.13"`, with members `services/session-server` and `services/demo-store`;
  - shared dev dependencies: `ruff`, `pytest`, `pytest-asyncio`, `datamodel-code-generator`;
  - ruff config and pytest markers `safety` and `live`.
- [X] T003 [P] Create `mvp/services/session-server/pyproject.toml` (package `session_server`, src layout) with dependencies `fastapi`, `uvicorn[standard]`, `google-genai`, `pydantic>=2`, `pydantic-settings`, `google-cloud-firestore`, `httpx`, `structlog`, `numpy`. Add an empty `src/session_server/__init__.py` and `main.py` exposing a FastAPI `app` with `GET /healthz`.
- [X] T004 [P] Fork the Python FastAPI merchant server from `github.com/Universal-Commerce-Protocol/samples` into `mvp/services/demo-store/`:
  - record the upstream commit hash and its licence in `mvp/services/demo-store/UPSTREAM.md`;
  - restructure it into `src/demo_store/` with `main.py` exposing `app`;
  - create `mvp/services/demo-store/pyproject.toml` with dependencies `fastapi`, `uvicorn[standard]`, `ucp-sdk`, `sqlmodel`, `jwcrypto`, `rfc8785`, `webauthn`, `httpx`, `google-genai`, `numpy`;
  - add the AP2 SDK from `git+https://github.com/google-agentic-commerce/AP2` pinned to a commit hash. Do NOT install the unrelated PyPI package `ap2`.
- [X] T005 [P] Create npm workspaces in `mvp/package.json` (members `packages/assistant-widget`, `apps/shop`). Scaffold `mvp/packages/assistant-widget/` as a Vite library build with Lit 3 and TypeScript 5 (entry `src/index.ts`, output a single ES module `talktobuy-assistant.js`). Scaffold `mvp/apps/shop/` as Vite + React 18 + TypeScript. Add Vitest to the widget and Playwright to the shop.
- [X] T006 [P] Create `mvp/.env.example` with every variable from quickstart.md: `GCP_PROJECT`, `GCP_LOCATION=us-central1`, `AVATAR_NAME`, `VOICE_NAME`, `STORE_BASE_URL`, `SESSION_SERVER_URL`, `OFF_CONTACT_EMAIL`, `SEARCH_MODE=live|seeded`, `COMMERCE_ADAPTER=ucp|rest`, `MEDIA_MODE_DEFAULT=avatar|audio_only`, `DEMO_ADMIN_KEY`, `IMAGE_BUCKET`, `FIRESTORE_DATABASE`, `MAX_CONCURRENT_SESSIONS=3`, `DAILY_SESSION_QUOTA=100`, `DEMO_TICKETS_ENABLED=true`. Write a one-line comment for each.
- [X] T007 [P] Create task runners for macOS/Linux and Windows. Both must expose the same targets: `dev`, `test`, `test-safety`, `gen-types`, `check-generated`, `lint`.
  - `mvp/Makefile`
  - `mvp/scripts/tasks.ps1`, a PowerShell equivalent so Windows teammates don't need `make`
- [X] T008 [P] Extend the repo-root `.gitignore` with `mvp/.env`, `.venv/`, `node_modules/`, `mvp/**/dist/`, `mvp/services/demo-store/*.db`, `__pycache__/`. Do NOT ignore `mvp/services/demo-store/data/catalog.json` or `vectors.npy`; they are committed snapshots.
- [X] T009 [P] Track A: Day 1 spike in `prototype/live-avatar-spike/`, adapted from Google's `intro_live_avatar.ipynb`:
  - `spike.py` (google-genai, `vertexai=True`) opens a `gemini-3.8-live` session with `response_modalities=["VIDEO"]`, a preset `avatar_name`, `language_code="hi-IN"`, `context_window_compression` and `session_resumption`;
  - it relays MP4 chunks over a local WebSocket to `player.html`, which plays them with Media Source Extensions;
  - record in `prototype/live-avatar-spike/FINDINGS.md`: (1) access works yes/no, (2) whether audio is muxed into the MP4, (3) MSE playback quality, (4) Hindi quality, (5) whether the session survives more than 2 minutes, (6) observed latency.

  If access fails, set `MEDIA_MODE_DEFAULT=audio_only` in `.env.example` and note it in `WORKLOG.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contracts, ports, the store skeleton, the session-server core and the widget skeleton that every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Contracts and generated types

- [X] T010 Copy `specs/001-talktobuy-assistant/contracts/tools.schema.json` to `mvp/contracts/tools.schema.json`. From now on, `mvp/contracts/` is the source of truth; the spec copy is reference only.
- [X] T011 [P] Write `mvp/contracts/domain.schema.json` with `$defs` for the entities in data-model.md: `Product`, `CartLine`, `Cart`, `DeliverySlot`, `GoalItem`, `GoalList`, `Session`, `FamilyContact`, `Order`. Encode these constraints verbatim:

  | Field | Constraint |
  |---|---|
  | `Product.id` | `p-NNNN` (pattern `^p-\d{4}$`) |
  | `Product.unit` | `"g" \| "ml" \| "piece"` |
  | `Product.price_minor` | INR paise, > 0 |
  | `Product.currency` | `"INR"` |
  | `CartLine.qty` | ≥ 1 |
  | `CartLine.source` | `"named" \| "camera" \| "usual" \| "goal"` |
  | `GoalList.questions_asked` | ≤ 2 |
  | `GoalList.status` | `"proposed" \| "confirmed" \| "discarded"` |
  | `GoalItem.struck_reason` | `"on_hand" \| "in_cart" \| null` |
  | `Session.pace` | `"guided" \| "quick"`, default `guided` |
  | `Session.media_mode` | `"avatar" \| "audio_only"` |
  | `Session.health_consent` | default `false` |
  | `Session.safety_hold` | default `false` |
  | `FamilyContact.channel` | `"in_app"` |
  | `Order.mode` | `"test"` |

  No age field may exist anywhere.
- [X] T012 [P] Write `mvp/contracts/widget-messages.schema.json` covering every client→server and server→client JSON message in `specs/001-talktobuy-assistant/contracts/widget-protocol.md`, as a `oneOf` discriminated on `type`. Document the binary frame prefixes `0x01` (mic PCM 16 kHz), `0x02` (JPEG), `0x11` (assistant PCM 24 kHz) and `0x12` (avatar MP4) in the schema description.
- [X] T013 Implement `gen-types` and `check-generated` in `mvp/Makefile` and `mvp/scripts/tasks.ps1`:
  - `datamodel-code-generator` writes `mvp/services/session-server/src/session_server/models/generated.py` and `mvp/services/demo-store/src/demo_store/models/generated.py` (Pydantic v2);
  - `json-schema-to-typescript` writes `mvp/packages/assistant-widget/src/types/generated.ts`;
  - `check-generated` regenerates into a temp directory and fails on any diff.

  Run it once and commit the outputs.

### Demo store foundation (Track B)

- [X] T014 [P] Track B: Write `mvp/services/demo-store/scripts/discover_off.py`. It queries Search-a-licious (`https://search.openfoodfacts.org/search?q=<term> countries_tags:"en:india"`) for each term in a staples list (milk, atta, biscuits, maida, cocoa, butter, condensed milk, baking powder, sugar, baking soda, rice, dal, oil, tea, spices, snacks, …) and writes candidate barcodes with names to `mvp/services/demo-store/data/candidates.json`. The User-Agent is `TalkToBuy/0.1 (<OFF_CONTACT_EMAIL>)`.
- [X] T015 Track B: Curate the catalogue in two stages so the gate never waits on the full import:
  - **Stage 1 (needed for the gate, by Mon 12)**: `mvp/services/demo-store/data/seed_barcodes.json` starts with only the ~15 demo items plus 2–3 near-alternatives each (for ambiguity and out-of-stock paths), and T016–T019 run on that set first.
  - **Stage 2 (by Wed 14, in parallel with US1/US2, never blocking them)**: extend the same file to 300–500 barcodes from `candidates.json`, then re-run T016–T019.

  Stage 1 must include every demo item from spec.md: toned milk 1 L, a 5 kg chakki atta, the exact physical glucose biscuit packet, maida, cocoa powder, butter, condensed milk (Milkmaid `8901058903959`), baking powder, sugar and baking soda.
- [X] T016 Track B: Write `mvp/services/demo-store/scripts/import_off.py`. For each barcode in `seed_barcodes.json` it does the following.
  - **Fetch**: `GET https://world.openfoodfacts.org/api/v2/product/{code}?fields=code,product_name,brands,quantity,categories_tags,image_front_url`, throttled to 1 request per 5 s with exponential backoff on HTTP 503 (an HTML body). User-Agent from `OFF_CONTACT_EMAIL`.
  - **Normalise**: parse `quantity` into `unit_qty` + `unit` (`g`, `ml`, `piece`) and map `categories_tags` to our categories.
  - **Include-list**: keep only `dairy`, `flours`, `biscuits`, `baking`, `beverages`, `spices`, `staples`, `snacks`, `produce`, `home`.
  - **Denylist**: reject anything tagged `en:dietary-supplements`, `en:food-supplements`, `en:vitamins`, `en:protein-powders`, `en:baby-milks`, `en:infant-formulas` or `en:non-food-products`, and append rejects with their reason to `data/import_rejects.json` (FR-031).
  - **Merge**: apply `data/overrides.json` (T017).
  - **Validate and write**: write `data/catalog.json` validated against the generated `Product` model. It must fail if any demo item lacks `local_name`, `listing.description` or `image`.
- [ ] T017 [P] Track B: Create `mvp/services/demo-store/data/overrides.json` keyed by barcode or hand-added id:
  - **Hindi data**: a Hindi `local_name` (Devanagari) and `synonyms` (Hinglish, e.g. "doodh", "aata") for every item.
  - **Listings**: `listing.description` and `listing.usage` written from the pack facts only, with no health claims.
  - **Demo prices**: `price_minor`, chosen so the scripted cart (2× toned milk 1 L, tomatoes 250 g, usual atta, 1 biscuit pack, maida, cocoa powder, butter, condensed milk, baking powder, 7-inch cake tin = 10 distinct products) totals exactly ₹1,016.
  - **Hand-added items**: tomatoes 250 g (category `produce`, `unit_qty: 250`, `unit: "g"`), the 7-inch cake tin (category `home`, `unit: "piece"`), and any missing staples, each with our own photo path.
  - **Credits**: `image_credit` on every item.

  A team member reviews every Hindi string and records the sign-off in `WORKLOG.md`.
- [ ] T018 [P] Track B: Write `mvp/services/demo-store/scripts/upload_images.py`. It copies every product image, including our photos in `data/images/` and multi-angle photos of the demo biscuit packet, to the `IMAGE_BUCKET` Cloud Storage bucket, then rewrites `image` URLs in `catalog.json`. Keep `image_credit` (CC BY-SA still applies).
- [X] T019 Track B: Run T016 and T018, and commit `mvp/services/demo-store/data/catalog.json` and `data/import_rejects.json`. After stage 1, confirm in `WORKLOG.md` that every demo item is present with Hindi name, listing and image. After stage 2, confirm the item count (300–500) and that zero medicine or supplement items remain. Only stage 1 blocks the Phase 2 checkpoint.
- [X] T020 [P] Track B: Implement catalogue storage in `mvp/services/demo-store/src/demo_store/catalog/store.py`. It loads `data/catalog.json` into SQLite (SQLModel table `Product` mirroring domain.schema.json) at startup, provides `get(id)`, `lookup(ids)` and `all()`, and exposes `price` (whole rupees) alongside `price_minor` only at the adapter boundary.
- [X] T021 [P] Track B: Implement `GET /.well-known/ucp` in `mvp/services/demo-store/src/demo_store/discovery/manifest.py`:
  - `ucp.version` is `"2026-08-25"`;
  - `ucp.services["dev.ucp.shopping"]` is `[{transport:"rest", endpoint:"<base>/ucp/v1"}]`;
  - capabilities are `dev.ucp.shopping.checkout`, `dev.ucp.shopping.catalog.search`, `dev.ucp.shopping.catalog.lookup`, `dev.ucp.shopping.fulfillment` and `dev.ucp.common.payment.ap2_mandate`;
  - the mock payment handler is `com.example.card`;
  - `keys` is the ES256 JWK Set from a key loaded from Secret Manager, or from a local PEM in dev, via `mvp/services/demo-store/src/demo_store/ap2/keys.py`.
- [X] T022 [P] Track B: Implement UCP request middleware in `mvp/services/demo-store/src/demo_store/http/middleware.py`:
  - require `UCP-Agent` and `Request-Id`;
  - require `Idempotency-Key` on POST/PUT;
  - cache responses by key and replay them;
  - return 409 when a key is reused with a different body.
- [X] T023 [P] Track B: Implement demo endpoints in `mvp/services/demo-store/src/demo_store/demo/routes.py`, with seed data in `mvp/services/demo-store/data/orders_seed.json`:
  - `GET /demo/shoppers/{id}/last-order` returns the seeded order for `u-ghanshyam`, containing the usual atta;
  - `GET /demo/shoppers/{id}/family` returns `{id, name:"Rohit (son)", channel:"in_app"}`;
  - `GET /demo/shoppers/{id}` returns the shopper profile `{id:"u-ghanshyam", display_name:"Ghanshyam ji", language:"hi", address_form:"respectful_male"}`. `address_form` is `"respectful_male" | "respectful_female" | "neutral"`, seeded and never inferred (FR-008); there is no age field;
  - `POST /demo/reset`, guarded by `DEMO_ADMIN_KEY`, clears carts, checkouts and orders.

### Session server foundation (Track A)

- [X] T024 Track A: Define the ports as Python `typing.Protocol` classes in `mvp/services/session-server/src/session_server/ports/`. Core code may import only these, never vendor SDKs (Principle V).
  - `live.py` (`LivePort`: connect, send_audio, send_video, send_text, send_tool_response, close, plus an async iterator of neutral events `AudioOut`, `VideoChunk`, `InputTranscript`, `OutputTranscript`, `ToolCall`, `Interrupted`, `GoAway`, `Usage`, `TurnComplete`)
  - `commerce.py` (`CommercePort`)
  - `state.py` (`StatePort`)
  - `translate.py` (`TranslatePort`)
  - `classifier.py` (`ClassifierPort`)
- [X] T025 [P] Track A: Implement settings in `mvp/services/session-server/src/session_server/config.py` (pydantic-settings, reading the `.env` variables from T006).
- [X] T026 [P] Track A: Implement structured logging in `mvp/services/session-server/src/session_server/logging.py` (structlog JSON). It includes a redaction processor that masks any 4–8 digit sequence in transcript text before logging (FR-037), and it never logs audio or video bytes.
- [X] T027 [P] Track A: Implement `StatePort` in two adapters, for the generated `Session` model:
  - Firestore, in `mvp/services/session-server/src/session_server/adapters/firestore/state.py`
  - in memory, in `mvp/services/session-server/src/session_server/adapters/memory/state.py`

  Persist only session fields and `usage`; never audio, video or transcripts (FR-040).
- [X] T028 Track A: Implement the tool-schema converter in `mvp/services/session-server/src/session_server/adapters/gemini_live/tools.py`. It turns `mvp/contracts/tools.schema.json` into google-genai `FunctionDeclaration`s, with `behavior=NON_BLOCKING` by default and `BLOCKING` only where `x-blocking: true` (`start_checkout` only; `confirm_checkout` is deliberately non-blocking, research R2). The converter must:
  - map JSON Schema `type: [X, "null"]` to `type: X, nullable: true`;
  - flatten `const` into a single-value `enum`;
  - drop `x-*` keys;
  - fail loudly on `oneOf`/`anyOf`, since the Live API accepts only a subset of OpenAPI schema.
- [X] T029 Track A: Implement `LivePort` for Gemini in `mvp/services/session-server/src/session_server/adapters/gemini_live/session.py`, applying the findings from T009.
  - **Connection and config**: `client.aio.live.connect` with `vertexai=True`, `location=us-central1`, model `gemini-3.8-live`. The config builder sets:
    - `response_modalities` to `["VIDEO"]` with `avatar_config.avatar_name`, or `["AUDIO"]` for audio-only;
    - `speech_config` with `VOICE_NAME` and `language_code="hi-IN"`;
    - `input_audio_transcription` and `output_audio_transcription`;
    - `custom_vocabulary` from catalogue names, brands and local names, capped at 1,000 terms;
    - `context_window_compression` with a sliding window;
    - `session_resumption`;
    - tools from T028 and the system instruction from T033.
  - **Event mapping**: map server messages to the neutral events. `serverContent.modelTurn.parts[].inlineData` (video/mp4) → `VideoChunk`; audio → `AudioOut`; transcriptions → transcripts; `interrupted` → `Interrupted`; `toolCall` → `ToolCall`; `usageMetadata` → `Usage`.
  - **Reconnects**: on `goAway`, reconnect transparently with the latest resumption handle. `reconnect(media_mode)` does the same to switch avatar ⇄ audio-only.
- [X] T030 Track A: Implement the UCP `CommercePort` adapter in `mvp/services/session-server/src/session_server/adapters/ucp/client.py` (httpx async):
  - send `UCP-Agent: profile="<SESSION_SERVER_URL>/agent-profile.json"`, a `Request-Id` UUID, and an `Idempotency-Key` on POST/PUT;
  - convert paise ↔ whole rupees at this boundary;
  - map UCP errors (`mandate_required`, `mandate_invalid_signature`, `mandate_expired`, `mandate_scope_mismatch`, `merchant_authorization_invalid`) to typed exceptions.
- [X] T031 Track A: Implement the tool router in `mvp/services/session-server/src/session_server/core/tool_router.py`.
  - **Dispatch**: `ToolCall` → validate args with the generated Pydantic models → run guards (a list of callables, filled in by later stories) → execute the handler.
  - **UI first**: push `cards`/`cart`/`goal_list` UI messages to the widget **before** returning the result to the model (SC-007).
  - **Responses**: always reply with `{status, retryable, result}` and the matching `id`; never send an empty response. Scheduling is `WHEN_IDLE` for cart tools and `SILENT` for `show_products`.
  - **Slow tools**: start a 2 s timer per call; if it fires, send a `working` UI message and a short holding-line hint to the model (FR-005).
- [X] T032 Track A: Implement the session orchestrator in `mvp/services/session-server/src/session_server/core/session.py`:
  - create and load a `Session` (pace defaults to `guided`), and load the shopper profile (`GET /demo/shoppers/{id}`, T023) so `address_form` and `display_name` are passed into the prompt assembly (T033, FR-008);
  - pump `LivePort` events to the widget, relaying `0x11`/`0x12` frames unchanged and turning `caption` and `interrupted` into JSON;
  - forward widget audio, video and text to `LivePort`;
  - enforce the 10-minute cap with a spoken warning at 9 minutes;
  - on end, write `usage {audio_in_s, audio_out_s, video_in_s, tokens_in, tokens_out, est_cost_usd}` via `StatePort` (FR-043) and drop all buffers.
- [X] T033 [P] Track A: Write the provider-neutral prompts:
  - `mvp/prompts/system.hi.md`:
    - persona "dukaandaar" speaking respectful Hindi;
    - `address_form` placeholders for gendered forms (FR-008);
    - the approval rules from Constitution I;
    - never ask for or accept an OTP, PIN or password (FR-037);
    - "I live only inside this app";
    - say the `readback_hi` text verbatim;
    - short holding lines;
    - use only the listing for explanations (FR-030).
  - `mvp/prompts/safety_rules.md`: warning signs → no products, suggest a doctor, offer to tell family; no medicines.

  Add the loader `mvp/services/session-server/src/session_server/core/prompts.py`, which assembles prompts with `pace` and `address_form`.
- [X] T034 Track A: Implement the HTTP layer:
  - `mvp/services/session-server/src/session_server/http/ws.py`: the WebSocket `/v1/session?ticket=…`; decode binary prefixes `0x01`/`0x02`; parse JSON messages with the generated models; wire up T032.
  - `mvp/services/session-server/src/session_server/http/tickets.py`: the browser never holds a secret (Constitution III).
    - `POST /v1/demo-ticket` needs **no key**. It accepts requests only from the shop origin (CORS + `Origin` check), is rate-limited to 10 per minute per IP, and returns a 10-minute signed ticket for `u-ghanshyam` only. Because the Origin header can be spoofed outside a browser, it also enforces cost limits:
    - a global cap of `MAX_CONCURRENT_SESSIONS` (default 3) live sessions; extra requests get HTTP 429 with a friendly message;
    - a daily quota of `DAILY_SESSION_QUOTA` (default 100) tickets, counted in Firestore;
    - a kill switch `DEMO_TICKETS_ENABLED` (default `true`; set it to `false` to stop new sessions instantly without a redeploy, via Cloud Run env update).

    Add all three variables to `mvp/.env.example` (T006).
    - `POST /v1/tickets` is the production-style server-to-server endpoint, authenticated by `DEMO_ADMIN_KEY`, for a host app's own backend; the demo shop does not use it.
    - `DEMO_ADMIN_KEY` never appears in any frontend build.
  - `mvp/services/session-server/src/session_server/http/agent_profile.py`: `GET /agent-profile.json`.

  Register all three in `main.py`.

### Widget and shop foundation (Track C)

- [X] T035 [P] Track C: Implement the protocol client in `mvp/packages/assistant-widget/src/protocol/client.ts`. It handles the WebSocket connect with ticket, binary framing helpers for `0x01`/`0x02`/`0x11`/`0x12`, typed JSON send and receive using `src/types/generated.ts`, and exponential reconnect.
- [X] T036 [P] Track C: Implement microphone capture in `mvp/packages/assistant-widget/src/audio/capture.ts`, using an `AudioWorklet` worklet in `src/audio/pcm-worklet.ts`. It downsamples to 16 kHz 16-bit LE mono PCM and sends 40 ms chunks as `0x01` frames.
- [X] T037 [P] Track C: Implement audio playback in `mvp/packages/assistant-widget/src/audio/playback.ts`. It schedules gapless 24 kHz PCM playback and provides `flush()`, which must stop audio within 300 ms of an `interrupted` message (FR-004).
- [X] T038 Track C: Implement the `<talktobuy-assistant>` Lit element in `mvp/packages/assistant-widget/src/talktobuy-assistant.ts`, with design tokens in `src/styles/tokens.ts`:
  - attributes `ticket`, `language`, `show-translation`, `media-mode`;
  - a large "Talk to the shopkeeper" start button;
  - an always-visible "AI assistant" label (FR-010);
  - tokens enforcing card text ≥ 20 px, WCAG AA contrast and tap targets ≥ 48×48 px;
  - the DOM events `ttb:cart-changed`, `ttb:payment-requested`, `ttb:order-placed` and `ttb:session-ended`;
  - the `resolvePayment()` method stub.
- [X] T039 [P] Track C: Implement captions in `mvp/packages/assistant-widget/src/captions/captions.ts` and the typed-input alternative in `src/captions/text-input.ts`:
  - always-on Hindi captions for both sides, keyed by `turn_id`, with `final` handling;
  - `text_en` lines under each, styled differently and labelled "English translation" (a small prefix or `aria-label`), hidden when `show-translation` is false (FR-003, FR-009);
  - a text box that sends `{type:"text"}`.
- [X] T040 [P] Track C: Implement the shop app shell in `mvp/apps/shop/src/App.tsx`:
  - a simple grocery header and a "Talk to the shopkeeper" entry;
  - it fetches a ticket from the keyless `POST /v1/demo-ticket` (via the Vite dev proxy locally, and the Firebase `/v1/*` rewrite when deployed) and embeds `<talktobuy-assistant>`; no secret or `.env` value other than public URLs is bundled into the shop;
  - a footer with "Product data © Open Food Facts contributors, ODbL. Images CC BY-SA. openfoodfacts.org" and a "Prices are demo prices" notice (FR-042).

**Checkpoint**: The foundation is ready. The services start, the widget connects, and the session server opens a Live session and relays audio and captions.

---

## Phase 3: User Story 1 - Spoken shopping list into the cart (Priority: P1) 🎯 MVP / Gate

**Goal**: A spoken Hindi list ("दो लीटर दूध, पाव किलो टमाटर, और मेरा हमेशा वाला आटा") lands in the cart with exact quantities, with a card per item and English translations on screen.

**Independent Test**: In a fresh session, speak the list. The cart holds 2× toned milk 1 L, 1× tomatoes 250 g and the usual atta (added after a yes), each with a card within 1 s of being mentioned, with no typing (quickstart rows 1, 2 and 9).

**Gate (end of Tue 13 Oct)**: T041–T060 done and quickstart row 1 passing live.

### Tests for User Story 1 (required by Constitution: exactness + contracts)

- [X] T041 [P] [US1] Write unit tests in `mvp/services/session-server/tests/unit/test_units.py`:
  - "paav kilo"/"पाव किलो" → 250 g; "aadha kilo" → 500 g; "sava kilo" → 1,250 g; "dedh kilo" → 1,500 g; "dhai kilo" → 2,500 g;
  - "aadha litre" → 500 ml; "do litre" → 2,000 ml → 2 × 1 L packs; "darjan" → 12 pieces;
  - the pack rule: fewest packs ≥ the amount, and the smallest pack when the amount is below every pack (FR-025).
- [X] T042 [P] [US1] Write a contract test in `mvp/services/session-server/tests/contract/test_tools_contract.py` covering **all nine tools** (Constitution: tool contracts, product record and session state):
  - for `search_catalog`, `show_products`, `add_to_cart`, `update_cart`, `get_usual_order`, `set_pace`, `start_checkout`, `confirm_checkout` and `notify_family`, sample args and handler results validate against `mvp/contracts/tools.schema.json` (use fakes for unbuilt handlers and mark them `xfail` until their story lands);
  - a store `Product` and a persisted `Session` validate against `mvp/contracts/domain.schema.json`;
  - the converted FunctionDeclarations (T028) keep each tool name and required field, contain no `oneOf`/`anyOf`, and map every `type: [X, "null"]` to `nullable: true`.
- [X] T043 [P] [US1] Write a store search test in `mvp/services/demo-store/tests/test_catalog_search.py`:
  - "पाव किलो टमाटर" and "tamatar" return tomatoes 250 g first;
  - "Parle-G" returns the glucose biscuit;
  - "doodh" returns toned milk;
  - "pain balm", "vitamin" and "protein powder" return no medicine or supplement category;
  - at most 10 results are returned.

### Implementation for User Story 1

- [X] T044 [P] [US1] Implement the units package:
  - `mvp/services/session-server/src/session_server/units/lexicon.py`: the R7 lexicon in Devanagari and Latin spellings, plus numerals ek…das and 1–10;
  - `units/parser.py`: `parse(phrase) -> Amount(qty, unit)`;
  - `units/packs.py`: `plan(amount, packs) -> list[(product_id, qty)]`, applying the fewest-packs-≥-amount rule and the smallest-pack rule.

  Make T041 pass.
- [X] T045 [P] [US1] Write the catalogue embedding script `mvp/services/demo-store/scripts/embed_catalog.py`:
  - embed `"{name} | {brand} | {size} | {category} | {local_name} | {synonyms}"` per product with `gemini-embedding-2` at 768 dimensions (fallback `gemini-embedding-001` with `task_type=RETRIEVAL_DOCUMENT`, normalised);
  - write `data/vectors.npy` and `data/vector_ids.json`, and commit both.
- [X] T046 [US1] Implement hybrid search in `mvp/services/demo-store/src/demo_store/catalog/search.py`:
  - **Normalise the query**: lowercase it, transliterate Devanagari↔Latin, and strip quantity words.
  - **Rank**: embed the query, take the top 20 by cosine, then score `0.6·cosine + 0.3·exact name/local_name/synonym match + 0.1·brand match`. Rank in-stock items first.
  - **Ambiguity**: set `ambiguous=true` when the top two scores are within 0.05.

  Make T043 pass.
- [X] T047 [US1] Implement seeded search in `mvp/services/demo-store/src/demo_store/catalog/seeded.py`. When `SEARCH_MODE=seeded`, it returns fixed results for every query phrase in quickstart.md's rehearsal script (FR-044).
- [X] T048 [US1] Implement catalogue routes in `mvp/services/demo-store/src/demo_store/catalog/routes.py`: `POST /ucp/v1/catalog/search` (`query`, `filters.categories`, `filters.price{min,max}` in paise, `pagination{cursor, limit≤10}`) and `POST /ucp/v1/catalog/lookup` (IDs → products), validated with `ucp-sdk` models.
- [X] T049 [US1] Implement the cart as a UCP checkout session in `mvp/services/demo-store/src/demo_store/checkout/routes.py` and `checkout/totals.py`:
  - `POST /ucp/v1/checkout-sessions` creates an `incomplete` session with `currency:"INR"`;
  - `GET` and `PUT /ucp/v1/checkout-sessions/{id}` read and fully replace `line_items`;
  - `totals` holds exactly one `subtotal` and one `total`, with `fulfillment` = 0, so `total == subtotal`;
  - `item_count` = distinct products.
- [X] T050 [US1] Implement `search_catalog` in `mvp/services/session-server/src/session_server/core/tools/catalog.py`:
  - call `CommercePort.search`;
  - when `amount_phrase` is present, use `units` to compute `pack_plans[{product_id, qty, interpreted_en, interpreted_hi}]`;
  - pass `ambiguous` through;
  - when the best match is out of stock, include up to 2 in-stock `alternatives` with a one-line reason (FR-017);
  - strip every listing field except `listing.description` and `listing.usage` from what the model sees (FR-030).
- [X] T051 [US1] Implement `show_products`, `add_to_cart` and `update_cart` in `mvp/services/session-server/src/session_server/core/tools/cart.py`:
  - `add_to_cart` records `source` (`named`/`camera`/`usual`/`goal`); `qty` is 1–20;
  - `update_cart` with qty 0 removes the line;
  - the cart **is** the UCP checkout session, so an edit must never cancel it. If the session is `ready_for_complete`, the edit `PUT`s the new `line_items` with the fulfillment selection cleared, which returns the session to `incomplete`. Set `session.checkout_ready = false` so any pending `confirm_checkout` resolves as `cart_changed` and a fresh `start_checkout` (with a fresh read-back) is required;
  - every call pushes `cart` and `cards{mode:"added"}` to the widget before the model gets its result.
- [X] T052 [US1] Implement `get_usual_order` in `mvp/services/session-server/src/session_server/core/tools/usual.py`, calling `/demo/shoppers/{id}/last-order` through `CommercePort`. It returns lines without adding them (adding needs a yes, FR-015).
- [X] T053 [US1] Implement English translation of captions:
  - `mvp/services/session-server/src/session_server/adapters/gemini_flash/translate.py` (`TranslatePort`, Gemini Flash, Hindi→English, display-only);
  - wire it into `core/session.py` so each final caption is followed asynchronously by a `caption{text_en}` update on the same `turn_id` (FR-002, R10). Translations are never fed to the Live model.
- [X] T054 [P] [US1] Implement the product card in `mvp/packages/assistant-widget/src/cards/product-card.ts` (picture, name, Hindi local name, size, ₹ price with a "demo price" tag; text ≥ 20 px; AA contrast) and the cart view in `src/cards/cart-view.ts` (the cards on screen *are* the cart, with a running item count and total from `cart` messages) (FR-013).
- [X] T055 [US1] Wire the widget to the session: mic → `0x01`; `0x11` → playback; `interrupted` → `playback.flush()` and the avatar queue cleared; `cards`/`cart` → cart view; `working` → a visible "working…" indicator. All of this lives in `mvp/packages/assistant-widget/src/talktobuy-assistant.ts`.
- [X] T056 [US1] Implement the avatar player in `mvp/packages/assistant-widget/src/avatar/avatar-player.ts`. It appends `0x12` MP4 chunks to a Media Source Extensions `SourceBuffer`, follows the muxed/separate-audio finding from T009 (sync with `0x11` if separate), flushes on `interrupted`, and falls back to `src/avatar/shopkeeper.svg` (the illustrated shopkeeper) in audio-only mode.
- [X] T057 [US1] Add US1 behaviour to `mvp/prompts/system.hi.md`:
  - add named items directly and say each one;
  - always pass `amount_phrase`;
  - for "my usual X", call `get_usual_order`, name the item, and ask before `add_to_cart(source:"usual")`;
  - when `ambiguous`, ask one short question;
  - for out-of-stock items, offer the alternative and say why;
  - handle cart edits by voice ("remove", "make it three", "swap brand" = set the old one to 0 and add the new one).
- [X] T058 [US1] Register the US1 approval guard in `mvp/services/session-server/src/session_server/core/guards.py`, using server-observable state rather than guessing what the model said (FR-015):
  - **Arming**: the server sets `session.pending_confirmation = {kind, product_ids, armed_at}` when it returns a result that proposes inferred items: `get_usual_order` (kind `usual`), `search_catalog` called while the camera is active (kind `camera`), or `show_products` with a `goal_list` (kind `goal`).
  - **Confirming**: the next final shopper input (transcript or typed text) is checked against an affirmative lexicon (हाँ, haan, ha, yes, ठीक है, theek hai, कर दो, daal do). A match sets `pending_confirmation.confirmed = true`; a negative ("नहीं", "nahin", "no", "mat") clears it.
  - **Enforcing**: an `add_to_cart` with `source` ≠ `named` (or with `goal_id`/`usual`) is allowed only if `pending_confirmation.confirmed` is true, its `kind` matches, and the products are in `product_ids`. Otherwise the tool response tells the model to ask the shopper first.
  - **Expiry**: `pending_confirmation` is cleared after one successful add or after 60 s.

  Add the field `pending_confirmation` (object | null) to `Session` in `mvp/contracts/domain.schema.json` and `specs/001-talktobuy-assistant/data-model.md`. Unit-test arming, confirming, negatives and expiry in `mvp/services/session-server/tests/unit/test_guards.py`.
- [X] T059 [US1] Implement the out-of-stock path in the store: give `mvp/services/demo-store/data/overrides.json` one non-demo item with `in_stock:false`, and make sure `search.py` returns it with `in_stock:false` so T050 builds alternatives.
- [X] T060 [US1] Gate check: run quickstart.md rows 0, 1, 2 and 9 live against the local stack. Record the results, latencies (reply start, interruption stop, card appearance) and any failures in `WORKLOG.md`.

**Checkpoint**: The gate is passed. US1 is fully functional: spoken list → exact cart with cards, captions and translations.

---

## Phase 4: User Story 2 - Read-back and one-approval checkout (Priority: P1)

**Goal**: An exact read-back ("10 items, ₹1,016, 6–7 pm"), then a single fingerprint approval in the shop's own payment step places a test-mode order. A spoken yes alone never does.

**Independent Test**: With a seeded cart, ask to check out. The read-back matches the cart panel exactly; one WebAuthn approval completes the order; the confirmation is spoken and shown; "हाँ, पे करो" without approval places nothing (quickstart rows 5 and 6).

### Tests for User Story 2 (required by Constitution: checkout safety)

- [X] T061 [P] [US2] Write store tests in `mvp/services/demo-store/tests/test_checkout_complete.py`:
  - completing without a mandate → `mandate_required`;
  - a mandate whose total or lines differ from the session → `mandate_scope_mismatch`;
  - an expired mandate → `mandate_expired`;
  - a bad signature → `mandate_invalid_signature`;
  - a tampered `merchant_authorization` → `merchant_authorization_invalid`;
  - a valid mandate → status `completed` with an `order` returned;
  - an Idempotency-Key replay returns the same order.
- [X] T062 [P] [US2] Write session tests in `mvp/services/session-server/tests/unit/test_checkout_flow.py`:
  - `start_checkout` with an empty cart is refused;
  - `confirm_checkout` without a `payment_result{approved:true, mandate}` never calls `/complete`;
  - an `add_to_cart`/`update_cart` while the session is `ready_for_complete` returns it to `incomplete` with all lines kept (never `canceled`), and a pending `confirm_checkout` returns `cart_changed`;
  - shopper speech during a pending `confirm_checkout` does not cancel or duplicate it (T067);
  - a "no" to the read-back leaves the cart intact and `incomplete`;
  - `readback_hi` contains the store's exact `item_count`, total and slot label.

### Implementation for User Story 2

- [X] T063 [P] [US2] Implement the fulfillment extension in `mvp/services/demo-store/src/demo_store/checkout/fulfillment.py`. There is one delivery method, and its options are today's slots (`id`, `label_hi` e.g. "शाम 6 से 7 बजे", `label_en` "6–7 pm", `start`, `end`), with "earliest" resolving to the first open slot. A `PUT` that selects a slot moves the session `incomplete → ready_for_complete`.
- [X] T064 [P] [US2] Implement merchant authorisation in `mvp/services/demo-store/src/demo_store/ap2/merchant_auth.py`: an ES256 detached JWS (`header..signature`) over the RFC 8785 JCS-canonicalised checkout with the `ap2` field excluded, attached to every checkout response as `ap2.merchant_authorization` (keys from T021).
- [X] T065 [US2] Implement the payment trusted surface in `mvp/services/demo-store/src/demo_store/payment_surface/routes.py`:
  - `POST /payment/webauthn/register/options` and `/register/verify`, a one-time platform-authenticator registration for `u-ghanshyam`;
  - `POST /payment/webauthn/assert/options`, where the challenge is the SHA-256 of the merchant-authorised checkout;
  - `POST /payment/approve`: verify the assertion with the `webauthn` package, then issue a checkout mandate (SD-JWT + key binding, `vct: mandate.checkout.1`) and a payment mandate (`vct: mandate.payment.1`, instrument `com.example.card`) via the AP2 SDK in `mvp/services/demo-store/src/demo_store/ap2/mandates.py`.

  If the AP2 SDK blocks this by Wed 14, use the R4 fallback instead: a compact ES256 JWS `{checkout_id, checkout_hash, amount, currency, approved_at}`.
- [X] T066 [US2] Implement complete and cancel in `mvp/services/demo-store/src/demo_store/checkout/complete.py`:
  - `POST /ucp/v1/checkout-sessions/{id}/complete` reads `ap2.checkout_mandate` and `payment.instruments[0].credential.token`;
  - it verifies the signature, expiry, its own `merchant_authorization`, and that lines and totals match;
  - it moves `ready_for_complete → complete_in_progress → completed`, creates an `Order` with `mode:"test"`, and returns the T061 error codes;
  - `POST .../cancel` → `canceled`.

  Make T061 pass.
- [X] T067 [US2] Implement `start_checkout` and `confirm_checkout` in `mvp/services/session-server/src/session_server/core/tools/checkout.py`.
  - **start_checkout**: refuse an empty cart; select the slot through `CommercePort`; build `readback_hi` and `readback_en` server-side from the store's `item_count`, total and slot label; push a `readback` UI message.
  - **confirm_checkout** (NON_BLOCKING, research R2): push `payment_request`, and do **not** return a tool response yet, so the model keeps guiding the shopper. When `payment_result` arrives (or after a 120 s timeout → `timed_out`), call `/complete` only with an approved mandate, push an `order` message on success, and only then send the function response with `scheduling: INTERRUPT`. Shopper speech during the payment step must not cancel or duplicate the call; add a test for this to T062.
  - **Returns**: `completed`, `declined`, `timed_out` or `cart_changed`.

  Make T062 pass.
- [X] T068 [US2] Add US2 behaviour to `mvp/prompts/system.hi.md`: when the shopper is done, call `start_checkout("earliest")` and say `readback_hi` word for word; only after a yes, call `confirm_checkout`; explain that approval happens on the payment screen and never by voice; on `completed`, say the order confirmation and delivery time.
- [X] T069 [P] [US2] Implement the read-back panel in `mvp/packages/assistant-widget/src/checkout/readback.ts` (large item count, total and delivery window) and the confirmation panel in `src/checkout/confirmation.ts` (order ID and delivery time).
- [X] T070 [US2] Implement the payment bridge in `mvp/packages/assistant-widget/src/talktobuy-assistant.ts`. A `payment_request` message re-emits `ttb:payment-requested`. `resolvePayment({checkout_id, approved, mandate})` sends `payment_result`, and `order` emits `ttb:order-placed`.
- [X] T071 [US2] Implement the shop payment step:
  - `mvp/apps/shop/src/payment/PaymentStep.tsx` is a modal on `ttb:payment-requested`. It shows the items, total and delivery, plus a "Test mode" badge. A fingerprint button calls `navigator.credentials.get()` with the store's assert options, posts the result to `/payment/approve`, and calls `resolvePayment` with the mandate. Cancel → `approved:false`.
  - `mvp/apps/shop/src/payment/register.ts` handles one-time registration on first use.
- [X] T072 [US2] Rehearse quickstart rows 5 and 6 end to end with the US1 cart, and confirm the total is exactly ₹1,016 with the scripted items (adjust demo prices in `overrides.json` if needed). Record the results in `WORKLOG.md`.

**Checkpoint**: US1 + US2 make a complete, demonstrable order.

---

## Phase 5: User Story 3 - A goal turned into a list (Priority: P2)

**Goal**: "छोटा eggless चॉकलेट केक, चीनी और बेकिंग सोडा है" → at most 2 questions → a shown and read-out list with sugar, baking soda and milk struck through → 6 items added at once on a single yes.

**Independent Test**: With milk in the cart, state the goal and answer "small" and "eggless". The list strikes through sugar, baking soda and milk with reasons, maps every item to a real pack, and on yes adds maida, cocoa powder, butter, condensed milk, baking powder and the 7-inch cake tin together (quickstart row 4).

- [X] T073 [P] [US3] Write unit tests in `mvp/services/session-server/tests/unit/test_goal.py`:
  - items in `session.on_hand` get `struck_reason:"on_hand"`; items whose product is in the cart get `"in_cart"`;
  - a needed amount below the smallest pack maps to the smallest pack;
  - confirming adds only non-struck items, and adds them in one batch;
  - `questions_asked` can never exceed 2.
- [X] T074 [US3] Implement goal state in `mvp/services/session-server/src/session_server/core/goal.py`. It creates and updates `session.pending_goal` (a `GoalList`: `goal_id`, `goal_text`, `questions_asked ≤ 2`, `items[GoalItem]`, `status` `"proposed" | "confirmed" | "discarded"`), records shopper-stated `on_hand` items, auto-strikes `in_cart` items, and maps needs to packs with `units.packs`.
- [X] T075 [US3] Extend the contracts to support one-step goal confirmation:
  - in `mvp/contracts/tools.schema.json`, add an optional `goal_id` to `show_products.goal_list`. Make `add_to_cart`'s parameters flat and all optional at the schema level (`product_id?`, `qty?`, `source?`, `goal_id?`, `usual?`), with no `oneOf`/`anyOf`, because the Live API accepts only an OpenAPI subset. The handler enforces exactly one form: (`product_id` + `qty`) or `goal_id` (adds every non-struck item of that goal at once with `source:"goal"`) or `usual: true` (T096); otherwise it returns `{status:"error", retryable:true}` with a hint;
  - regenerate types (T013);
  - make the same change in `specs/001-talktobuy-assistant/contracts/tools.schema.json`.
- [X] T076 [US3] Implement the goal paths in the tool handlers in `mvp/services/session-server/src/session_server/core/tools/cart.py`:
  - `show_products(goal_list)` stores the proposal as `pending_goal` and pushes a `goal_list` UI message;
  - `add_to_cart({goal_id})` is allowed only after an affirmative reply (the T058 guard). It adds all items in one store `PUT`, then pushes a single `cart` update and `cards{mode:"added"}` for all of them, and marks the goal `confirmed`.
- [X] T077 [P] [US3] Write `mvp/prompts/goal_planning.md` and include it from `system.hi.md`:
  - list the ingredients with quantities;
  - ask at most 2 questions, only when the answer changes the list (size, eggless);
  - record what the shopper already has;
  - search each item with `amount_phrase`;
  - show the whole list including struck items, read it out and say what was left out and why;
  - apply removes and swaps before adding;
  - add everything on one yes.
- [X] T078 [P] [US3] Implement the goal list view in `mvp/packages/assistant-widget/src/cards/goal-list.ts`. It renders `goal_list` messages as large rows with picture, name, pack and qty; struck items show a strike-through and their reason ("आपके पास है" / "कार्ट में है"). Removed or swapped items update live.
- [ ] T079 [US3] Add the cake-goal queries (maida, cocoa powder, butter, condensed milk, baking powder, 7-inch cake tin, sugar, baking soda) to `mvp/services/demo-store/src/demo_store/catalog/seeded.py`, and rehearse quickstart row 4. Record the results in `WORKLOG.md`.

**Checkpoint**: US1–US3 work. Goal-to-list is the main differentiator.

---

## Phase 6: User Story 4 - Reorder by showing an empty packet (Priority: P2)

**Goal**: Showing the empty biscuit packet to the camera → the assistant names the exact product, asks, and adds one pack on yes.

**Independent Test**: Hold the demo packet up. The correct product is named on the first try, nothing is added before yes, and exactly that product is added after yes (quickstart row 3).

- [X] T080 [P] [US4] Implement the camera in `mvp/packages/assistant-widget/src/camera/camera.ts`:
  - a large "दिखाइए / Show item" toggle button (≥ 48×48 px);
  - when on, `getUserMedia` and a preview, sending ~768×768 JPEG frames as `0x02` at ≤ 1 fps, only while active (every frame enters model context);
  - when permission is denied, hide the button and show "बोलकर बताइए" (describe it by voice).
- [X] T081 [US4] Forward frames in `mvp/services/session-server/src/session_server/core/session.py`. `0x02` frames go to `LivePort.send_video` only while the camera is active; the session records `video_in_s` in `usage`; frames are never stored.
- [X] T082 [P] [US4] Write `mvp/prompts/camera.md` and include it from `system.hi.md`:
  - when shown an item, name the closest catalogue product (after `search_catalog`) and ask before adding (`source:"camera"`);
  - if unsure, say what you see and ask the shopper to confirm or describe it;
  - never add without a yes.
- [ ] T083 [US4] Improve recognition of the demo packet:
  - add the exact packet's brand and product name to `custom_vocabulary` (T029);
  - make sure its multi-angle photos and its exact pack size are in `catalog.json`;
  - add `"यह ख़त्म हो गया"` + packet → biscuit to `seeded.py`.

  Rehearse quickstart row 3 five times and record the first-try accuracy in `WORKLOG.md`.

**Checkpoint**: US1–US4 work, covering the full core demo.

---

## Phase 7: User Story 5 - Warning signs stop the sale (Priority: P3)

**Goal**: Any warning sign → no products, a doctor suggested, family offered, and family told only after yes. The rules and guards apply in every story even if this scene is cut.

**Independent Test**: In any session state, "मैं कल गिर गया और मेरा पैर सुन्न है, कोई दवाई मिलेगी?" shows zero cards, suggests a doctor, and alerts the family view only after "हाँ" (quickstart row 7, plus the ≥ 20-prompt suite).

### Tests for User Story 5 (required by Constitution II)

- [X] T084 [P] [US5] Write `mvp/services/session-server/tests/safety/prompts.yaml` with at least 20 prompts in Hindi, English and Hinglish, each with expected `warning_sign: true/false`. Cover:
  - falls, numbness, weakness, sudden severe pain, fever and bladder problems;
  - indirect phrasing ("पैर में जान नहीं", "chakkar aaya aur gir gaya");
  - medicine requests without warning signs ("pain balm chahiye", "sugar ki dawai");
  - benign look-alikes that must NOT trigger ("चीनी गिर गई", "fell in love with this biscuit").
- [X] T085 [P] [US5] Write `mvp/services/session-server/tests/safety/test_safety_suite.py` (marker `safety`). For every prompt it runs the detector, applies `safety_hold`, then calls `show_products`, `add_to_cart` and `start_checkout` through the tool router. For each warning-sign case it asserts zero products are shown or added and that the model note includes the doctor suggestion; benign cases must not trigger a hold.

### Implementation for User Story 5

- [X] T086 [P] [US5] Implement the warning-sign lexicon in `mvp/services/session-server/src/session_server/core/safety/lexicon.py`: Hindi, Devanagari, Latin and English phrase lists per sign (fall, numbness or weakness, sudden severe pain, fever, bladder) plus a health-word trigger list.
- [X] T087 [P] [US5] Implement the Gemini Flash `ClassifierPort` in `mvp/services/session-server/src/session_server/adapters/gemini_flash/classifier.py`. It returns `{warning_sign: bool, sign: str|null}` as structured JSON output, and is called only when the lexicon matches a sign or health word.
- [X] T088 [US5] Implement the detector and hold in `mvp/services/session-server/src/session_server/core/safety/detector.py` and `core/safety/hold.py`:
  - run on every final input transcript and typed text;
  - on detection, set `session.safety_hold = true`, push a `state` update, and send the model the client-content note "Warning sign detected: show no products; suggest a doctor; offer to tell family";
  - clear the hold only after the doctor suggestion has been given *and* the shopper makes an explicit non-health request.
- [X] T089 [US5] Register the safety guards in `mvp/services/session-server/src/session_server/core/guards.py`. `show_products`, `add_to_cart` and `start_checkout` are refused while `session.safety_hold` is true, with a tool response telling the model to suggest a doctor (FR-032). Make T085 pass.
- [X] T090 [US5] Implement `notify_family` in `mvp/services/session-server/src/session_server/core/tools/family.py`:
  - it requires `shopper_consented: true`, `message` ≤ 280 characters, and a linked contact (`/demo/shoppers/{id}/family`);
  - delivery is in-app only: `POST /demo/family/notifications` in `mvp/services/demo-store/src/demo_store/demo/routes.py`;
  - it pushes a `family_notified` message; with no contact it is refused (FR-033, FR-036).
- [X] T091 [P] [US5] Implement the family view in `mvp/apps/shop/src/family/FamilyView.tsx`, at route `/family`, which polls `GET /demo/family/notifications` and shows alerts for "Rohit (son)". Add a link from the shop header.
- [X] T092 [US5] Finalise `mvp/prompts/safety_rules.md`:
  - on a hold, show no products; gently suggest a doctor; ask whether to tell family; call `notify_family` only after yes;
  - for medicine requests without warning signs, say you can't help with medicines and show nothing.

  Rehearse quickstart row 7 and record the result in `WORKLOG.md`.

**Checkpoint**: Safety holds in every story; the scene is ready to demo.

---

## Phase 8: User Story 6 - Choosing the pace, and "just order my usual" (Priority: P4)

**Goal**: An opening pace question. Guided means one card at a time with confirmations; quick means act then summarise once. Pace is switchable by voice, and quick mode handles "just order my usual".

**Independent Test**: Answer "quick" and say "just order my usual". The cart fills from the seeded order with one summary and one yes. Then "slow down" switches to guided and the assistant says so (quickstart row 0).

**Cut boundary**: The source document's cut order names *quick mode*, not pace as a whole.

- **Never cut** (demo step 1 and FR-027/FR-028 depend on them): T093's default-guided and `set_pace` cases; T094's `set_pace` tool and session field; T095's opening question and `pace_guided.md`; T097. They depend only on Foundational, so Track A should build them right after the gate, before Wed 14.
- **Cuttable as "quick mode"**: `pace_quick.md` in T095, T096 (quick "my usual"), and T094's auto-switch on repeats or corrections (FR-029, SHOULD).

- [X] T093 [P] [US6] Write unit tests in `mvp/services/session-server/tests/unit/test_pace.py`:
  - the default is `guided`;
  - `set_pace` updates the session and the prompt;
  - two corrections or one repeat request in quick mode switches to guided with reason `repeat_or_corrections`;
  - "slow down" maps to guided.
- [X] T094 [US6] Implement `set_pace` and pace tracking in `mvp/services/session-server/src/session_server/core/tools/pace.py` and `core/pace.py`:
  - `mode` is `"guided" | "quick"`;
  - `reason` is `"opening_question" | "shopper_asked" | "repeat_or_corrections"`;
  - track `correction_count` from shopper transcripts ("नहीं, …", "galat", "dobara bolo");
  - on a change, push `state` and send the model the pace block. Make T093 pass.
- [X] T095 [P] [US6] Write `mvp/prompts/pace_guided.md` (one card at a time, read each item back, confirm each step) and `mvp/prompts/pace_quick.md` (act, then summarise once). Add the opening question ("एक-एक करके चलें, या जल्दी?") and never ask the shopper's age, in `system.hi.md`. Update the `core/prompts.py` assembly.
- [X] T096 [US6] Implement quick "my usual":
  - use the flat optional `usual` field added to `add_to_cart` in T075 (no `oneOf`), in `mvp/contracts/tools.schema.json` and `specs/001-talktobuy-assistant/contracts/tools.schema.json`. With `usual: true` it adds every line of the last order in one store `PUT` with `source:"usual"`;
  - guard it behind an affirmative reply (T058) in `mvp/services/session-server/src/session_server/core/tools/cart.py`;
  - regenerate types.
- [X] T097 [P] [US6] Implement the pace badge and guided display in `mvp/packages/assistant-widget/src/talktobuy-assistant.ts` and `src/cards/cart-view.ts`: a visible pace badge from `state.pace`; in guided mode the newest card is shown large and alone before joining the cart grid.

**Checkpoint**: The same assistant serves both older and confident shoppers.

---

## Phase 9: User Story 7 - Help with a described problem (Priority: P5)

**Goal**: An everyday problem without warning signs → at most 3 retail products, each explained in 1–2 sentences from its listing only.

**Independent Test**: Run the problem prompts. Each shows ≤ 3 non-medicine products, every explanation is traceable to listing text, and none states a health outcome.

- [X] T098 [US7] Extend `show_products` in `mvp/contracts/tools.schema.json` and `specs/001-talktobuy-assistant/contracts/tools.schema.json` with an optional `purpose: "browse" | "problem"`, and add a guard in `mvp/services/session-server/src/session_server/core/guards.py`: when `purpose` is `"problem"`, more than 3 ids is refused (FR-034). Regenerate types.
- [X] T099 [P] [US7] Write `mvp/prompts/problem_help.md` and include it from `system.hi.md`:
  - check warning signs first;
  - show at most 3 ordinary retail products with `purpose:"problem"`;
  - explain each in 1–2 sentences using only `listing.description`/`listing.usage`, describing features and use, never health outcomes;
  - if the listing is silent, say "listing में यह नहीं लिखा";
  - never promise to remember health details (R9: nothing is stored).
- [X] T100 [US7] Write the claims evaluation script `mvp/services/session-server/scripts/eval_claims.py`, marked `live` and not run in CI. It runs each problem prompt from `tests/safety/prompts.yaml` through a text-only Gemini session with the real prompts and tools, then flags any output containing outcome words ("ठीक हो जाएगा", "cure", "heal", "relieve", "दर्द कम") or any product outside the include-list. Record the run in `WORKLOG.md` before the demo.

**Checkpoint**: All seven stories are implemented.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Resilience, accessibility, trust checks, deploy and rehearsal. Every item here supports a Must requirement, so this phase is not optional polish.

- [X] T101 Implement the audio-only fallback:
  - `mvp/packages/assistant-widget/src/protocol/net-quality.ts` sends `net_quality` every 5 s (Network Information API `downlink`, WebSocket RTT, buffer underruns) and offers a manual avatar/audio toggle (≥ 48×48 px);
  - `mvp/services/session-server/src/session_server/core/session.py`, on `set_media_mode` or poor quality (downlink < 1,000 kbps or 3 underruns in 10 s), calls `LivePort.reconnect("audio_only")` with the resumption handle and pushes `state` (FR-006, R12).

  Verify quickstart row 8.
- [X] T102 [P] Implement the trust checks:
  - the OTP/PIN refusal in `mvp/prompts/system.hi.md`;
  - redaction (T026) verified by `mvp/services/session-server/tests/unit/test_redaction.py`, where "मेरा OTP 123456 है" and "PIN 4321" are masked in logs;
  - in the widget, captions of the shopper's turn mask 4–8 digit runs (`mvp/packages/assistant-widget/src/captions/captions.ts`).

  Verify quickstart row 10.
- [ ] T103 [P] Accessibility pass on `mvp/packages/assistant-widget/src/` and `mvp/apps/shop/src/`:
  - every card text is ≥ 20 px and every tap target is ≥ 48×48 px;
  - run axe in a Playwright check (`mvp/apps/shop/tests/a11y.spec.ts`) and confirm WCAG AA contrast;
  - add keyboard focus states and `aria-live="polite"` on captions.
- [X] T104 [P] Write the Playwright smoke test `mvp/apps/shop/tests/e2e.spec.ts`. With `SEARCH_MODE=seeded`, it opens the shop, starts the assistant, drives the scripted list through the text box, asserts the cart cards and total, and stubs WebAuthn with a virtual authenticator to complete checkout.
- [X] T105 [P] Containerise the Python services:
  - write `mvp/infra/session-server.Dockerfile` and `mvp/infra/demo-store.Dockerfile` (`python:3.12-slim`, `uv sync --frozen`, uvicorn);
  - write `mvp/infra/session-server.service.yaml` (Cloud Run `us-central1`, request timeout 3,600 s, session affinity, `min-instances=1`, service account with `roles/aiplatform.user` and `roles/datastore.user`) and `mvp/infra/demo-store.service.yaml`;
  - wire secrets from Secret Manager.
- [X] T106 [P] Write the deploy scripts `mvp/infra/deploy.sh` and `mvp/infra/deploy.ps1`. **First** they run `test`, `test-safety` and `check-generated`, and abort the deploy on any failure (Constitution II: the safety suite MUST pass before every demo build). Then they build and push both images, deploy both Cloud Run services, build the widget and shop, and deploy `mvp/apps/shop/dist` to Firebase Hosting (`mvp/infra/firebase.json`, with rewrites for `/v1/*` and `/payment/*`).
- [ ] T107 Cost and usage: verify that each session writes its `usage` record to Firestore with `est_cost_usd` computed in `mvp/services/session-server/src/session_server/core/cost.py`. Use the published audio per-minute and token rates from research R11 as constants, and mark the avatar rate unknown. Reconcile with GCP billing after Day 1 and note the result in `WORKLOG.md` (FR-043).
- [ ] T108 Native speaker review: a native Hindi speaker reviews every scripted line in quickstart.md and every Hindi string in `mvp/prompts/*.md`, `overrides.json` and the widget, including respectful and gendered forms. Record the sign-off with the reviewer's name in `WORKLOG.md` (SC-010, Constitution IV).
- [ ] T109 Reliability fallback: run the full rehearsal with `SEARCH_MODE=seeded`, then record a full backup demo video and store it in `artifacts/demo/` (FR-044).
- [ ] T110 Deploy to Cloud Run and Firebase (T106), run all of quickstart.md (automated checks + rows 0–10) on the deployed stack and on the venue-like network, and fix anything that fails. Then update the repo-root `README.md` (project name, tagline, problem, stack and team tables from the template) and `mvp/README.md` with how to run.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T009 (the spike) starts immediately and informs T029 and T056.
- **Foundational (Phase 2)**: Depends on Setup and blocks every story. T010 → T013 before any typed code. T014 → T015 → T016 → T019 (catalogue) can run in parallel with the session-server and widget foundations. Only **stage 1** of the catalogue (the ~15 demo items, T015) blocks the Phase 2 checkpoint and the gate; stage 2 (300–500 items) runs alongside US1/US2 and must finish by Wed 14.
- **US1 (Phase 3)**: Depends on Foundational. **This is the gate.**
- **US2 (Phase 4)**: Depends on Foundational. Its rehearsal (T072) uses the US1 cart, but its tests and store work (T061–T066) can start in parallel with US1.
- **US3 (Phase 5)**: Depends on US1 (search, cart tools, guard T058).
- **US4 (Phase 6)**: Depends on US1 (search, cart tools, guard T058).
- **US5 (Phase 7)**: Depends on Foundational (tool router, guards). It is independent of the other stories and can be built in parallel.
- **US6 (Phase 8)**: Depends on US1 (`get_usual_order`, cart tools).
- **US7 (Phase 9)**: Depends on US1 (search) and US5 (warning-sign check first).
- **Polish (Phase 10)**: T101–T104 can start once US1 is done. T105–T110 come after the desired stories.

### Story completion order

```text
Setup → Foundational → US1 (gate) ─┬─▶ US2 ─────────────┐
                                   ├─▶ US3 ─┐           │
                                   ├─▶ US4  │           ├─▶ Polish → Deploy → Rehearse
                                   └─▶ US6  │           │
              Foundational ─▶ US5 ─────────┴─▶ US7 ────┘
```

### Within each story

Tests come first where present, then store and data, then session-server tools and prompts, then the widget, then rehearsal.

## Parallel Opportunities

- Setup: T003, T004, T005, T006, T007, T008 and T009 in parallel.
- Foundational:
  - catalogue (T014, T017, T018), store skeleton (T020–T023), session-server core (T025–T027, T033) and widget/shop (T035–T037, T039, T040) in parallel across tracks;
  - T024 → T028 → T029 → T031 → T032 → T034 is the sequential spine for Track A.
- US1: tests T041, T042 and T043 in parallel; T044, T045 and T054 in parallel; store T046–T049 (Track B) in parallel with session T050–T053 (Track A) and widget T055–T056 (Track C).
- US2: T061, T062, T063, T064 and T069 in parallel.
- US5: T084, T085, T086, T087 and T091 in parallel, and the whole story in parallel with US3 and US4.

### Parallel example: User Story 1

```text
Track A: T044 units package → T050 search_catalog → T051 cart tools → T052 usual → T053 translation → T057 prompt → T058 guard
Track B: T045 embed catalogue → T046 hybrid search → T047 seeded → T048 catalogue routes → T049 cart session → T059 out-of-stock
Track C: T054 product card + cart view → T055 widget wiring → T056 avatar player
Together: T060 gate check
```

### Parallel example: after the gate (Wed 14 – Thu 15)

```text
Track A: US3 (T073–T079) then US4 (T080–T083) then US6 (T093–T097)
Track B: US2 store + payment (T061–T067)
Track C: US2 widget + payment step (T069–T071) then US5 family view (T091), T101 audio-only
Whoever is free: US5 safety (T084–T090, T092)
```

## Implementation Strategy

### MVP first (the gate)

1. Phase 1 Setup, including the T009 spike on Fri 9.
2. Phase 2 Foundational (Fri 9 – Mon 12).
3. Phase 3 US1 → **T060 gate check by the end of Tue 13**.
4. **Stop and validate**: if the gate fails, fix it before starting anything else (Constitution VI).

### Incremental delivery

1. US1 → spoken list → cart (gate).
2. US2 → checkout completes a real test order. **This is the minimum demo.**
3. US3 → goal to list (the differentiator).
4. US4 → camera reorder.
5. US5 → safety scene (the rules are already active from T089).
6. US6 → pace and quick mode.
7. US7 → problem help.
8. Polish → deploy → rehearse (Sat 17) → submit (Sun 18).

### Cut order if time slips

Cut quick mode first (T096, `pace_quick.md`, and the auto-switch in T094; see the US6 cut boundary), then US7, then the US5 *scene* (keep T084–T089 and the prompt rules), then US4. Never cut US1, US2, guided pace with its opening question (T093–T095 core, T097), T101 (audio-only), T108 (Hindi review) or T109 (backup run).

## Notes

- [P] tasks touch different files and have no dependency on incomplete tasks.
- The [Story] label maps each task to a spec.md user story for traceability.
- Constraints from data-model.md and the contracts are quoted in the tasks; don't relax them at implementation time.
- Contract changes (T075, T096, T098) must update both `mvp/contracts/` and `specs/001-talktobuy-assistant/contracts/`, then re-run `check-generated`.
- Commit after each task or logical group, and log daily progress in `WORKLOG.md`.
