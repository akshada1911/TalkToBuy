# TalkToBuy
TalkToBuy: a voice-first AI shopkeeper for Hindi and English. Say a dish, get its ingredients in the right amounts, and add them to one shared cart with a fingerprint checkout. Built on Gemini Live and Cloud Run.
# TalkToBuy

**A voice-first AI shopkeeper for Hindi and English.** Say what you want to cook, and TalkToBuy works out the
ingredients in the right amounts, puts them in one shared cart, and checks out with a fingerprint.

Built for people who find shopping apps hard: senior citizens and first-time smartphone users. Talk to it, or
just browse and tap. Both fill the same cart.

> Team **AVA-AI**: Alok Jain, Vaibhav Singh, Akshada Borhade

## What it does

- **Talks like a shopkeeper.** It greets you by name and asks one question at a time, in Hindi or English.
- **Any dish becomes a shopping list.** Say "I want to make matar paneer", give the number of people, and it
  plans every ingredient in kg, g or litres (50 people of biryani means about 5 kg of rice, never 50 packets).
  It finds the right packs in the catalogue and asks before adding.
- **One cart for talking and tapping.** Browse 525 products and add them yourself, or ask the shopkeeper.
  "Clear the cart" and "cancel my order" work either way.
- **Safe checkout.** Payment happens only on the payment screen with a fingerprint, never by voice. The
  assistant never asks for an OTP, PIN or card number.
- **Phone-style demo UI.** On a laptop the app sits inside a phone frame with a short lock-screen intro, and
  the payment ends with a fingerprint scan and a green "Order placed" tick.

## How it works

```text
 phone / browser                 Cloud Run                         Google Cloud (Vertex AI)
┌──────────────────┐   voice   ┌───────────────────────┐        ┌───────────────────────────┐
│ Shop app (React) │◄─────────►│ Session server        │◄──────►│ Gemini Live  (voice)      │
│ Assistant widget │ WebSocket │  tools, guards, dish  │        │ Gemini Flash (planner,    │
│ (Lit component)  │           │  planner, safety      │        │   safety), Flash-Lite,    │
│ WebAuthn         │           ├───────────────────────┤        │   Embedding, Speech       │
└──────────────────┘           │ Demo store            │        └───────────────────────────┘
        │ fingerprint          │  catalogue, cart,     │
        └─────────────────────►│  checkout, payment    │   UCP for catalogue and checkout,
                               └───────────────────────┘   AP2 signed mandates for payment
```

| Part | Tech |
|---|---|
| Shop app | React 18, Vite, TypeScript |
| Assistant widget | Lit web component, Web Audio, WebSocket, WebAuthn |
| Session server | Python 3.12, FastAPI, Gemini Live API (Google Gen AI SDK on Vertex AI) |
| Demo store | Python 3.12, FastAPI, UCP catalogue/cart/checkout, AP2 mandates (ES256), py-webauthn |
| Google Cloud | Vertex AI (Gemini Live, Flash, Flash-Lite, Embedding), Cloud Run, Artifact Registry, Cloud Build |
| Quality | pytest, Vitest, Playwright, ruff, a safety test suite |

## Repo layout

```text
contracts/        JSON Schemas: the single source of truth for tools, domain objects and widget messages
prompts/          system instruction and rule files for the assistant
services/
  session-server/ voice session, tools, guards, dish planner, safety
  demo-store/     demo grocery store (UCP) with fingerprint payment
packages/
  assistant-widget/  the <talktobuy-assistant> web component
apps/
  shop/           the React shop that embeds the widget
deployment/       one-command deployment to Google Cloud Run (see below)
scripts/          type generation and helper scripts
```

## Run it locally

You need Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20+ and a Google Cloud project with the Vertex AI
API enabled.

```bash
cp .env.example .env              # set GCP_PROJECT to your project
gcloud auth application-default login
uv sync --all-packages
npm install
make dev                          # store :3000, session server :8080, shop :5173
```

Open http://localhost:5173 and tap the **Talk** button. On Windows use `./scripts/tasks.ps1 dev`.

Tests:

```bash
make test           # Python and JavaScript tests
make test-safety    # the safety suite
```

## Deploy on Google Cloud Run

Two Cloud Run services: **talktobuy-ui** (the shop, served by nginx) and **talktobuy-backend** (session server
and demo store in one container). In `deployment/config.ps1` set your project and account, then:

```powershell
gcloud auth login --account=<you@example.com>
powershell -ExecutionPolicy Bypass -File deployment/deploy.ps1
```

It enables the APIs, builds both images in Cloud Build, deploys both services, and runs a smoke test on the live
address. Details are in [`deployment/README.md`](deployment/README.md).

## Safety and privacy

- Payment is approved only with a fingerprint on the shop's own payment screen.
- No audio, video or transcripts are stored.
- Items the assistant infers (from a recipe, a camera or a past order) are added only after a clear yes.
- No health claims, and health never blocks shopping.
- Sessions have an idle timeout and a time cap, and the public demo has usage limits.




