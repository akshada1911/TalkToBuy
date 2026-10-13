import { afterEach, describe, expect, it } from "vitest";
import "../captions/captions";
import "../cards/cart-view";
import "../camera/camera";
import "../checkout/address-picker";
import "../talktobuy-assistant";
import type { TtbCaptions } from "../captions/captions";
import type { TtbCartView } from "../cards/cart-view";
import type { TtbCamera } from "../camera/camera";
import type { TtbAddressPicker } from "../checkout/address-picker";
import type { TalkToBuyAssistant } from "../talktobuy-assistant";
import type { UiProduct } from "../types/messages.generated";

afterEach(() => {
  document.body.innerHTML = "";
});

const product = (id: string, name: string, price = 50): UiProduct => ({
  id,
  name,
  local_name: `${name} (hi)`,
  size: "1 kg",
  price,
  image: "",
  image_credit: "",
  in_stock: true,
});

describe("<ttb-captions variant=talk>", () => {
  it("draws only the latest line from each side but keeps every turn for screen readers", async () => {
    const el = document.createElement("ttb-captions") as TtbCaptions;
    el.variant = "talk";
    document.body.appendChild(el);
    el.upsert({ type: "caption", who: "assistant", turn_id: "a1", text_hi: "first", final: true });
    el.upsert({ type: "caption", who: "shopper", turn_id: "s1", text_hi: "milk please", final: true });
    el.upsert({ type: "caption", who: "assistant", turn_id: "a2", text_hi: "second", final: true });
    await el.updateComplete;
    const turns = [...el.shadowRoot!.querySelectorAll(".t")];
    expect(turns.length).toBe(3);
    expect(turns.map((t) => t.classList.contains("old"))).toEqual([true, false, false]);
    expect(el.shadowRoot!.querySelector("[role=log][aria-live=polite]")).not.toBeNull();
    // White text on the green page: none of the log bubbles' classes (they have light backgrounds).
    expect(turns.every((t) => !t.classList.contains("assistant") && !t.classList.contains("shopper"))).toBe(true);
    expect(turns.map((t) => t.getAttribute("data-who"))).toEqual(["assistant", "shopper", "assistant"]);
  });

  it("greets before the first turn", async () => {
    const el = document.createElement("ttb-captions") as TtbCaptions;
    el.variant = "talk";
    el.language = "en";
    document.body.appendChild(el);
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector(".bot")!.textContent).toContain("What would you like to order today?");
  });
});

describe("<ttb-cart-view compact>", () => {
  it("lists the cart as rows with the count and total", async () => {
    const el = document.createElement("ttb-cart-view") as TtbCartView;
    el.compact = true;
    el.language = "en";
    el.pace = "quick";
    document.body.appendChild(el);
    el.setCart({ lines: [{ product: product("a", "Atta", 265), qty: 2, line_total: 530 }], item_count: 1, total: 530 });
    await el.updateComplete;
    const root = el.shadowRoot!;
    expect(root.querySelector(".sum")!.textContent).toContain("530");
    expect(root.querySelectorAll("ul.rows li").length).toBe(1);
    expect(root.querySelector("li .what b")!.textContent).toBe("Atta");
    expect(root.querySelector("li .what small")!.textContent).toContain("×2");
    expect(root.querySelector("ul.grid")).toBeNull();
  });

  it("says so when the cart is empty", async () => {
    const el = document.createElement("ttb-cart-view") as TtbCartView;
    el.compact = true;
    el.language = "en";
    document.body.appendChild(el);
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector(".empty")!.textContent).toContain("Nothing yet");
  });
});

describe("<ttb-camera variant=overlay>", () => {
  it("is invisible until opened, then explains when there is no camera, and closes", async () => {
    const el = document.createElement("ttb-camera") as TtbCamera;
    el.variant = "overlay";
    el.language = "en";
    document.body.appendChild(el);
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector(".overlay")).toBeNull();
    await el.toggle(); // happy-dom has no getUserMedia
    await el.updateComplete;
    const overlay = el.shadowRoot!.querySelector(".overlay")!;
    expect(overlay.textContent).toContain("Camera not available");
    (overlay.querySelector("button.cancel") as HTMLButtonElement).click();
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector(".overlay")).toBeNull();
  });
});

