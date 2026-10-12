import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Elder-first accessibility checks on the static shop page (T103, Constitution IV), no backend:
 * body text ≥ 18 px, card text ≥ 20 px, tap targets ≥ 48×48 px, the "AI assistant" label visible.
 *
 * axe-core (@axe-core/playwright) is not installed in this workspace, so the WCAG AA contrast scan
 * is not automated here; the colour tokens are documented with their contrast ratios in
 * packages/assistant-widget/src/styles/tokens.ts. Add `@axe-core/playwright` and an
 * `new AxeBuilder({ page }).withTags(["wcag2aa"]).analyze()` assertion when it is available.
 */

async function fontPx(loc: Locator): Promise<number> {
  return loc.evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
}

async function expectTapTarget(loc: Locator, name: string) {
  await expect(loc, name).toBeVisible();
  const box = await loc.boundingBox();
  expect(box, `${name} has a box`).not.toBeNull();
  expect(box!.width, `${name} width`).toBeGreaterThanOrEqual(48);
  expect(box!.height, `${name} height`).toBeGreaterThanOrEqual(48);
}

async function open(page: Page) {
  // No backend: stub the ticket endpoint so nothing hangs if something tries to start a session.
  await page.route("**/v1/demo-ticket", (r) => r.fulfill({ status: 503, body: "{}" }));
  await page.goto("/");
  await expect(page.locator("talktobuy-assistant")).toBeAttached();
}

test("body text is at least 18 px", async ({ page }) => {
  await open(page);
  expect(await fontPx(page.locator("body"))).toBeGreaterThanOrEqual(18);
  for (const sel of [".hero-en", ".site-footer p", ".aisle-hi", ".aisle-en"]) {
    const loc = page.locator(sel).first();
    expect(await fontPx(loc), sel).toBeGreaterThanOrEqual(18);
  }
});

test("card text is at least 20 px", async ({ page }) => {
  await open(page);
  const aisles = page.locator(".aisle");
  expect(await aisles.count()).toBeGreaterThan(0);
  for (const loc of await aisles.all()) expect(await fontPx(loc)).toBeGreaterThanOrEqual(20);
});

test("key controls are at least 48×48 px", async ({ page }) => {
  await open(page);
  // Playwright locators pierce the widget's shadow DOM.
  await expectTapTarget(page.getByRole("button", { name: /दुकानदार से बात करें/ }), "start button");
  await expectTapTarget(page.getByRole("link", { name: /परिवार/ }), "family link");
  await expectTapTarget(page.locator(".brand"), "brand link");
});

test("AI assistant label and footer notices are visible", async ({ page }) => {
  await open(page);
  await expect(page.getByText("AI सहायक")).toBeVisible();
  await expect(page.getByText(/Open Food Facts contributors, ODbL/)).toBeVisible();
  await expect(page.getByText("दाम सिर्फ़ डेमो के लिए हैं")).toBeVisible();
});

test("the start button is reachable by keyboard and shows a focus ring", async ({ page }) => {
  await open(page);
  const start = page.getByRole("button", { name: /दुकानदार से बात करें/ });
  await start.focus();
  const outline = await start.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});

test("family view renders without a backend", async ({ page }) => {
  await page.route("**/demo/family/notifications**", (r) => r.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto("/family");
  await expect(page.getByText(/परिवार के लिए सूचनाएँ/)).toBeVisible();
  await expectTapTarget(page.getByRole("link", { name: /दुकान पर वापस/ }), "back link");
});
