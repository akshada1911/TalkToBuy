import { afterEach, describe, expect, it, vi } from "vitest";
import "../cards/goal-list";
import "../cards/cart-view";
import type { TtbGoalList } from "../cards/goal-list";
import type { TtbCartView } from "../cards/cart-view";
import { SPOTLIGHT_MS } from "../cards/cart-view";
import type { UiProduct } from "../types/messages.generated";
import { chooseMseType, sniffCodecs } from "../avatar/codec";
import { buildNetQuality } from "../protocol/net-quality";

const product = (id: string, local_name: string, price = 50): UiProduct => ({
  id,
  name: `Name ${id}`,
  local_name,
  size: "1 kg",
  price,
  image: "",
  image_credit: "",
  in_stock: true,
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("<ttb-goal-list>", () => {
  it("renders struck items with their reason", async () => {
    const el = document.createElement("ttb-goal-list") as TtbGoalList;
    document.body.appendChild(el);
    el.goal = {
      type: "goal_list",
      goal_id: "g1",
      goal_text: "छोटा eggless चॉकलेट केक",
      items: [
        { need: "चीनी", struck: true, struck_reason: "on_hand" },
        { need: "दूध", product: product("p1", "दूध"), qty: 1, struck: true, struck_reason: "in_cart" },
        { need: "मैदा", product: product("p2", "मैदा"), qty: 1, struck: false },
      ],
    };
    await el.updateComplete;
    const rows = el.shadowRoot!.querySelectorAll("li");
    expect(rows.length).toBe(3);
    const struck = el.shadowRoot!.querySelectorAll("li.struck");
    expect(struck.length).toBe(2);
    expect(struck[0].querySelector(".reason")!.textContent).toContain("आपके पास है");
    expect(struck[1].querySelector(".reason")!.textContent).toContain("कार्ट में है");
    expect(rows[2].classList.contains("struck")).toBe(false);
    expect(rows[2].querySelector(".reason")).toBeNull();
  });
});

describe("<ttb-cart-view>", () => {
  it("shows count/total and spotlights the newest card in guided pace", async () => {
    vi.useFakeTimers();
    const el = document.createElement("ttb-cart-view") as TtbCartView;
    document.body.appendChild(el);
    el.pace = "guided";
    const milk = product("milk", "दूध", 54);
    el.setCart({ lines: [{ product: milk, qty: 2, line_total: 108 }], item_count: 1, total: 108 });
    await el.updateComplete;
    expect(el.spotlightId).toBe("milk");
    expect(el.shadowRoot!.querySelector(".summary")!.textContent).toContain("₹108");
    expect(el.shadowRoot!.querySelector("ul.grid")).toBeNull(); // alone
    vi.advanceTimersByTime(SPOTLIGHT_MS + 10);
    await el.updateComplete;
    expect(el.spotlightId).toBeNull();
    expect(el.shadowRoot!.querySelectorAll("ul.grid ttb-product-card").length).toBe(1);
  });

  it("does not spotlight in quick pace", async () => {
    const el = document.createElement("ttb-cart-view") as TtbCartView;
    document.body.appendChild(el);
    el.pace = "quick";
    el.setCart({ lines: [{ product: product("a", "आटा"), qty: 1, line_total: 50 }], item_count: 1, total: 50 });
    await el.updateComplete;
    expect(el.spotlightId).toBeNull();
  });
});

describe("avatar codec sniffing", () => {
  it("builds an avc1 string from avcC", () => {
    const bytes = new Uint8Array([0, 0, 0, 0, ...[..."avcC"].map((c) => c.charCodeAt(0)), 1, 0x42, 0xe0, 0x1e, 0, 0, ...[..."mp4a"].map((c) => c.charCodeAt(0))]);
    expect(sniffCodecs(bytes)).toEqual({ video: "avc1.42E01E", audio: "mp4a.40.2" });
    expect(chooseMseType(bytes, (t) => t === 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"')).toBe(
      'video/mp4; codecs="avc1.42E01E, mp4a.40.2"',
    );
  });
  it("falls back to common types", () => {
    expect(chooseMseType(new Uint8Array(4), (t) => t === 'video/mp4; codecs="avc1.42E01E"')).toBe('video/mp4; codecs="avc1.42E01E"');
    expect(chooseMseType(new Uint8Array(4), () => false)).toBeNull();
  });
});

describe("net_quality", () => {
  it("converts downlink to kbps and reports underruns since last report", () => {
    expect(buildNetQuality({ downlink: 1.5, rtt: 200 }, 120, 2)).toEqual({
      type: "net_quality",
      downlink_kbps: 1500,
      rtt_ms: 120,
      underruns: 2,
    });
    expect(buildNetQuality(undefined, null, 0)).toEqual({ type: "net_quality", downlink_kbps: null, rtt_ms: null, underruns: 0 });
  });
});
