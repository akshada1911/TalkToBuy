import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

/**
 * The shop ⇄ assistant hand-off, end to end, without the AI: the browser talks to a scripted
 * stand-in for the session server (Playwright's WebSocket routing), and everything else is real:
 * the demo store's catalogue, checkout, address and WebAuthn payment endpoints.
 *
 *   tap ADD → the assistant is asked and the cart answers → View cart → Check out → address cards →
 *   read-back → "yes" → the payment screen → fingerprint (virtual authenticator) → the store
 *   verifies the mandate and completes → the order screen.
 *
 * Needs the demo store running and proxied by the shop dev server (`/demo`, `/payment`). Opt in with
 * TTB_STORE=1; TTB_STORE_URL is where the store listens for the UCP calls (default :3000).
 *
 * Each run registers a new virtual fingerprint with the store, and the store remembers it. Start the
 * store with a throw-away copy of its data (DATA_DIR=...) and SHOP_ORIGIN set to the shop's origin
 * (WebAuthn checks the origin), so a test never leaves a fake credential in the real data folder.
 */
test.skip(process.env.TTB_STORE !== "1", "needs the demo store running (set TTB_STORE=1)");

const STORE = process.env.TTB_STORE_URL ?? "http://localhost:3000";
const UCP = { "UCP-Agent": 'profile="http://session.test/agent-profile.json"' };
const ucpHeaders = () => ({ ...UCP, "Request-Id": crypto.randomUUID(), "Idempotency-Key": crypto.randomUUID() });

interface Product {
  id: string;
  name: string;
  local_name: string;
  size: string;
  price: number;
  image: string;
  image_credit: string;
}

async function createReadyCheckout(request: APIRequestContext, p: Product) {
  const created = await request.post(`${STORE}/ucp/v1/checkout-sessions`, {
    headers: ucpHeaders(),
    data: { currency: "INR", line_items: [{ item: { id: p.id }, quantity: 1 }] },
  });
  expect(created.status()).toBe(201);
  const id = (await created.json()).id as string;
  const put = await request.put(`${STORE}/ucp/v1/checkout-sessions/${id}`, {
    headers: ucpHeaders(),
    data: {
      currency: "INR",
      line_items: [{ item: { id: p.id }, quantity: 1 }],
      fulfillment: { selected_option_id: "earliest" },
      destination: { shopper_id: "u-ghanshyam", address_id: "addr-home" },
    },
  });
  expect(put.status()).toBe(200);
  const body = await put.json();
  expect(body.status).toBe("ready_for_complete");
  const slot = body.fulfillment.methods[0].groups[0].options.find((o: { id: string }) => o.id === body.fulfillment.methods[0].groups[0].selected_option_id);
  return { id, slot: slot.metadata as { label_hi: string; label_en: string }, id_slot: slot.id as string };
}

async function installAssistantStandIn(page: Page, request: APIRequestContext, product: Product) {
  const log: string[] = [];
  await page.route("**/v1/demo-ticket", (r) => r.fulfill({ json: { ticket: "t", expires_in: 600 } }));
  await page.routeWebSocket(/\/v1\/session/, (ws) => {
    const send = (m: unknown) => ws.send(JSON.stringify(m));
    const cart = (qty: number) => ({
      type: "cart",
      cart: {
        lines: qty
          ? [{ product: { id: product.id, name: product.name, local_name: product.local_name, size: product.size, price: product.price, image: product.image, image_credit: product.image_credit, in_stock: true }, qty, line_total: product.price * qty }]
          : [],
        item_count: qty ? 1 : 0,
        total: product.price * qty,
      },
    });
    let qty = 0;
    let checkout: Awaited<ReturnType<typeof createReadyCheckout>> | null = null;
    send({ type: "state", pace: "quick", media_mode: "audio_only", safety_hold: false, remaining_s: 600 });

    ws.onMessage(async (raw) => {
      if (typeof raw !== "string") return;
      const m = JSON.parse(raw) as { type: string; text?: string; approved?: boolean; mandate?: { checkout_mandate: string; payment_mandate: string } };
      if (m.type === "text" && m.text) {
        log.push(m.text);
        const t = m.text.toLowerCase();
        if (t.includes("add one more") || t.includes("add ")) {
          qty += 1;
          send(cart(qty));
        } else if (t.includes("remove")) {
          qty = Math.max(0, qty - 1);
          send(cart(qty));
        } else if (t.includes("check out")) {
          send({ type: "addresses", addresses: [{ id: "addr-home", label: "Home", text: "Flat 12, Kothrud, Pune 411038" }, { id: "addr-rohit", label: "Rohit's place", text: "B-204, Baner, Pune 411045" }] });
        } else if (t.includes("address chosen")) {
          checkout = await createReadyCheckout(request, product);
          send({
            type: "readback", checkout_id: checkout.id, item_count: 1, total: product.price,
            delivery: { id: checkout.id_slot, label_hi: checkout.slot.label_hi, label_en: checkout.slot.label_en },
            address_text: "Home: Flat 12, Kothrud, Pune 411038", text_hi: "सब ठीक है?", text_en: "Shall I place the order?",
          });
        } else if (t === "yes" && checkout) {
          send({
            type: "payment_request", checkout_id: checkout.id, item_count: 1, total: product.price, currency: "INR",
            delivery: { id: checkout.id_slot, label_hi: checkout.slot.label_hi, label_en: checkout.slot.label_en },
            address_text: "Home: Flat 12, Kothrud, Pune 411038",
          });
        }
      } else if (m.type === "payment_result" && checkout) {
        log.push(`payment_result approved=${m.approved}`);
        if (m.approved && m.mandate) {
          // The store itself verifies the signatures, the amount and the address the shopper approved.
          const done = await request.post(`${STORE}/ucp/v1/checkout-sessions/${checkout.id}/complete`, {
            headers: ucpHeaders(),
            data: { ap2: { checkout_mandate: m.mandate.checkout_mandate }, payment: { instruments: [{ handler_id: "com.example.card", credential: { token: m.mandate.payment_mandate } }] } },
          });
          log.push(`complete ${done.status()}`);
          if (done.ok()) {
            const order = (await done.json()).order;
            send({ type: "order", order_id: order.id, delivery: { id: checkout.id_slot, label_hi: checkout.slot.label_hi, label_en: checkout.slot.label_en } });
            send(cart(0));
          }
        }
      }
    });
  });
  return log;
}

