import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

/**
 * One cart, two ways to fill it and to check out, end to end. The browser talks to a scripted
 * stand-in for the session server (Playwright's WebSocket routing); everything else is real: the
 * demo store's catalogue, cart, address, checkout and WebAuthn payment endpoints.
 *
 *   1. By tapping only (no assistant, no WebSocket): ADD → stepper → Clear cart → ADD → Check out →
 *      address and slot → payment → fingerprint → the store verifies and completes → order.
 *   2. The same cart with the assistant: tap ADD → open the shopkeeper (it connects with the cart's id)
 *      → the assistant adds to that same cart → the shop shows it → check out by voice → fingerprint →
 *      order. Then "cancel my order" by voice empties the cart and the shop shows it.
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
const ucpHeaders = () => ({
  "UCP-Agent": 'profile="http://session.test/agent-profile.json"',
  "Request-Id": crypto.randomUUID(),
  "Idempotency-Key": crypto.randomUUID(),
});

interface Product {
  id: string;
  name: string;
  price: number;
}
interface StoreCart {
  id: string;
  status: string;
  lines: { product: { id: string }; qty: number }[];
  item_count: number;
  total: number;
  slot: { id: string; label_hi: string; label_en: string } | null;
}

const cartMessage = (c: StoreCart, id: string | null) => ({
  type: "cart",
  cart: { lines: c.lines, item_count: c.item_count, total: c.total },
  cart_id: id,
});

const lineMap = (c: StoreCart) => Object.fromEntries(c.lines.map((l) => [l.product.id, l.qty]));
const toLines = (m: Record<string, number>) => Object.entries(m).map(([product_id, qty]) => ({ product_id, qty }));

async function storeCart(request: APIRequestContext, id: string): Promise<StoreCart> {
  const res = await request.get(`${STORE}/demo/carts/${id}`);
  expect(res.ok()).toBe(true);
  return (await res.json()) as StoreCart;
}

/** A scripted stand-in for the assistant, working on the real store's cart. */
async function installAssistantStandIn(page: Page, request: APIRequestContext, extra: Product) {
  const log: string[] = [];
  await page.route("**/v1/demo-ticket", (r) => r.fulfill({ json: { ticket: "t", expires_in: 600 } }));
  await page.routeWebSocket(/\/v1\/session/, (ws) => {
    const send = (m: unknown) => ws.send(JSON.stringify(m));
    const cartId = new URL(ws.url()).searchParams.get("cart");
    log.push(`connect cart=${cartId}`);
    send({ type: "state", pace: "quick", media_mode: "audio_only", safety_hold: false, remaining_s: 600 });
    const push = async () => {
      if (!cartId) return;
      const c = await storeCart(request, cartId);
      // like the server: a finished cart is no longer the assistant's cart
      if (c.status === "incomplete" || c.status === "ready_for_complete") send(cartMessage(c, cartId));
    };
    void push(); // like the server: the cart that was picked up is shown at once

    ws.onMessage(async (raw) => {
      if (typeof raw !== "string" || !cartId) return;
      const m = JSON.parse(raw) as { type: string; text?: string; approved?: boolean; mandate?: { checkout_mandate: string; payment_mandate: string } };
      if (m.type === "cart_sync") {
        log.push("cart_sync");
        await push();
      } else if (m.type === "text" && m.text) {
        log.push(m.text);
        const t = m.text.toLowerCase();
        const cart = await storeCart(request, cartId);
        if (t.includes("cancel")) {
          // The assistant's cancel tool: the store cart is cancelled, and the shop is told there is no cart.
          const live = (await page.evaluate(() => localStorage.getItem("ttb-cart"))) ?? cartId; // the shop's current cart
          const done = await request.post(`${STORE}/ucp/v1/checkout-sessions/${live}/cancel`, { headers: ucpHeaders(), data: {} });
          expect(done.ok()).toBe(true);
          send(cartMessage({ ...cart, lines: [], item_count: 0, total: 0 }, null));
        } else if (/\badd\b/.test(t)) {
          // Voice adds an item to the SAME cart (it keeps what was tapped).
          const lines = { ...lineMap(cart), [extra.id]: (lineMap(cart)[extra.id] ?? 0) + 1 };
          const put = await request.put(`${STORE}/demo/carts/${cartId}`, { data: { lines: toLines(lines) } });
          expect(put.ok()).toBe(true);
          send(cartMessage((await put.json()) as StoreCart, cartId));
        } else if (t.includes("check out")) {
          send({ type: "addresses", addresses: [{ id: "addr-home", label: "Home", text: "Flat 12, Kothrud, Pune 411038" }] });
        } else if (t.includes("address chosen")) {
          const put = await request.put(`${STORE}/demo/carts/${cartId}`, {
            data: { lines: toLines(lineMap(cart)), slot_id: "earliest", address_id: "addr-home" },
          });
          const ready = (await put.json()) as StoreCart;
          expect(ready.status).toBe("ready_for_complete");
          send({
            type: "readback", checkout_id: cartId, item_count: ready.item_count, total: ready.total,
            delivery: ready.slot, address_text: "Home: Flat 12, Kothrud, Pune 411038", text_hi: "सब ठीक है?", text_en: "Shall I place the order?",
          });
        } else if (t === "yes") {
          const ready = await storeCart(request, cartId);
          send({
            type: "payment_request", checkout_id: cartId, item_count: ready.item_count, total: ready.total, currency: "INR",
            delivery: ready.slot, address_text: "Home: Flat 12, Kothrud, Pune 411038",
          });
        }
      } else if (m.type === "payment_result" && m.approved && m.mandate) {
        const done = await request.post(`${STORE}/ucp/v1/checkout-sessions/${cartId}/complete`, {
          headers: ucpHeaders(),
          data: { ap2: { checkout_mandate: m.mandate.checkout_mandate }, payment: { instruments: [{ handler_id: "com.example.card", credential: { token: m.mandate.payment_mandate } }] } },
        });
        log.push(`complete ${done.status()}`);
        if (done.ok()) {
          const order = (await done.json()).order;
          const cart = await storeCart(request, cartId);
          send({ type: "order", order_id: order.id, delivery: cart.slot ?? { id: "slot", label_hi: "", label_en: "" } });
          send(cartMessage({ ...cart, lines: [], item_count: 0, total: 0 }, null));
        }
      }
    });
  });
  return log;
}

