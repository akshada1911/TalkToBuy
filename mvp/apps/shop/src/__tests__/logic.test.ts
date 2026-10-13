import { describe, expect, it } from "vitest";
import { STRINGS, translate } from "../i18n";
import { CATEGORIES, categoryMeta, displayName } from "../catalog";
import { COUPONS, asCatalog, couponValue } from "../screens/Cart";

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("translations", () => {
  const entries = Object.entries(STRINGS) as [string, { en: string; hi: string }][];

  it("every label exists in both English and Hindi", () => {
    for (const [key, v] of entries) {
      expect(v.en.trim(), `${key} en`).not.toBe("");
      expect(v.hi.trim(), `${key} hi`).not.toBe("");
    }
  });

  it("English and Hindi use the same placeholders", () => {
    for (const [key, v] of entries) expect(placeholders(v.hi), key).toEqual(placeholders(v.en));
  });

  it("the Hindi labels are Hindi (Devanagari) apart from names and units", () => {
    const latinOnly = entries.filter(([, v]) => !/[ऀ-ॿ]/.test(v.hi)).map(([k]) => k);
    // Brand names and symbols that stay Latin in Hindi too.
    expect(latanOk(latinOnly)).toBe(true);
  });

  it("fills placeholders", () => {
    expect(translate("en", "inCart", { n: 3 })).toBe("3 in cart");
    expect(translate("hi", "inCart", { n: 3 })).toBe("कार्ट में 3");
    expect(translate("en", "resultsFor", { n: 5, q: "milk" })).toBe('5 results for "milk"');
  });

  it("every category has a label and a tile", () => {
    for (const c of CATEGORIES) {
      expect(STRINGS[c.label]).toBeDefined();
      expect(c.icon.startsWith("ic-")).toBe(true);
    }
  });
});

function latanOk(keys: string[]): boolean {
  // These are allowed to have no Devanagari at all: UPI, and the like.
  const allowed = new Set(["payUpi", "assistantTitle", "trackSub"]);
  return keys.every((k) => allowed.has(k));
}

describe("catalogue helpers", () => {
  it("shows the Hindi name in Hindi mode and the English name otherwise", () => {
    const p = { name: "Toned Milk 1 L", local_name: "टोंड दूध 1 लीटर" };
    expect(displayName(p, "hi")).toBe("टोंड दूध 1 लीटर");
    expect(displayName(p, "en")).toBe("Toned Milk 1 L");
    expect(displayName({ name: "Salt", local_name: "" }, "hi")).toBe("Salt");
  });

  it("falls back to a default tile for an unknown category", () => {
    expect(categoryMeta("dairy").icon).toBe("ic-milk");
    expect(categoryMeta("nope")).toBe(categoryMeta("home"));
  });

  it("maps the assistant's cart products to the catalogue shape", () => {
    const c = asCatalog({ id: "p-1", name: "Milk", local_name: "दूध", size: "1 L", price: 54, image: "x", image_credit: "c", in_stock: true });
    expect(c).toMatchObject({ id: "p-1", name: "Milk", size: "1 L", price: 54, in_stock: true });
  });
});

describe("demo coupons (preview only)", () => {
  const flat = COUPONS.find((c) => c.code === "TALK50");
  const pct = COUPONS.find((c) => c.code === "FRESH10");

  it("unlocks only above the minimum", () => {
    expect(couponValue(flat, 298)).toBe(0);
    expect(couponValue(flat, 299)).toBe(50);
    expect(couponValue(pct, 198)).toBe(0);
    expect(couponValue(undefined, 999)).toBe(0);
  });

  it("caps the percentage coupon", () => {
    expect(couponValue(pct, 200)).toBe(20);
    expect(couponValue(pct, 2000)).toBe(60);
  });
});
