# Work Log

Daily progress, decisions, blockers, and notes. Most recent entry at the top.

---

## Log Format

```
## YYYY-MM-DD — [Your Name]
**Focus:** What you worked on today
**Done:** What was completed
**Blockers:** What is blocking progress
**Next:** What you plan to do next
**Notes:** Any decisions made, context, or things to remember
```

---

## 2026-10-12 — Alok (with Claude Code)
**Focus:** GCP setup, Live Avatar spike, catalogue embeddings, gate check.

**Done:**
- **GCP:** project `talktobuy` (billing on, Vertex AI on), region `us-central1`. The application-default credentials' quota project was changed from `zeroqueue-503710` to `talktobuy`.
- **T009, Live Avatar works:** the preset avatar Kai speaks Hindi. Media arrive as fragmented MP4 with the audio muxed in (H.264 `avc1.42C01F` + AAC), so the widget uses `avatar-audio="muxed"`. Video uses about 4–5 Mbit/s.
- **T045, catalogue embedded:** `gemini-embedding-2` isn't available on the project, so all 500 products were embedded with `gemini-embedding-001`. The model name is recorded in `vectors_meta.json`, and search queries use the same model.
- **T060, gate passed:** an automated text smoke test (`mvp/scripts/smoke_live.py`) and the team's voice run both put 2 × milk 1 L and tomatoes 250 g in the cart, with cards, live.
- **Fixes:**
  - The Flash model is now `gemini-2.5-flash`; the 3.x IDs return 404.
  - Thinking is turned off for translation and the safety classifier, so English captions are no longer cut off.
  - Each caption is sent once instead of twice.
  - New `STATE_BACKEND` setting: memory locally, Firestore on Cloud Run.

**Blockers:** None for local runs. Firestore, Cloud Run, Secret Manager, Artifact Registry and Firebase APIs are not yet enabled; they are needed for deploy.

**Live rehearsal by text** (`mvp/scripts/rehearse_live.py`; real model, software fingerprint):
- **Results:**
  - Row 1 (exact quantities; usual atta added only after a yes) passes.
  - The read-back equals the cart.
  - A spoken "हाँ, पे कर दो" places no order.
  - One approval completes the order.
  - The safety stop shows no products.
- **T100 claims evaluation:** 27 cases, 0 violations (`services/session-server/scripts/eval_claims.py`).
- **Bugs found live, and fixed:**
  - Guided pace dropped items from a multi-item list (prompt fix).
  - The model repeated `add_to_cart` calls (server de-duplicates within a request).
  - Re-showing the goal list wiped the shopper's "yes" (a re-arm now keeps it).
  - One bad goal line made the store reject the whole batch (goal items are vetted when shown; store rejections are logged).
  - `<no speech>` markers appeared as captions (filtered).
- **Demo data:** the smallest-pack rule correctly picks Weikfield baking powder 50 g, so that pack is now the ₹40 demo item (100 g repriced to ₹65). The scripted cart is still ₹1,016.
- **Known variance:**
  - The model sometimes picks a different pack (₹1,001 or ₹1,041); the read-back still matches the cart. For a word-exact stage total, run the store with `SEARCH_MODE=seeded`.
  - Milk already in the cart is often not listed struck "in cart" on the cake list (T079 open). It is never added twice.
  - The delivery slot depends on the clock ("4–5 pm" today). Set `DEMO_CLOCK` for a fixed "6–7 pm".

**Next:** Camera rehearsal with the real packet (T083), cake strike-through (T079), Hindi review (T017, T108), enable the deploy APIs, then deploy (T110).

**Notes:**
- In text runs the first reply took 5.5–7.4 s to start, against the spec's 1.5 s target. It felt OK in the voice run; measure it in rehearsal.
- A query like "pain balm" returns its nearest items (honey). This is harmless, but consider a minimum-similarity cut-off.

---

## 2026-10-09 — Alok (with Claude Code)
**Focus:** Spec Kit setup (constitution, spec, plan, tasks, analysis), then `/speckit-implement`.

**Done** (95 of 110 tasks in `specs/001-talktobuy-assistant/tasks.md`):
- **Session server** (Python):
  - All nine tools, guards (approval, safety, form), tool router, orchestrator, prompts.
  - Adapters: Gemini Live + Live Avatar, Flash, Firestore, UCP.
  - Tickets with cost guards.
  - 140 tests, including the 24-prompt safety suite.
- **Demo store** (Python, UCP 2026-08-25):
  - 500-item Open Food Facts catalogue; the scripted cart is exactly ₹1,016.
  - Hybrid search, checkout session as cart, delivery slots, AP2 test-mode mandates, WebAuthn payment surface.
  - 103 tests.
- **Widget** (Lit) and **shop** (React):
  - Captions with labelled English translation, cards, goal list, camera, audio-only mode, payment step, family view.
  - 28 Vitest tests; both build.
- **Integration**: `mvp/tests/integration`, 3 tests. The full demo script runs in-process across real services, from spoken list to fingerprint checkout, plus the safety stop.
- **Infra**: Dockerfiles, Cloud Run YAML, Firebase config, `deploy.sh` and `deploy.ps1`. Deploys are gated on tests, the safety suite and the generated-types check.

**Blockers:**
- No confirmed GCP project. `mvp/.env` now says `GCP_PROJECT=talktobuy`, but it was set outside this session, so it isn't confirmed yet, and **no Google Cloud call has been made**.
- Never use `zeroqueue-503710`. All code refuses it.
- Live Avatar access is untested (T009).

**Next:**
1. Confirm the GCP project and run the T009 spike.
2. Embed the catalogue (T045).
3. Gate check live (T060).
4. Rehearse the quickstart rows (T072, T079, T083, T092).

**Notes / decisions:**
- **Demo store fork:** a lean fork of the UCP Python sample, because upstream targets 2026-04-08 and `ucp-sdk<0.5`. See `mvp/services/demo-store/UPSTREAM.md`.
- **AP2:** uses the R4 compact-JWS mandate fallback; SD-JWT is the upgrade path.
- **Contract changes:**
  - `add_to_cart` has flat optional forms: product, `goal_id` or `usual`.
  - `show_products.purpose` added.
  - `PendingConfirmation.kind` gains `family`, so family alerts are also consent-checked server-side.
  - Tool `Product.image` is optional.
- **Search fix:** the integration test caught "Parle-G biscuit" ranking another Parle product first. Fixed with curated synonyms on p-0004.
- **Catalogue:** the 460 stage-2 items have generated Hindi names (tag `talktobuy:auto-hindi`) and **need native review** (T017, T108).
- **Demo packet:** assumed to be Parle-G Original 150 g (8901719255151). Change it in `seed_barcodes.json` and `overrides.json` if yours differs (T083).

---

<!-- Add new entries above this line, most recent at top -->

## YYYY-MM-DD — [Name]
**Focus:** 
**Done:** 
**Blockers:** 
**Next:** 
**Notes:** 

---