test("browse, add, check out, pay with the fingerprint, and see the order", async ({ page, request }) => {
  const product = ((await (await request.get(`${STORE}/demo/catalog?limit=1`)).json()).items[0]) as Product;
  const log = await installAssistantStandIn(page, request, product);

  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });

  await page.goto("/?lang=en");
  await page.locator("nav").getByRole("button", { name: "Browse", exact: true }).click();
  const card = page.locator(".pcard").first();
  await expect(card).toBeVisible();

  // ADD asks the assistant (the voice sheet opens); the cart answers and the stepper appears.
  await card.getByRole("button", { name: /^Add / }).click();
  await expect(page.getByText("AI assistant")).toBeVisible();
  await expect(card.locator(".stepper .qty")).toHaveText("1", { timeout: 20_000 });
  await expect(page.locator(".cartbar")).toContainText(`₹${product.price}`);

  // The stepper's + asks for one more (the sheet is closed first: it covers the lower list).
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await card.getByRole("button", { name: /Add one more/ }).click();
  await expect(card.locator(".stepper .qty")).toHaveText("2", { timeout: 20_000 });
  await card.getByRole("button", { name: /Remove one/ }).click();
  await expect(card.locator(".stepper .qty")).toHaveText("1", { timeout: 20_000 });

  // The cart screen shows the assistant's cart. Check out → the assistant asks for the address.
  await page.getByRole("button", { name: "Close", exact: true }).click(); // the voice sheet
  await page.locator(".cartbar").getByRole("button", { name: "View cart" }).click();
  await expect(page.getByText("Item total")).toBeVisible();
  await page.getByRole("button", { name: /Check out/ }).click();
  const picker = page.locator("ttb-address-picker");
  await expect(picker).toBeVisible({ timeout: 20_000 });
  await picker.getByRole("button", { name: /Deliver here/ }).first().click();

  // Read-back → "yes" typed to the assistant → the shop's own payment screen.
  await expect(page.locator("ttb-readback")).toBeVisible({ timeout: 20_000 });
  const input = page.getByPlaceholder(/Type here/);
  await input.fill("yes");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".topbar-title b", { hasText: "Payment" })).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".screen .note", { hasText: "Flat 12, Kothrud, Pune 411038" })).toBeVisible();

  // The fingerprint: registers (first time), asserts, and the store verifies the mandate.
  await page.getByRole("button", { name: /with fingerprint/ }).click();
  const track = page.locator(".track-card");
  await expect(track.getByText("Order placed")).toBeVisible({ timeout: 30_000 });
  await expect(track.getByText(/Order ord_/)).toBeVisible();
  expect(log.some((l) => l.startsWith("complete 200"))).toBe(true);

  // Back home: the cart is empty again, and Orders is now available.
  await page.getByRole("button", { name: "Back to home" }).last().click();
  await expect(page.locator(".cartbar")).toHaveCount(0);
  await expect(page.locator("nav").getByRole("button", { name: "Orders", exact: true })).toBeEnabled();
});
