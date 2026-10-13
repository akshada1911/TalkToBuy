import { useState } from "react";
import type { UiProduct } from "@talktobuy/assistant-widget";
import type { CatalogProduct } from "../api";
import { displayName } from "../catalog";
import { ProductImage } from "../components/ProductImage";
import { Stepper } from "../components/Stepper";
import { TopBar, VoiceButton } from "../components/TopBar";
import { Icon } from "../design/Icon";
import { useApp } from "../state";

/** The cart shows the assistant's UI products; the +/− requests take the catalogue shape. */
export function asCatalog(p: UiProduct): CatalogProduct {
  return {
    id: p.id,
    name: p.name,
    local_name: p.local_name,
    brand: null,
    size: p.size,
    price: p.price,
    image: p.image,
    image_credit: p.image_credit ?? "",
    category: "",
    in_stock: p.in_stock,
    description: "",
    usage: null,
  };
}

interface Coupon {
  code: string;
  title: "couponFlat50" | "couponPct10";
  note: "couponFlat50Note" | "couponPct10Note";
  min: number;
  type: "flat" | "pct";
  val: number;
  cap?: number;
}
export const COUPONS: Coupon[] = [
  { code: "TALK50", title: "couponFlat50", note: "couponFlat50Note", min: 299, type: "flat", val: 50 },
  { code: "FRESH10", title: "couponPct10", note: "couponPct10Note", min: 199, type: "pct", val: 10, cap: 60 },
];
const TIPS = [0, 10, 20, 30];

export function couponValue(c: Coupon | undefined, item: number): number {
  if (!c || item < c.min) return 0;
  return c.type === "flat" ? c.val : Math.min(c.cap ?? c.val, Math.round((item * c.val) / 100));
}

