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
