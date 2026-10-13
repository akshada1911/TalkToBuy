import { describe, expect, it } from "vitest";
import "../talktobuy-assistant";
import type { TalkToBuyAssistant } from "../talktobuy-assistant";

describe("<talktobuy-assistant>", () => {
  it("shows the AI label and the big start button before a session", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    el.setAttribute("show-translation", "false");
    document.body.appendChild(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    expect(root.querySelector(".ai-label")!.textContent).toContain("AI सहायक");
    expect(root.querySelector("button.start-btn")!.textContent).toContain("दुकानदार से बात करें");
    expect(el.showTranslation).toBe(false);
    el.remove();
  });

  it("shows every label in English when language=en", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    el.setAttribute("language", "en");
    document.body.appendChild(el);
    await el.updateComplete;
    const root = el.shadowRoot!;
    expect(root.querySelector(".ai-label")!.textContent).toContain("AI assistant");
    expect(root.querySelector("button.start-btn")!.textContent).toContain("Talk to the shopkeeper");
    expect(/[ऀ-ॿ]/.test(root.textContent ?? "")).toBe(false);
    el.remove();
  });

  it("re-emits cart, payment and order messages as DOM events", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    document.body.appendChild(el);
    await el.updateComplete;
    const seen: Array<[string, unknown]> = [];
    for (const n of ["ttb:cart-changed", "ttb:payment-requested", "ttb:order-placed"]) {
      document.addEventListener(n, (e) => seen.push([n, (e as CustomEvent).detail]));
    }
    const delivery = { id: "slot-1800", label_hi: "शाम 6 से 7 बजे", label_en: "6–7 pm" };
    el.onServerMessage({ type: "cart", cart: { lines: [], item_count: 0, total: 0 } });
    el.onServerMessage({ type: "payment_request", checkout_id: "chk_1", item_count: 10, total: 1016, currency: "INR", delivery });
    el.onServerMessage({ type: "order", order_id: "ord_1", delivery });
    expect(seen.map((s) => s[0])).toEqual(["ttb:cart-changed", "ttb:payment-requested", "ttb:order-placed"]);
    expect(seen[0][1]).toEqual({ cart: { lines: [], item_count: 0, total: 0 }, cart_id: null });
    expect(seen[1][1]).toEqual({ checkout_id: "chk_1", total: 1016, currency: "INR", item_count: 10, delivery });
    expect(seen[2][1]).toEqual({ order_id: "ord_1", delivery });
    // No session yet: resolvePayment cannot send.
    expect(el.resolvePayment({ checkout_id: "chk_1", approved: false })).toBe(false);
    el.remove();
  });
});
