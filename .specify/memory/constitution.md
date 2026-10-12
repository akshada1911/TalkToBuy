<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Modified principles: none (initial ratification)
- Added principles: I. Approval Before Money or Guesses; II. No Medical Claims, Safety Stops the
  Sale (NON-NEGOTIABLE); III. Scam-Resistant Trust Boundaries; IV. Elder-First Accessibility;
  V. Portability Through Owned Interfaces; VI. Protect the Gate
- Added sections: Technology & Data Constraints; Development Workflow & Quality Gates; Governance
- Removed sections: none
- Templates: plan/spec/tasks templates read this file at runtime; no template edits required
- Deferred TODOs: none
- Source: artifacts/reports/Agentic Shopping Assistant — Hackathon Requirements.pdf (2026-10-09)
-->

# TalkToBuy Constitution

## Core Principles

### I. Approval Before Money or Guesses

The assistant MAY act on its own when the shopper's intent is explicit: searching the catalogue,
comparing pack sizes, converting local units, and adding an item the shopper named (always shown
as a card). It MUST ask the shopper for an explicit yes before:

- adding any item it inferred (recognised on camera, recalled from a past order, or produced by
  goal-to-list planning);
- adding a goal-based list (the whole list is confirmed once, after it is shown and read out);
- telling a family member anything.

It MUST NEVER place an order or pay on its own. Clarifying questions are asked only when the answer
changes the list, and at most two per goal.

Rationale: the product's value is agency; its trust depends on the shopper never being surprised
by what was bought.

### II. No Medical Claims, Safety Stops the Sale (NON-NEGOTIABLE)

- Every product explanation MUST be built only from that product's listing (description, usage)
  and MUST describe features and use, never health outcomes.
- Products licensed as medicines or supplements MUST be excluded by catalogue category at import
  time, not by shelf, section or keyword.
- When the shopper reports a warning sign (a recent fall, numbness or weakness, sudden severe pain,
  fever, bladder problems), the assistant MUST show no products, suggest a doctor, and offer, but
  never perform without consent, to tell family.
- A regression set of at least 20 tricky health prompts MUST pass before every demo build.

Rationale: a single health claim is a legal and trust failure for both us and the shopping app.

### III. Scam-Resistant Trust Boundaries

- The assistant exists only inside the shopping app. It MUST NOT call, message or start contact
  outside it (in-app reminders are allowed).
- It MUST NEVER ask for or accept an OTP, PIN or password, and MUST refuse if offered one.
- Payment is approved only in the shopping app's own payment step (fingerprint), never by voice
  alone.
- A visible "AI assistant" label stays on screen throughout.
- Collect only what the order needs. No age question. Health details are saved only after
  explicit consent. No audio or video is stored after the session.
- Model and service credentials MUST never reach the browser.

Rationale: a friendly face that handles money is exactly what scammers imitate; fixed, explainable
limits are the defence.

### IV. Elder-First Accessibility

- Design for the older shopper first (around 65+, weaker eyesight, hearing or hand control).
- Product card text at least 20 px with WCAG AA contrast; tap targets at least 48×48 px.
- Captions of both sides are always on; translation lines can be switched off; a text box is
  always available as an alternative to speech.
- The shopper can interrupt at any time; the assistant never leaves dead air while it works.
- Pace (`guided` or `quick`) is the shopper's choice, changeable by voice; the system never infers
  it from age.
- Every scripted or prompt-level Hindi line MUST be reviewed by a native speaker, including
  respectful and gendered forms.

Rationale: a system simple enough for an older first-time shopper is faster for everyone else.

### V. Portability Through Owned Interfaces

- Core logic calls only interfaces we own (live conversation and avatar, tools, commerce, payment
  approval, product search, hosting and data). Vendor SDKs live only inside adapters.
- The tool set is defined once as provider-neutral JSON Schema; prompts are stored as
  provider-neutral files; vendor choices (avatar, voice, model) are configuration.
- The shopping app keeps its catalogue, cart, checkout and payments; the assistant reaches them
  only through the tools (UCP or a thin app adapter).
- The MVP builds exactly one implementation per interface.

Rationale: the business pitch is "embed us on your stack"; that claim must be true in the code.

### VI. Protect the Gate

- The gate is a spoken request that adds a real item to the cart through a tool call, end to end.
  It is never cut and is reached before any other scenario is polished.
- When time slips, cut scope in this order: quick mode → problem-based suggestions → the
  safety-check scene (its rules stay in the prompt) → camera reorder.
- No new scope after code freeze; buffer days are for hardening, not features.
- Simplest thing that demos reliably wins (YAGNI); every added component must name the
  requirement it serves.

Rationale: an unfinished demo is the largest risk; scope discipline is a principle, not a wish.

## Technology & Data Constraints

- Hackathon stack (Google): Gemini Live with Live Avatar for the conversation; a session server
  on Cloud Run that holds the live session, holds session state and runs every tool; Firestore,
  Cloud Storage, Firebase Hosting and Secret Manager for data, assets, hosting and secrets.
- Commerce: our own small demo store exposing a UCP capability manifest at `/.well-known/ucp`
  with catalogue, cart and checkout; AP2 checkout mandate in test mode only. Fallback, if UCP
  slips: a plain REST store behind the same tools.
- Catalogue: 300–500 grocery items from Open Food Facts (ODbL data, CC BY-SA images), credited
  in the app; demo prices are set by us and labelled as demo prices; local names and non-food
  items added by hand.
- The assistant's spoken output is audio; on-screen text comes from transcription and tool
  results, never from model text replies.
- Session cost and duration are logged per session; demo sessions are capped at 10 minutes.
- Out of scope for the MVP: real payments, production platform integration, native mobile SDKs,
  cross-session memory beyond the seeded usual order, multi-speaker language switching, family
  order summaries, medicines and supplements, our own speech, avatar or recommendation models.

## Development Workflow & Quality Gates

- Milestones (October 2026): gate by end of Tue 13; code freeze end of Fri 16; deploy and
  rehearse Sat 17; submit by end of Sun 18.
- Every feature follows Spec Kit: specify → (clarify) → plan → tasks → implement. Plans MUST
  include a Constitution Check against Principles I–VI.
- Tool contracts (the nine tools, product record, session state) are covered by contract tests;
  the safety regression set (Principle II) runs before every demo build.
- Demo acceptance (all MUST pass in rehearsal): every spoken item lands with the right quantity
  (including 250 g for "paav kilo"); the camera reorder is correct on the first try with the demo
  packet; the cake list leaves out sugar, baking soda and milk and maps every item to a real pack;
  the read-back matches cart total and delivery slot exactly; checkout completes in test mode with
  one approval; the safety check shows no products in every rehearsal; a native speaker has
  approved every Hindi line.
- Reliability: keep a recorded backup run and a seeded session that needs no live search; the
  full flow MUST work in audio-only mode.

## Governance

This constitution supersedes other practices for TalkToBuy. Any spec, plan or task that conflicts
with it MUST either change or record a justified exception in the plan's Complexity Tracking
section. Amendments are proposed as a change to this file, agreed by the team, and versioned:
MAJOR for removing or redefining a principle, MINOR for adding a principle or materially expanding
guidance, PATCH for clarifications. Reviews verify compliance with Principles I–III on every change
that touches tools, prompts, checkout or catalogue import. The source requirements document is
`artifacts/reports/Agentic Shopping Assistant — Hackathon Requirements.pdf`.

**Version**: 1.0.0 | **Ratified**: 2026-10-09 | **Last Amended**: 2026-10-09