test("one cart: tap or talk, check out either way", async ({ page, request }) => {
  const items = (await (await request.get(`${STORE}/demo/catalog?limit=2`)).json()).items as Product[];
  const [first, second] = items;
  const log = await installAssistantStandIn(page, request, second);
  let sockets = 0;
  page.on("websocket", (ws) => {
    if (ws.url().includes("/v1/session")) sockets++; // not the dev server's own hot-reload socket
  });

  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
  const tab = (name: string) => page.locator("nav").getByRole("button", { name, exact: true });
  const card = () => page.locator(".pcard").first();
  const viewCart = () => page.locator(".cartbar").getByRole("button", { name: "View cart" });

  // ------------------------------------------------------------ 1. by tapping only
  await page.goto("/?lang=en");
  await tab("Browse").click();
  await expect(card()).toBeVisible();
  await card().getByRole("button", { name: /^Add / }).click();
  await expect(card().locator(".stepper .qty")).toHaveText("1");
  await card().getByRole("button", { name: /Add one more/ }).click();
  await expect(card().locator(".stepper .qty")).toHaveText("2");
  await card().getByRole("button", { name: /Remove one/ }).click();
  await expect(card().locator(".stepper .qty")).toHaveText("1");
  await expect(page.locator(".cartbar")).toContainText(`₹${first.price}`);
  expect(sockets, "adding by tapping never starts the assistant").toBe(0);

  // Clear cart: the items fade out, "Cart cleared" shows, and the cart is empty.
  await viewCart().click();
  await page.getByRole("button", { name: "Clear cart" }).click();
  await expect(page.getByText("Cart cleared").first()).toBeVisible();
  await expect(page.getByText("Your cart is empty")).toBeVisible({ timeout: 5_000 });

  // Add again and check out by tapping: address, slot, payment, fingerprint, order.
  await page.getByRole("button", { name: "Browse", exact: true }).click(); // the empty cart's own button
  await card().getByRole("button", { name: /^Add / }).click();
  await expect(card().locator(".stepper .qty")).toHaveText("1");
  await viewCart().click();
  await page.getByRole("button", { name: "Check out", exact: true }).click();
  await expect(page.locator(".topbar-title b", { hasText: "Checkout" })).toBeVisible();
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page.locator(".topbar-title b", { hasText: "Payment" })).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".screen .note", { hasText: "Kothrud" })).toBeVisible();
  await page.getByRole("button", { name: /with fingerprint/ }).click();
  const track = page.locator(".track-card");
  await expect(track.getByText("Order placed")).toBeVisible({ timeout: 30_000 });
  await expect(track.getByText(/Order ord_/)).toBeVisible();
  expect(sockets, "checking out by tapping never starts the assistant").toBe(0);
  await page.getByRole("button", { name: "Back to home" }).last().click();
  await expect(page.locator(".cartbar")).toHaveCount(0);

  // ------------------------------------------------------------ 2. the same cart with the assistant
  await tab("Browse").click();
  await card().getByRole("button", { name: /^Add / }).click(); // a tap: a new cart (the last one was ordered)
  await expect(card().locator(".stepper .qty")).toHaveText("1");
  await tab("TalkToBuy").click();
  await expect(page.getByText("AI assistant")).toBeVisible();
  await expect.poll(() => log.find((l) => l.startsWith("connect cart=chk_")), { timeout: 20_000 }).toBeTruthy();
  // The conversation picked up the tapped cart: its panel shows the item.
  await expect(page.locator("ttb-cart-view .rows li")).toHaveCount(1, { timeout: 20_000 });

  // Voice adds to the same cart; the shop's cart shows both.
  await page.getByPlaceholder(/Type here/).fill("please add one more thing");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator("ttb-cart-view .rows li")).toHaveCount(2, { timeout: 20_000 });
  await page.getByRole("button", { name: "End and go back" }).click();
  await expect(page.locator(".cartbar")).toContainText("2 items");

  // A tap while the conversation is running is shown in it at once (cart_sync).
  await card().getByRole("button", { name: /Add one more/ }).click();
  await expect.poll(() => log.includes("cart_sync"), { timeout: 10_000 }).toBe(true);

  // Check out by voice: address cards → read-back → "yes" → payment screen → fingerprint → order.
  await viewCart().click();
  await page.getByRole("button", { name: "Check out by voice instead" }).click();
  const picker = page.locator("ttb-address-picker");
  await expect(picker).toBeVisible({ timeout: 20_000 });
  await picker.getByRole("button", { name: /Deliver here/ }).first().click();
  await expect(page.locator("ttb-readback")).toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder(/Type here/).fill("yes");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.locator(".topbar-title b", { hasText: "Payment" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: /with fingerprint/ }).click();
  await expect(page.locator(".track-card").getByText("Order placed")).toBeVisible({ timeout: 30_000 });
  expect(log.filter((l) => l.startsWith("complete 200")).length).toBe(1);
  await page.getByRole("button", { name: "Back to home" }).last().click();

  // ------------------------------------------------------------ 3. "cancel my order" by voice
  await tab("Browse").click();
  await card().getByRole("button", { name: /^Add / }).click();
  await expect(card().locator(".stepper .qty")).toHaveText("1");
  await viewCart().click();
  await expect(page.getByRole("button", { name: "Clear cart" })).toBeVisible();
  await page.locator(".topbar").getByRole("button", { name: "Order by talking" }).click();
  await page.getByPlaceholder(/Type here/).fill("please cancel my order");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Cart cleared").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Your cart is empty")).toBeVisible({ timeout: 8_000 });
});
