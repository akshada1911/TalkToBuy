import { afterEach, describe, expect, it } from "vitest";
import "../checkout/address-picker";
import "../talktobuy-assistant";
import type { TtbAddressPicker } from "../checkout/address-picker";
import type { TalkToBuyAssistant } from "../talktobuy-assistant";
import { parseServerMessage } from "../protocol/client";

const ADDRESSES = [
  { id: "addr-home", label: "Home", text: "Flat 12, Kothrud, Pune 411038" },
  { id: "addr-rohit", label: "Rohit's place", text: "B-204, Baner, Pune 411045" },
];

afterEach(() => {
  document.body.innerHTML = "";
});

async function picker(language: "hi" | "en") {
  const el = document.createElement("ttb-address-picker") as TtbAddressPicker;
  el.addresses = ADDRESSES;
  el.language = language;
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe("<ttb-address-picker>", () => {
  it("lists saved addresses and emits the chosen one", async () => {
    const el = await picker("hi");
    const root = el.shadowRoot!;
    expect(root.querySelectorAll("li").length).toBe(2);
    expect(root.textContent).toContain("किस पते पर भेजें?");
    let seen: unknown = null;
    el.addEventListener("ttb-address-select", (e) => (seen = (e as CustomEvent).detail));
    (root.querySelectorAll("li button")[1] as HTMLButtonElement).click();
    expect(seen).toEqual({ id: "addr-rohit", label: "Rohit's place" });
  });

  it("is fully English when language=en", async () => {
    const el = await picker("en");
    const text = el.shadowRoot!.textContent ?? "";
    expect(text).toContain("Where should we deliver?");
    expect(text).toContain("New address");
    expect(/[ऀ-ॿ]/.test(text)).toBe(false);
  });

  it("validates a new address before emitting it", async () => {
    const el = await picker("en");
    const root = el.shadowRoot!;
    (root.querySelector("button.new") as HTMLButtonElement).click();
    await el.updateComplete;
    let seen: unknown = null;
    el.addEventListener("ttb-address-new", (e) => (seen = (e as CustomEvent).detail));
    const submit = () => root.querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true }));
    submit();
    await el.updateComplete;
    expect(root.querySelector(".err")!.textContent).toContain("every field");
    expect(seen).toBeNull();

    const fill = (name: string, value: string) => {
      const input = root.querySelector(`input[name=${name}]`) as HTMLInputElement;
      input.value = value;
      input.dispatchEvent(new Event("input"));
    };
    fill("name", "Ghanshyam Sharma");
    fill("line1", "Shop 4, FC Road");
    fill("area", "Deccan");
    fill("city", "Pune");
    fill("pincode", "41");
    fill("phone", "9876543210");
    submit();
    await el.updateComplete;
    expect(root.querySelector(".err")!.textContent).toContain("6 digits");
    fill("pincode", "411004");
    submit();
    expect(seen).toEqual({
      fields: { name: "Ghanshyam Sharma", line1: "Shop 4, FC Road", area: "Deccan", city: "Pune", pincode: "411004", phone: "9876543210" },
    });
    await el.updateComplete;
    expect(root.querySelector("form")!.hidden).toBe(true);
  });
});

describe("address step in the assistant", () => {
  it("parses the addresses message", () => {
    const m = parseServerMessage(JSON.stringify({ type: "addresses", addresses: ADDRESSES }));
    expect(m?.type).toBe("addresses");
  });

  it("shows the picker on addresses and replaces it with the read-back", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    document.body.appendChild(el);
    await el.updateComplete;
    // The picker lives in the live view; drive the state directly.
    (el as unknown as { phase: string }).phase = "live";
    await el.updateComplete;
    el.onServerMessage({ type: "addresses", addresses: ADDRESSES });
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector("ttb-address-picker")).not.toBeNull();
    const delivery = { id: "slot-1800", label_hi: "शाम 6 से 7 बजे", label_en: "6–7 pm" };
    el.onServerMessage({
      type: "readback", checkout_id: "c1", item_count: 2, total: 100, delivery,
      address_text: "Home: Flat 12, Kothrud, Pune 411038", text_hi: "हिंदी", text_en: "English",
    });
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector("ttb-address-picker")).toBeNull();
    expect(el.shadowRoot!.querySelector("ttb-readback")).not.toBeNull();
  });
});

describe("cancelled order and voice-only mode", () => {
  it("closes the checkout steps when the cart is emptied and offers no video switch", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    document.body.appendChild(el);
    await el.updateComplete;
    (el as unknown as { phase: string }).phase = "live";
    await el.updateComplete;
    const delivery = { id: "slot-1800", label_hi: "शाम 6 से 7 बजे", label_en: "6–7 pm" };
    const cancelled: unknown[] = [];
    el.addEventListener("ttb:payment-cancelled", (e) => cancelled.push(e));
    el.onServerMessage({ type: "cart", cart: { lines: [], item_count: 2, total: 100 } });
    el.onServerMessage({
      type: "readback", checkout_id: "c1", item_count: 2, total: 100, delivery, text_hi: "हिंदी", text_en: "English",
    });
    el.onServerMessage({ type: "payment_request", checkout_id: "c1", item_count: 2, total: 100, currency: "INR", delivery });
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector("ttb-readback")).not.toBeNull();
    el.onServerMessage({ type: "cart", cart: { lines: [], item_count: 0, total: 0 } });
    await el.updateComplete;
    expect(cancelled.length).toBe(1);
    expect(el.shadowRoot!.querySelector("ttb-readback")).toBeNull();
    expect(el.shadowRoot!.querySelector("ttb-media-toggle")).toBeNull();
    expect(el.effectiveMode).toBe("audio_only");
  });
});
