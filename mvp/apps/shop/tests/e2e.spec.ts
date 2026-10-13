import { expect, test, type Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

/**
 * Seeded-mode smoke test (T104). Needs the full stack running: demo store and session server with
 * SEARCH_MODE=seeded, and the shop dev server (or SHOP_URL). Opt in with TTB_E2E=1.
 *
 * Flow: open the shop → open the shopkeeper → drive the scripted list through the text box →
 * assert the cart panel and total → choose the delivery address → read-back → the shop's own
 * payment screen with a WebAuthn virtual authenticator → order placed.
 */
test.skip(process.env.TTB_E2E !== "1", "needs the backend running (set TTB_E2E=1)");

const TURN_TIMEOUT = 45_000;

async function say(page: Page, text: string) {
  const input = page.getByPlaceholder(/लिखकर बताइए/);
  await expect(input).toBeEnabled({ timeout: TURN_TIMEOUT });
  await input.fill(text);
  await page.getByRole("button", { name: /भेजें/ }).click();
}

async function cartLines(page: Page): Promise<number> {
  return page.locator("ttb-cart-view ul.rows[aria-label*='कार्ट का सामान'] li").count();
}

test("scripted text session places a test-mode order", async ({ page }) => {
  // Record cart events and orders for assertions.
  await page.addInitScript(() => {
    const w = window as unknown as { __ttb: { carts: unknown[]; orders: unknown[] } };
    w.__ttb = { carts: [], orders: [] };
    document.addEventListener("ttb:cart-changed", (e) => w.__ttb.carts.push((e as CustomEvent).detail.cart), true);
    document.addEventListener("ttb:order-placed", (e) => w.__ttb.orders.push((e as CustomEvent).detail), true);
  });

  // Virtual platform authenticator with user verification ("fingerprint").
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  });

  await page.goto("/?lang=hi");
  await page.getByRole("button", { name: "TalkToBuy" }).click();
  await expect(page.getByText("AI सहायक")).toBeVisible();

  // Opening question: pace (quickstart row 0).
  await say(page, "धीरे-धीरे, एक-एक करके");
  await expect(page.getByText(/धीरे-धीरे/).first()).toBeVisible({ timeout: TURN_TIMEOUT });

  // Row 1 (typed, row 9): milk and tomatoes are added; the usual atta is asked about first.
  await say(page, "दो लीटर दूध, पाव किलो टमाटर, और मेरा हमेशा वाला आटा");
  await expect.poll(() => cartLines(page), { timeout: TURN_TIMEOUT, intervals: [1000] }).toBeGreaterThanOrEqual(2);
  await say(page, "हाँ");
  await expect.poll(() => cartLines(page), { timeout: TURN_TIMEOUT, intervals: [1000] }).toBeGreaterThanOrEqual(3);

  // The cart panel total equals the sum of its lines.
  const cart = await page.evaluate(() => {
    const w = window as unknown as { __ttb: { carts: { total: number; item_count: number; lines: { line_total: number }[] }[] } };
    return w.__ttb.carts[w.__ttb.carts.length - 1];
  });
  expect(cart.item_count).toBe(3);
  expect(cart.total).toBe(cart.lines.reduce((s, l) => s + l.line_total, 0));
  await expect(page.locator("ttb-cart-view .sum")).toContainText(`₹${cart.total.toLocaleString("en-IN")}`);

  // Row 5: read-back. The assistant asks for the delivery address first; tap the saved "Home" one.
  await say(page, "बस, ऑर्डर कर दो");
  const picker = page.locator("ttb-address-picker");
  await expect(picker).toBeVisible({ timeout: TURN_TIMEOUT });
  await picker.getByRole("button", { name: /यहाँ भेजें/ }).first().click();
  const readback = page.locator("ttb-readback");
  await expect(readback).toBeVisible({ timeout: TURN_TIMEOUT });
  await expect(readback).toContainText(`₹${cart.total.toLocaleString("en-IN")}`);

  // Row 6: yes → the shop's own payment screen → fingerprint.
  await say(page, "हाँ");
  await expect(page.getByRole("heading", { name: /भुगतान/ }).or(page.locator(".topbar-title b", { hasText: "भुगतान" }))).toBeVisible({ timeout: TURN_TIMEOUT });
  await expect(page.getByText("टेस्ट मोड")).toBeVisible();
  await page.getByRole("button", { name: /फ़िंगरप्रिंट से/ }).click();

  // The order screen (tracking is a demo) shows the placed order.
  await expect(page.getByText("ऑर्डर हो गया")).toBeVisible({ timeout: TURN_TIMEOUT });
  const orders = await page.evaluate(() => (window as unknown as { __ttb: { orders: unknown[] } }).__ttb.orders);
  expect(orders.length).toBe(1);
});
