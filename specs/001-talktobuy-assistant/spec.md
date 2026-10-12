# Feature Specification: TalkToBuy Conversational Shopping Assistant (MVP)

**Feature Branch**: `001-talktobuy-assistant`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "TalkToBuy — an agentic conversational shopping assistant that shopping
apps embed: a live avatar that listens, looks, plans and fills the cart, then checks out after one
approval from the shopper. Designed first for older shoppers; demo in Hindi with English
translations. Source: artifacts/reports/Agentic Shopping Assistant — Hackathon Requirements.pdf"

## User Scenarios & Testing *(mandatory)*

The primary persona is **Ghanshyam ji**, an older shopper (around 65+) with little app experience
who may have weaker eyesight, hearing or hand control. Secondary users are everyday shoppers
(busy, hands full, or shopping in a second language) and the **shopping app** that embeds the
assistant and keeps its own catalogue, cart, checkout and payments.

Priorities follow the agreed cut order: P1 can never be cut; lower priorities are cut first when
time slips. Safety *rules* (FR-030 to FR-035) apply in every story regardless of whether the
safety *scene* (User Story 5) is demonstrated.

### User Story 1 - Spoken shopping list into the cart (Priority: P1) — the gate

Ghanshyam ji opens the shopping app, taps "Talk to the shopkeeper", and says in Hindi: "Two litres
of milk, a paav kilo of tomatoes, and my usual atta." The assistant replies in Hindi while it works,
converts local quantities to real pack sizes, and a large product card appears for each item as
it lands in the cart. The cards on screen are the cart.

**Why this priority**: This is the gate. It proves the conversation, the assistant's actions and
the store work together end to end. Without it nothing else can be demonstrated.

**Independent Test**: Start a fresh session, speak the list, and verify the cart contains two 1 L
packs of toned milk, one 250 g pack of tomatoes and the 5 kg atta from the seeded last order, each
shown as a card, with no typing or tapping beyond starting the conversation.

**Acceptance Scenarios**:

1. **Given** an empty cart, **When** the shopper asks for "two litres of milk", **Then** the cart
   holds two 1 L milk packs and a card for that item is visible within 1 second of the assistant
   mentioning it.
2. **Given** an empty cart, **When** the shopper asks for "a paav kilo of tomatoes", **Then** the
   cart holds 250 g of tomatoes.
3. **Given** a seeded past order containing a specific atta, **When** the shopper asks for "my
   usual atta", **Then** the assistant names that atta and asks for a yes before adding it
   (recalled items need approval).
4. **Given** items in the cart, **When** the shopper says "remove the tomatoes" or "make the milk
   three", **Then** the cart and cards update accordingly and the assistant confirms the change.
5. **Given** the assistant is speaking, **When** the shopper starts talking, **Then** the assistant
   stops within 300 ms and responds to the new input.
6. **Given** a requested item is out of stock, **When** the shopper asks for it, **Then** the
   assistant offers the closest in-stock alternative, says why, and adds it only on a yes.

---

### User Story 2 - Read-back and one-approval checkout (Priority: P1)

With the cart filled, Ghanshyam ji says he is done. The assistant reads back the item count, the
total and the delivery time ("10 items, ₹1,016, delivery between 6 and 7 pm"). He says yes, the
shopping app's own payment step opens, and one fingerprint places the order. The assistant speaks
and shows the confirmation and delivery time.

**Why this priority**: Completing an order alone is the core outcome the MVP must prove. Without
checkout, the cart is only a list.

**Independent Test**: With a seeded cart, ask to check out; verify the spoken and on-screen
read-back exactly match the cart total and delivery slot, that the order is placed only after the
shopper's yes and a single approval in the payment step, and that a confirmation with delivery
time is spoken and shown.

**Acceptance Scenarios**:

1. **Given** a cart of 10 products totalling ₹1,016, **When** the shopper asks to check out,
   **Then** the assistant reads back "10 items", "₹1,016" and the delivery window, matching the
   cart exactly.
2. **Given** a read-back, **When** the shopper says yes, **Then** the app's payment step asks for
   one approval, and no order exists until that approval is given.
3. **Given** the payment step, **When** the shopper approves once, **Then** the order is placed (in
   test mode) and the order confirmation and delivery time are spoken and displayed.
4. **Given** a read-back, **When** the shopper says no or asks to change something, **Then** no
   checkout is started and the conversation returns to editing the cart.