describe("<ttb-address-picker> default address", () => {
  it("lists the default first and marks it", async () => {
    const el = document.createElement("ttb-address-picker") as TtbAddressPicker;
    el.language = "en";
    el.addresses = [
      { id: "a", label: "Home", text: "Flat 12" },
      { id: "b", label: "Office", text: "Shop 4" },
    ];
    el.preferredId = "b";
    document.body.appendChild(el);
    await el.updateComplete;
    const labels = [...el.shadowRoot!.querySelectorAll("li .label")].map((n) => n.textContent!.trim());
    expect(labels[0]).toContain("Office");
    expect(labels[0]).toContain("Default");
    expect(labels[1]).toBe("Home");
  });
});

describe("<talktobuy-assistant> app layout", () => {
  async function live(): Promise<TalkToBuyAssistant> {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    el.setAttribute("language", "en");
    document.body.appendChild(el);
    await el.updateComplete;
    (el as unknown as { phase: string }).phase = "live";
    await el.updateComplete;
    return el;
  }

  it("announces its phase to the host", async () => {
    const el = document.createElement("talktobuy-assistant") as TalkToBuyAssistant;
    const seen: string[] = [];
    el.addEventListener("ttb:phase", (e) => seen.push((e as CustomEvent<{ phase: string }>).detail.phase));
    document.body.appendChild(el);
    await el.updateComplete;
    (el as unknown as { phase: string }).phase = "live";
    await el.updateComplete;
    expect(seen).toContain("idle");
    expect(seen[seen.length - 1]).toBe("live");
  });

  it("shows status, suggestion chips, and the three round controls", async () => {
    const el = await live();
    const root = el.shadowRoot!;
    expect(root.querySelector(".status")!.textContent).toContain("listening");
    expect(root.querySelectorAll(".chips button").length).toBe(3);
    expect(root.querySelector("button.mic")).not.toBeNull();
    expect(root.querySelectorAll(".controls button.ctl").length).toBe(2);
    expect(root.querySelector("ttb-camera[variant=overlay]")).not.toBeNull();
    expect(root.querySelector("ttb-captions[variant=talk]")).not.toBeNull();
  });

  it("the mic button switches the microphone off and on", async () => {
    const el = await live();
    const mic = () => el.shadowRoot!.querySelector("button.mic") as HTMLButtonElement;
    expect(mic().getAttribute("aria-pressed")).toBe("false");
    mic().click();
    await el.updateComplete;
    expect(mic().getAttribute("aria-pressed")).toBe("true");
    expect(el.shadowRoot!.querySelector(".status")!.textContent).toContain("Mic is off");
    mic().click();
    await el.updateComplete;
    expect(mic().getAttribute("aria-pressed")).toBe("false");
  });

  it("the cart button asks the host to open the cart", async () => {
    const el = await live();
    let opened = 0;
    el.addEventListener("ttb:open-cart", () => opened++);
    (el.shadowRoot!.querySelectorAll(".controls button.ctl")[1] as HTMLButtonElement).click();
    expect(opened).toBe(1);
  });

  it("the sheet layout hides the cart panel but keeps it mounted", async () => {
    const el = await live();
    el.setAttribute("layout", "sheet");
    await el.updateComplete;
    const cart = el.shadowRoot!.querySelector("ttb-cart-view")!;
    expect(cart.hasAttribute("hidden")).toBe(true);
    el.setAttribute("layout", "page");
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector("ttb-cart-view")!.hasAttribute("hidden")).toBe(false);
  });

  it("a hidden host mutes the microphone (the muted attribute)", async () => {
    const el = await live();
    el.setAttribute("muted", "");
    await el.updateComplete;
    expect(el.muted).toBe(true);
    expect(el.shadowRoot!.querySelector(".status")!.textContent).toContain("Mic is off");
    expect((el.shadowRoot!.querySelector("button.mic") as HTMLButtonElement).disabled).toBe(true);
  });
});
