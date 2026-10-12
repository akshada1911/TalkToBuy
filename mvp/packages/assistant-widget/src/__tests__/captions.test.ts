import { describe, expect, it } from "vitest";
import { TtbCaptions, maskDigits } from "../captions/captions";

describe("maskDigits (T102)", () => {
  it("masks 4–8 digit runs", () => {
    expect(maskDigits("मेरा OTP 123456 है")).toBe("मेरा OTP •••••• है");
    expect(maskDigits("PIN 4321")).toBe("PIN ••••");
    expect(maskDigits("code 12345678")).toBe("code ••••••••");
  });

  it("leaves short numbers and long numbers alone", () => {
    expect(maskDigits("दो लीटर दूध, 250 ग्राम")).toBe("दो लीटर दूध, 250 ग्राम");
    expect(maskDigits("123")).toBe("123");
    expect(maskDigits("1234567890")).toBe("1234567890");
  });

  it("masks Devanagari digits and digits spoken one by one", () => {
    expect(maskDigits("ओटीपी १२३४५६")).toBe("ओटीपी ••••••");
    expect(maskDigits("OTP 1 2 3 4 5 6 hai")).toBe("OTP • • • • • • hai");
    expect(maskDigits("2 500 ग्राम")).toBe("2 500 ग्राम");
  });
});

describe("<ttb-captions>", () => {
  async function mount(): Promise<TtbCaptions> {
    const el = document.createElement("ttb-captions") as TtbCaptions;
    document.body.appendChild(el);
    await el.updateComplete;
    return el;
  }

  it("masks shopper captions but not the assistant's, keyed by turn_id", async () => {
    const el = await mount();
    el.upsert({ type: "caption", who: "shopper", turn_id: "s1", text_hi: "OTP 1234", final: false });
    el.upsert({ type: "caption", who: "shopper", turn_id: "s1", text_hi: "OTP 123456 है", final: true });
    el.upsert({ type: "caption", who: "assistant", turn_id: "a1", text_hi: "ऑर्डर 1016 रुपये", text_en: "Order ₹1016", final: true });
    await el.updateComplete;
    const turns = el.shadowRoot!.querySelectorAll(".turn");
    expect(turns.length).toBe(2);
    expect(turns[0].querySelector(".hi")!.textContent).toBe("OTP •••••• है");
    expect(turns[1].querySelector(".hi")!.textContent).toContain("1016");
    const en = turns[1].querySelector(".en")!;
    expect(en.textContent).toContain("EN (translation)");
    expect(en.getAttribute("aria-label")).toContain("English translation");
    expect(el.shadowRoot!.querySelector("[aria-live=polite]")).not.toBeNull();
  });

  it("hides translation lines when show-translation is false", async () => {
    const el = await mount();
    el.upsert({ type: "caption", who: "assistant", turn_id: "a1", text_hi: "नमस्ते", text_en: "Hello", final: true });
    el.showTranslation = false;
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector(".en")).toBeNull();
  });
});