5. **Given** any point in the conversation, **When** the shopper says "yes, pay" by voice, **Then**
   the order is still not placed without the approval in the payment step.

---

### User Story 3 - A goal turned into a list (Priority: P2)

Ghanshyam ji says: "I want to bake a chocolate cake. I have sugar and baking soda." The assistant
asks at most two short questions that change the list (how big? eggless?). It then shows the whole
list on screen, with sugar, baking soda and the milk already in the cart struck through and
explained, and reads it out. He can remove or swap items; on his yes, all remaining items are added
at once.

**Why this priority**: Goal-to-list planning is the main differentiator from existing voice
ordering, which only takes orders. It is not in the cut list.

**Independent Test**: With milk already in the cart, state the cake goal with sugar and baking
soda on hand, answer "small" and "eggless", and verify the displayed list strikes through sugar,
baking soda and milk, maps every remaining item to a real product and pack size, and that six
items (maida, cocoa powder, butter, condensed milk, baking powder, 7-inch cake tin) are added in
one step after a yes.

**Acceptance Scenarios**:

1. **Given** the shopper states a goal, **When** the size or eggless choice would change the list,
   **Then** the assistant asks at most two short questions before proposing a list.
2. **Given** the shopper said they have sugar and baking soda, and milk is in the cart, **When** the
   list is shown, **Then** those three appear struck through with a short reason each.
3. **Given** an ingredient amount smaller than any pack, **When** the list is built, **Then** the
   smallest available pack is chosen.
4. **Given** the list is shown, **When** the shopper removes or swaps an item, **Then** the list
   updates before anything is added.
5. **Given** the list is shown, **When** the shopper says yes, **Then** all non-struck items are
   added together and appear as cards; nothing is added before that yes.

---

### User Story 4 - Reorder by showing an empty packet (Priority: P2)

Ghanshyam ji holds an empty biscuit packet up to the camera and says it has run out. The assistant
names the product it recognises, asks whether to add another pack, and adds the same product on a
yes.

**Why this priority**: It shows the assistant can see what the shopper shows it, which no current
voice ordering does. It is the last scene to cut.

**Independent Test**: Hold the demo biscuit packet to the camera and verify the assistant names
the correct catalogue product on the first try, asks before adding, and adds exactly that product.

**Acceptance Scenarios**:

1. **Given** the camera is on, **When** the shopper shows the demo packet and says it has run out,
   **Then** the assistant names the matching catalogue product and asks before adding.
2. **Given** the assistant asked, **When** the shopper says yes, **Then** one pack of that exact
   product is added and shown as a card.
3. **Given** the assistant is not confident of the match, **When** a packet is shown, **Then** it
   says what it thinks it sees and asks the shopper to confirm or describe it, and adds nothing on
   its own.

---

### User Story 5 - Warning signs stop the sale (Priority: P3)

Ghanshyam ji says: "I fell yesterday and my leg is numb. Can I get some medicine?" The assistant
shows no products, gently suggests seeing a doctor, and asks whether he would like his family to
be told. It tells family only if he agrees.

**Why this priority**: The safety rules are non-negotiable in every story; this scene demonstrates
them on stage. Per the cut order the scene may be dropped from the demo, but the behaviour may not.

**Independent Test**: In any session state, say a message containing a warning sign and verify, in
every rehearsal, that no product cards appear, a doctor is suggested, and family is notified only
after an explicit yes.

**Acceptance Scenarios**:

1. **Given** any session, **When** the shopper mentions a recent fall, numbness or weakness, sudden
   severe pain, fever or bladder problems, **Then** no products are shown or added and a doctor is
   suggested.
2. **Given** a warning sign was raised, **When** the assistant offers to tell family and the
   shopper says yes, **Then** the linked family member is informed and the shopper hears a
   confirmation.
3. **Given** a warning sign was raised, **When** the shopper declines, **Then** nobody is
   contacted.
4. **Given** a request for medicine without warning signs, **When** the shopper asks, **Then** the
   assistant explains it cannot help with medicines and shows no medicine or supplement.

---

### User Story 6 - Choosing the pace, and "just order my usual" (Priority: P4)

