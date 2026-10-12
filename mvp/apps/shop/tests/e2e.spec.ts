import { expect, test, type Page } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

/**
 * Seeded-mode smoke test (T104). Needs the full stack running: demo store and session server with
 * SEARCH_MODE=seeded, and the shop dev server (or SHOP_URL). Opt in with TTB_E2E=1.
 *
 * Flow: open the shop → start the assistant → drive the scripted list through the text box →
 * assert the cart cards and total → read-back → payment step with a WebAuthn virtual
 * authenticator → order confirmation.
 */
test.skip(process.env.TTB_E2E !== "1", "needs the backend running (set TTB_E2E=1)");

const TURN_TIMEOUT = 45_000;

async function say(page: Page, text: string) {
  const input = page.getByPlaceholder(/लिखकर बताइए/);
  await expect(input).toBeEnabled({ timeout: TURN_TIMEOUT });
  await input.fill(text);
  await page.getByRole("button", { name: /भेजें \/ Send/ }).click();
}

async function cartLines(page: Page): Promise<number> {
  return page.locator("ttb-cart-view ul.grid[aria-label*='Cart'] ttb-product-card").count();
}

test("scripted text session places a test-mode order", async ({ page }) => {
  // Record cart events and payment requests for assertions.
  await page.addInitScript(() => {
    const w = window as unknown as { __ttb: { carts: unknown[]; orders: unknown[] } };
    w.__ttb = { carts: [], orders: [] };
    document.addEventListener(
      "ttb:cart-changed",
      (e) => w.__ttb.carts.push((e as CustomEvent).detail.cart),
      true,
    );
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

  await page.goto("/");
  await page.getByRole("button", { name: /दुकानदार से बात करें/ }).click();
  await expect(page.getByText("AI सहायक / AI assistant")).toBeVisible();

  // Opening question: pace (quickstart row 0).
  await say(page, "धीरे-धीरे, एक-एक करके");
  await expect(page.getByText(/धीरे-धीरे \/ Step by step/)).toBeVisible({ timeout: TURN_TIMEOUT });

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
  await expect(page.locator("ttb-cart-view .summary")).toContainText(`₹${cart.total.toLocaleString("en-IN")}`);

  // Row 5: read-back.
  await say(page, "बस, ऑर्डर कर दो");
  const readback = page.locator("ttb-readback");
  await expect(readback).toBeVisible({ timeout: TURN_TIMEOUT });
  await expect(readback).toContainText(`₹${cart.total.toLocaleString("en-IN")}`);

  // Row 6: yes → the shop's own payment step → fingerprint.
  await say(page, "हाँ");
  const dialog = page.getByRole("dialog", { name: /Payment/ });
  await expect(dialog).toBeVisible({ timeout: TURN_TIMEOUT });
  await expect(dialog).toContainText("Test mode");
  await dialog.getByRole("button", { name: /Pay with fingerprint/ }).click();
  await expect(dialog).toBeHidden({ timeout: TURN_TIMEOUT });

  await expect(page.getByText(/Order placed/)).toBeVisible({ timeout: TURN_TIMEOUT });
  const orders = await page.evaluate(() => (window as unknown as { __ttb: { orders: unknown[] } }).__ttb.orders);
  expect(orders.length).toBe(1);
});
