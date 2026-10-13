import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * Phone-app checks on the static shop (no backend; the store is stubbed): the controls are big
 * enough to tap (44 px, as in the design), the text is readable, the AI label is visible, the
 * language toggle reaches every screen, and nothing scrolls sideways on a phone.
 *
 * axe-core (@axe-core/playwright) is not installed in this workspace, so the WCAG AA contrast scan
 * is not automated here. Add `new AxeBuilder({ page }).withTags(["wcag2aa"]).analyze()` when it is.
 */

const PRODUCT = {
  id: "p-0001",
  name: "Toned Milk 1 L",
  local_name: "टोंड दूध 1 लीटर",
  brand: "Nestlé",
  size: "1 L",
  price: 68,
  image: "",
  image_credit: "",
  category: "dairy",
  in_stock: true,
  description: "Toned milk.",
  usage: null,
};

async function stubStore(page: Page) {
  await page.route("**/demo/catalog/p-**", (r) => r.fulfill({ json: { ...PRODUCT, similar: [] } }));
  await page.route("**/demo/catalog?**", (r) => r.fulfill({ json: { items: [PRODUCT], total: 1, limit: 24, offset: 0 } }));
  await page.route("**/demo/shoppers/**/addresses", (r) =>
    r.fulfill({ json: [{ id: "addr-home", label: "Home", name: "A", line1: "Flat 12", area: "Kothrud", city: "Pune", pincode: "411038", phone: "9876543210" }] }),
  );
  await page.route("**/demo/shoppers/**/last-order", (r) => r.fulfill({ status: 404, json: {} }));
  await page.route("**/demo/family/notifications**", (r) => r.fulfill({ json: [] }));
  // No backend: nothing should hang if something tries to start a session.
  await page.route("**/v1/demo-ticket", (r) => r.fulfill({ status: 503, body: "{}" }));
}

async function open(page: Page, path = "/") {
  await stubStore(page);
  await page.goto(path);
  await expect(page.locator("talktobuy-assistant")).toBeAttached();
}

/** A bottom-navigation tab (the promo cards also say "TalkToBuy", so scope to the nav). */
const tab = (page: Page, name: string) => page.locator("nav").getByRole("button", { name, exact: true });

async function expectTapTarget(loc: Locator, name: string) {
  await expect(loc, name).toBeVisible();
  const box = await loc.boundingBox();
  expect(box, `${name} has a box`).not.toBeNull();
  expect(box!.width, `${name} width`).toBeGreaterThanOrEqual(43.5);
  expect(box!.height, `${name} height`).toBeGreaterThanOrEqual(43.5);
}

test("the app is a phone-width column with no sideways scroll", async ({ page }) => {
  await open(page);
  const phone = await page.locator(".phone").boundingBox();
  expect(phone!.width).toBeLessThanOrEqual(430);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
});

test("home controls are at least 44×44 px", async ({ page }) => {
  await open(page);
  await expectTapTarget(tab(page, "TalkToBuy"), "talk button");
  await expectTapTarget(tab(page, "होम"), "home tab");
  await expectTapTarget(tab(page, "ब्राउज़"), "browse tab");
  await expectTapTarget(tab(page, "कार्ट"), "cart tab");
  await expectTapTarget(page.locator(".account-btn"), "account button");
  await expectTapTarget(page.locator(".search-row .mic-btn"), "voice button");
});

test("browse lists products with a 44 px ADD button", async ({ page }) => {
  await open(page);
  await tab(page, "ब्राउज़").click();
  await expect(page.locator(".pcard").first()).toBeVisible();
  await expectTapTarget(page.locator(".pcard .add-btn").first(), "ADD button");
  expect(await page.locator("body").evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(15);
});

test("the AI assistant label is visible when the shopkeeper opens", async ({ page }) => {
  await open(page);
  await tab(page, "TalkToBuy").click();
  await expect(page.getByText("AI सहायक")).toBeVisible();
});

test("the language setting changes every screen", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /खाता और सेटिंग/ }).click();
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(tab(page, "Home")).toBeVisible();
  await expect(tab(page, "Cart")).toBeVisible();
  await expect(page.getByText("Shop by category")).toBeVisible();
  await expect(page.getByText(/[ऀ-ॿ]/).first()).not.toBeVisible();
});

test("unsupported languages are shown but cannot be chosen yet", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /खाता और सेटिंग/ }).click();
  await expect(page.getByRole("button", { name: /தமிழ்/ })).toBeDisabled();
});

test("the cart is empty and offers the two ways to shop", async ({ page }) => {
  await open(page);
  await tab(page, "कार्ट").click();
  await expect(page.getByText("आपका कार्ट खाली है")).toBeVisible();
  await expectTapTarget(page.getByRole("button", { name: "ब्राउज़ करें" }), "browse button");
  await expectTapTarget(page.getByRole("button", { name: "बोलकर खरीदें" }), "talk button");
});

test("family view renders without a backend", async ({ page }) => {
  await open(page, "/family");
  await expect(page.getByText(/के लिए सूचनाएँ/)).toBeVisible();
  await expect(page.getByRole("switch")).toBeVisible();
  await expectTapTarget(page.getByRole("button", { name: "पीछे" }), "back button");
});

test("a keyboard user sees a focus ring on the main buttons", async ({ page }) => {
  await open(page);
  const talk = tab(page, "TalkToBuy");
  await talk.focus();
  const outline = await talk.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});