At the start, the assistant asks one question: step by step, or quick? In **guided** mode it shows
one card at a time, reads each item back and confirms each step. In **quick** mode it acts, then
summarises once. The shopper can change pace at any time ("slow down" → guided; "just order my
usual" → quick). In quick mode, "just order my usual" fills the cart from the last order,
summarises it once and asks for confirmation.

**Why this priority**: Pace keeps the same assistant usable for both older and confident shoppers.
The guided path is used in the main demo; quick mode is the first thing cut if time slips.

**Independent Test**: Start a session, answer "quick", say "just order my usual", and verify the
cart is filled from the seeded order with a single summary and confirmation; then say "slow down"
and verify the assistant switches to guided behaviour and says so.

**Acceptance Scenarios**:

1. **Given** a new session, **When** the conversation starts, **Then** the assistant asks once
   whether to go step by step or quick, and never asks the shopper's age.
2. **Given** guided pace, **When** items are added, **Then** each is shown, read back and confirmed
   one at a time.
3. **Given** quick pace, **When** the shopper says "just order my usual", **Then** the last order's
   items are proposed, summarised once, and added on a single yes.
4. **Given** any pace, **When** the shopper says "slow down", **Then** pace becomes guided and the
   assistant says so.
5. **Given** quick pace, **When** the shopper asks for a repeat or corrects the assistant twice,
   **Then** pace switches to guided and the assistant says so.

---

### User Story 7 - Help with a described problem (Priority: P5)

The shopper describes a non-urgent everyday problem ("my knees hurt when I sit on the floor"). The
assistant shows at most three ordinary retail products (for example a cushion or a low stool) and
explains each in one or two sentences drawn only from the product listing, without any health
claim.

**Why this priority**: Useful and differentiating, but marked as a "Should" and second in the cut
order.

**Independent Test**: Run a set of problem descriptions and verify each response shows at most
three non-medicine products, each explanation is traceable to its listing text, and none states a
health outcome.

**Acceptance Scenarios**:

1. **Given** a problem without warning signs, **When** the shopper describes it, **Then** at most
   three retail products are shown, each with a one- or two-sentence explanation from its listing.
2. **Given** the shopper shares a health detail, **When** the assistant would remember it beyond
   the current answer, **Then** it asks for consent first and stores nothing without it.
3. **Given** a product whose listing is silent on a feature, **When** the shopper asks about that
   feature, **Then** the assistant says the listing does not say, rather than guessing.

---

### Edge Cases

- The shopper speaks while a card is still loading, or interrupts a read-back: the assistant stops,
  handles the new input, and the cart stays consistent.
- An action takes longer than 2 seconds: the assistant says a short holding line instead of going
  silent.
- An ambiguous quantity ("some tomatoes") or ambiguous product ("biscuits" with several brands): the
  assistant asks one short question only if the answer changes the cart; otherwise it chooses the
  usual or most common pack and says so.
- A quantity that does not map exactly to packs ("one and a half litres"): the assistant proposes
  the nearest sensible pack combination and says what it chose.
- The shopper offers an OTP, PIN or password ("my PIN is…"): the assistant refuses, says it never
  needs one, and does not repeat or store it.
- Someone (or something on screen) claims to be the assistant outside the app: the assistant's
  fixed limits (lives only in the app, never asks for secrets) are stated if asked.
- Bandwidth drops mid-session: the assistant switches to audio-only automatically and the full flow
  continues; the shopper can also switch manually at any time.
- The camera is denied or unavailable: the camera reorder is not offered, and the shopper can
  describe the product by voice instead.
- The cart is empty when the shopper asks to check out: the assistant says so and offers help.
- An item becomes out of stock between adding and checkout: the read-back flags it and offers the
  closest alternative before the total is confirmed.
- The shopper types in the text box instead of speaking: every flow works identically.
- A goal implies a medicine or supplement (e.g., "something for my blood sugar"): no such product
  is offered, and warning-sign rules are checked.
- The session reaches its time cap: the assistant warns before it ends and nothing in the cart is
  lost from the shopping app.

## Requirements *(mandatory)*

### Functional Requirements

**Conversation and presence**

- **FR-001**: Shoppers MUST be able to hold a real-time spoken conversation with a live, lip-synced
  avatar inside the shopping app, started with a single tap.
- **FR-002**: The assistant MUST reply in the shopper's language; the MVP language is Hindi, with
  an English translation shown under each line.
- **FR-003**: Captions of everything said by both sides MUST always be shown; English translation
  lines MUST be switchable off; a text box MUST be available as an alternative to speaking.
- **FR-004**: Shoppers MUST be able to interrupt the assistant mid-sentence, and it MUST stop and
  respond to the new input.
- **FR-005**: The assistant MUST keep talking while it searches, adds or checks out, so there is no
  dead air, and MUST say a short holding line when an action takes longer than 2 seconds.
- **FR-006**: An audio-only mode MUST be available at any time and MUST be used automatically when
  bandwidth is low, with every flow still working.
- **FR-007**: The assistant MUST be able to identify a product the shopper holds up to the camera.
- **FR-008**: The assistant SHOULD use respectful forms of address for elders and the correct
  gendered forms for the shopper in Hindi.
- **FR-009**: On-screen text in the shopper's language MUST come only from what was actually said
  (transcription) and from actual results of the assistant's actions, never from separately
  generated text. English translation lines are machine translations of those same captions, MUST
  be visibly labelled as translations, and MUST NOT be shown as anything the assistant said.
- **FR-010**: A visible "AI assistant" label SHOULD remain on screen for the whole session.

**Shopping and cart**

- **FR-011**: The assistant MUST find products by spoken description, brand, or local product name.
- **FR-012**: The assistant MUST understand local quantities and units (e.g., "paav kilo" = 250 g,
  "half a litre" = 500 ml, "two litres" = two 1 L packs) and map them to available pack sizes.
- **FR-013**: Every item added MUST appear as a large card showing picture, name, local name, size
  and price; the cards on screen MUST be the cart.
- **FR-014**: Shoppers MUST be able to edit the cart by voice: remove an item, change a quantity,
  swap a brand.
- **FR-015**: The assistant MUST add items the shopper explicitly named without asking, and MUST ask
  for a yes before adding any item it inferred (seen on camera, recalled from a past order, or
  proposed by planning).
- **FR-016**: The assistant MUST be able to rebuild the shopper's last order ("my usual") from order
  history.
- **FR-017**: When an item is out of stock, the assistant SHOULD offer the closest in-stock
  alternative and say why.

**Checkout**

- **FR-018**: Before checkout the assistant MUST read back the item count, total and delivery time,
  and these MUST match the cart and chosen delivery slot exactly.
- **FR-019**: Checkout MUST go through the shopping app's own checkout.
- **FR-020**: An order MUST be placed only after a single approval in the shopping app's own payment
  step (fingerprint); a spoken yes alone MUST NOT place an order. The MVP runs in test mode with
  no real money.
- **FR-021**: After the order is placed, the assistant MUST speak and display the order confirmation
  and delivery time.

**Goal-based lists**

- **FR-022**: The assistant MUST turn a stated goal into a list of items with quantities.
- **FR-023**: The assistant MUST ask at most two short questions per goal, and only questions whose
  answers change the list.
- **FR-024**: The assistant MUST leave out what the shopper says they already have and what is
  already in the cart, and MUST say so.
- **FR-025**: Each list item MUST map to a real catalogue product and pack size; when the amount
  needed is less than a pack, the smallest pack MUST be chosen.
- **FR-026**: The whole list, including struck-through items, MUST be shown and read out; the
  shopper MUST be able to remove or swap items before everything is added at once on a single yes.

**Pace**

- **FR-027**: The session MUST hold one pace value, guided or quick, set by a single opening
  question and used to govern how much the assistant explains.
- **FR-028**: Shoppers MUST be able to change pace by voice at any time ("slow down" → guided; "just
  order my usual" → quick). Guided: one card at a time, each item read back, each step confirmed.
  Quick: act, then summarise once.
- **FR-029**: The assistant SHOULD switch to guided, and say so, when the shopper asks for a repeat
  or corrects the assistant twice.

**Product claims and safety**

- **FR-030**: Every product explanation MUST be built only from that product's listing and MUST
  describe features and use, never medical or health outcomes.
- **FR-031**: Products licensed as medicines or supplements MUST be absent from the catalogue the
  assistant can search, excluded by catalogue category.
- **FR-032**: When the shopper reports a warning sign (a recent fall, numbness or weakness, sudden
  severe pain, fever, bladder problems), the assistant MUST show and add no products and MUST
  suggest seeing a doctor.
- **FR-033**: The assistant MUST offer to tell a linked family member about a warning sign and MUST
  do so only after the shopper agrees.
- **FR-034**: When a shopper describes an everyday problem without warning signs, the assistant
  SHOULD show at most three retail products, each explained in one or two sentences.
- **FR-035**: The safety behaviour MUST hold across a regression set of at least 20 tricky health
  prompts, with zero products shown in warning-sign cases.

**Trust and privacy**

- **FR-036**: The assistant MUST exist only inside the shopping app and MUST NOT call, message or
  start contact outside it; in-app reminders are allowed.
- **FR-037**: The assistant MUST NEVER ask for or accept an OTP, PIN or password.
- **FR-038**: Health details MUST be saved only after the shopper agrees.
- **FR-039**: The system MUST collect only what the order needs and MUST NOT ask the shopper's age.
- **FR-040**: Audio and video MUST NOT be stored after the session ends.

**Embedding and demo operation**

- **FR-041**: The assistant MUST be embeddable in a shopping app as a component, using the app's
  catalogue, prices, stock, cart, checkout, payment step, account and order history rather than its
  own copies.
- **FR-042**: The demo store MUST credit its open product-data source and label demo prices as demo
  prices.
- **FR-043**: Session duration and cost MUST be recorded per session, and demo sessions MUST be
  capped at 10 minutes.
- **FR-044**: A seeded session MUST be able to run the full demo without live product search, as a
  reliability fallback.

### Key Entities

- **Shopper**: the person using the assistant; has a language, a pace preference, an optional
  linked family member, and order history. No age is stored.
- **Product**: a catalogue item with name, local name, size, price, currency, picture, category,
  listing (description and usage) and stock status. Category determines medicine/supplement
  exclusion.
- **Cart**: the set of products and quantities the shopper intends to buy; mirrored as cards on
  screen.
- **Goal list**: a proposed set of items derived from a goal, including struck-through items with
  reasons (already have, already in cart), pending the shopper's single approval.
- **Usual order**: the shopper's last order, used to rebuild "my usual" (seeded for the MVP).
- **Session**: one conversation; holds pace, language, cart reference, items the shopper says they
  already have, health-consent flag, any open checkout, duration and cost.
- **Checkout**: an open purchase with total, delivery slot and status; becomes an Order only after
  the shopper's approval in the payment step.
- **Order**: a placed purchase with order ID, items, total and delivery time.
- **Family contact**: a linked person who may be told about a warning sign, only with consent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time older shopper completes the full demo order (spoken list, camera reorder,
  cake list, checkout) alone, with no typing and no help, in under 10 minutes.
- **SC-002**: 100% of spoken items in the demo script land in the cart with the right quantity,
  including 250 g for "paav kilo".
- **SC-003**: The camera reorder adds the correct product on the first try with the demo packet in
  every rehearsal.
- **SC-004**: The cake list leaves out sugar, baking soda and milk and maps every remaining item to a
  real pack size, in every rehearsal.
- **SC-005**: The checkout read-back matches the cart total and delivery slot exactly in 100% of
  runs, and every order requires exactly one approval.
- **SC-006**: In 100% of warning-sign prompts (across all rehearsals and the 20+ prompt regression
  set) zero products are shown and a doctor is suggested; zero product explanations contain a
  health claim.
- **SC-007**: The assistant starts replying within 1.5 seconds of the shopper finishing speaking,
  stops within 300 ms of being interrupted, and shows a product card within 1 second of mentioning
  it.
- **SC-008**: All card text is at least 20 px with WCAG AA contrast, and all tap targets are at least
  48×48 px.
- **SC-009**: The complete demo flow succeeds in audio-only mode.
- **SC-010**: A native Hindi speaker has approved every scripted line, including gendered and
  respectful forms.
- **SC-011**: A confident shopper using quick mode completes "just order my usual" through to the
  approval step in under 1 minute.

## Assumptions

- The MVP runs against our own small demo store (300–500 grocery items from an open product
  dataset) shown inside a plain shopping app, not a real platform's production systems.
- Checkout runs in test mode; no real payment is taken. The fingerprint approval is shown in the
  app's payment step.
- Demo prices are set by us so that the scripted cart (10 products) totals ₹1,016; "item count" in
  the read-back means distinct products, not units.
- Delivery: the assistant offers the earliest available slot (6–7 pm in the demo) and the shopper
  may ask for another.
- "My usual" relies on one seeded past order for the demo persona; no other cross-session memory.
- The linked family member is seeded for the demo persona, and "telling family" is an in-app
  notification shown on a family view inside our app (not an SMS, call or external message), so it
  stays within the "only inside the app" rule.
- The demo biscuit packet is in the catalogue with photos from several angles.
- The demo is run in Hindi only; switching languages between two speakers is out of scope.
- Native mobile SDKs, order summaries to family, medicines and supplements, and our own speech,
  avatar or recommendation models are out of scope.
- The demo machine has a camera, microphone and a network connection; poor venue networks are
  handled by audio-only mode, the seeded session and a recorded backup run.