export function Cart() {
  const { lang, t, go, openTalk, cart, count, total, preferred, demo, setDemo, isPending, requestInc, requestDec, requestCheckout, requestCancel, checkoutPending } =
    useApp();
  const [couponOpen, setCouponOpen] = useState(false);
  const lines = cart?.lines ?? [];
  const applied = COUPONS.find((c) => c.code === demo.coupon);
  const saving = couponValue(applied, total);

  if (count === 0) {
    return (
      <div className="screen">
        <TopBar title={t("cartTitle")} sub={t("itemCount", { n: 0 })} right={<VoiceButton />} />
        <div className="grow" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 24, textAlign: "center" }}>
          <span style={{ width: 84, height: 84, borderRadius: "50%", background: "var(--sand)", color: "var(--forest)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="i-cart" size={40} />
          </span>
          <span className="display" style={{ fontWeight: 800, fontSize: 24 }}>
            {t("cartEmpty")}
          </span>
          <p style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.4 }}>{t("cartEmptyHint")}</p>
          <div style={{ display: "flex", gap: 10, paddingTop: 6 }}>
            <button type="button" className="btn btn-outline" onClick={() => go({ screen: "list", listCat: "all", query: "" })}>
              {t("browse")}
            </button>
            <button type="button" className="btn btn-pill" style={{ height: 48, borderRadius: 24 }} onClick={openTalk}>
              {t("talkToBuy")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="screen">
      <TopBar title={t("cartTitle")} sub={t("cartSub", { count: count === 1 ? t("itemCount1") : t("itemCount", { n: count }) })} right={<VoiceButton />} />

      <div className="scroll grow stack gap12" style={{ padding: "12px 16px 120px" }}>
        {saving > 0 && (
          <div className="save-banner">
            <Icon name="i-tag" size={20} />
            {t("couponSubOn", { x: `₹${saving}` })}
          </div>
        )}

        <div className="lines">
          {lines.map((l) => {
            const p = asCatalog(l.product);
            const name = displayName(p, lang);
            return (
              <div className="cline line" key={p.id}>
                <button type="button" className="thumb" style={{ background: "var(--sand-2)" }} onClick={() => go({ screen: "pdp", pdpId: p.id })} aria-label={t("details", { name })}>
                  <ProductImage product={{ image: p.image, category: "home", name: p.name }} size={34} />
                </button>
                <div className="stack gap2" style={{ flex: 1, minWidth: 0 }}>
                  <span className="clamp2" style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.25 }}>
                    {name}
                  </span>
                  <span className="psub">{p.size}</span>
                  <span style={{ fontWeight: 700, fontSize: 15 }}>₹{l.line_total}</span>
                </div>
                <Stepper size="compact" qty={l.qty} name={name} busy={isPending(p.id)} onDec={() => requestDec(p)} onInc={() => requestInc(p)} />
              </div>
            );
          })}
          <button
            type="button"
            className="btn-link"
            style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 48 }}
            onClick={() => go({ screen: "list", listCat: "all", query: "" })}
          >
            <Icon name="i-plus" size={20} />
            {t("addMore")}
          </button>
        </div>

        <button type="button" className="row-card" onClick={() => setCouponOpen(true)}>
          <span className="ico-box tag">
            <Icon name="i-tag" size={22} />
          </span>
          <span className="stack gap2" style={{ flex: 1 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{saving > 0 ? t("couponApplied", { code: demo.coupon ?? "" }) : t("applyCoupon")}</span>
            <span className="note">{saving > 0 ? t("couponSubOn", { x: `₹${saving}` }) : t("couponSubIdle")}</span>
          </span>
          <Icon name="i-chev" size={20} />
        </button>

        <div className="panel stack gap10">
          <div className="stack gap2">
            <span style={{ fontWeight: 700, fontSize: 15 }}>
              {t("tipTitle")} <span className="demo-tag">{t("demo")}</span>
            </span>
            <span className="note">{t("tipSub")}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8 }}>
            {TIPS.map((v) => (
              <button type="button" key={v} className={`choice ${demo.tip === v ? "on" : ""}`} aria-pressed={demo.tip === v} onClick={() => setDemo({ tip: v })}>
                {v ? `₹${v}` : t("tipNone")}
              </button>
            ))}
          </div>
        </div>

        <div className="panel stack gap10">
          <span className="display" style={{ fontWeight: 700, fontSize: 17 }}>
            {t("billTitle")}
          </span>
          <div className="bill-row">
            <span>{t("billItems")}</span>
            <span>₹{total}</span>
          </div>
          <div className="bill-row">
            <span>{t("billDelivery")}</span>
            <span style={{ color: "var(--green)" }}>{t("billFree")}</span>
          </div>
          {saving > 0 && (
            <div className="bill-row">
              <span>{t("billCoupon", { code: demo.coupon ?? "" })}</span>
              <span style={{ color: "var(--green)" }}>-₹{saving}</span>
            </div>
          )}
          {demo.tip > 0 && (
            <div className="bill-row">
              <span>{t("billTip")}</span>
              <span>₹{demo.tip}</span>
            </div>
          )}
          <div className="rule" />
          <div className="bill-row" style={{ alignItems: "baseline" }}>
            <span style={{ fontWeight: 700, fontSize: 16, color: "var(--ink)" }}>{t("toPay")}</span>
            <span className="display" style={{ fontWeight: 800, fontSize: 22, color: "var(--ink)" }}>
              ₹{total}
            </span>
          </div>
        </div>
        <span className="note" style={{ padding: "0 4px" }}>
          {t("billNote")}
        </span>
        <button type="button" className="btn-link" style={{ alignSelf: "flex-start", color: "var(--danger)" }} onClick={requestCancel}>
          {t("cancelOrder")}
        </button>
      </div>

      <div className="bottom-bar">
        <button
          type="button"
          onClick={() => go({ screen: "address" })}
          aria-label={t("changeAddress")}
          style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 1, padding: 0, background: "none", border: 0, textAlign: "left", color: "var(--ink)", minHeight: 44, justifyContent: "center" }}
        >
          <span style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 3 }}>
            {preferred ? t("deliveringTo", { label: preferred.label }) : t("deliveryAddress")}
            <Icon name="i-down" size={16} />
          </span>
          <span className="display" style={{ fontWeight: 800, fontSize: 22 }}>
            ₹{total}
          </span>
        </button>
        <button type="button" className="btn btn-forest" onClick={requestCheckout} disabled={checkoutPending}>
          {checkoutPending ? (
            <>
              <span className="spinner" /> {t("checkingOut")}
            </>
          ) : (
            <>
              {t("checkOut")} <Icon name="i-chev" size={20} />
            </>
          )}
        </button>
      </div>

      {couponOpen && <CouponSheet total={total} onClose={() => setCouponOpen(false)} />}
    </div>
  );
}

function CouponSheet({ total, onClose }: { total: number; onClose: () => void }) {
  const { t, demo, setDemo } = useApp();
  return (
    <>
      <button type="button" className="scrim-btn scrim" onClick={onClose} aria-label={t("close")} />
      <div className="bottom-sheet sheet" role="dialog" aria-label={t("offersTitle")}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="sheet-title">{t("offersTitle")}</span>
          <button type="button" className="round-btn" onClick={onClose} aria-label={t("close")}>
            <Icon name="i-close" size={20} stroke={2.2} />
          </button>
        </div>
        <span className="note">
          <span className="demo-tag">{t("demo")}</span> {t("offersDemo")}
        </span>
        {COUPONS.map((c) => {
          const ok = total >= c.min;
          const on = demo.coupon === c.code && ok;
          return (
            <div className="coupon" key={c.code}>
              <span className="stack gap2" style={{ flex: 1 }}>
                <span className="code">{c.code}</span>
                <span style={{ fontWeight: 700, fontSize: 15 }}>{t(c.title)}</span>
                <span className="note">{ok ? t(c.note) : t("couponLocked", { x: `₹${c.min - total}` })}</span>
              </span>
              <button
                type="button"
                className={`pill ${on ? "" : ok ? "on" : ""}`}
                disabled={!ok && !on}
                style={!ok && !on ? { background: "var(--sand-2)", borderColor: "var(--sand-2)", color: "var(--muted)" } : undefined}
                onClick={() => {
                  if (on) setDemo({ coupon: null });
                  else {
                    setDemo({ coupon: c.code });
                    onClose();
                  }
                }}
              >
                {on ? t("remove") : ok ? t("apply") : t("locked")}
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}
