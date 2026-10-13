import { useEffect, useState } from "react";
import { displayName } from "../catalog";
import { asCatalog } from "./Cart";
import { ProductImage } from "../components/ProductImage";
import { HelpSheet } from "../components/HelpSheet";
import { Icon } from "../design/Icon";
import { useApp } from "../state";
import shopkeeper from "../assets/shopkeeper.png";
import type { StringKey } from "../i18n";

const TAGS: StringKey[] = ["trackTag0", "trackTag1", "trackTag2", "trackTag3"];
const HEADS: StringKey[] = ["trackHead0", "trackHead1", "trackHead2", "trackHead3"];
const RIDERS: StringKey[] = ["riderAssigning", "riderStore", "riderWay", "riderDone"];
// The steps move on a timer: there is no delivery backend, so tracking is a demo.
const STEP_AT_MS = [0, 4000, 9000, 14000];

function useStep(placedAt: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const elapsed = now - placedAt;
  return STEP_AT_MS.reduce((s, at, i) => (elapsed >= at ? i : s), 0);
}

export function Track() {
  const { lang, t, order, goHome } = useApp();
  const [help, setHelp] = useState(false);
  const step = useStep(order?.placedAt ?? Date.now());

  if (!order) {
    return (
      <div className="screen">
        <div className="empty" style={{ marginTop: 120 }}>
          <p>{t("payNoRequest")}</p>
          <button type="button" className="btn btn-pill" onClick={goHome}>
            {t("backHome")}
          </button>
        </div>
      </div>
    );
  }

  const [addrLabel] = order.addressText.split(": ");
  const slot = lang === "hi" ? order.slot.label_hi : order.slot.label_en;

  return (
    <div className="screen">
      <div className="scroll grow" style={{ paddingBottom: 24 }}>
        <div className="track-map">
          <svg width="100%" height="300" viewBox="0 0 390 300" preserveAspectRatio="xMidYMid slice" style={{ display: "block" }} role="img" aria-label={t("mapLabel")}>
            <rect width="390" height="300" fill="#E6E9DD" />
            <path d="M-10 190c60-30 120 10 190-20s120-60 230-40v60c-110-20-170 20-230 50s-130-10-190 20z" fill="#CFE2EA" />
            <rect x="236" y="196" width="96" height="62" rx="14" fill="#CFE3C6" />
            <rect x="24" y="52" width="70" height="44" rx="12" fill="#CFE3C6" />
            <path d="M0 120h390M0 236h390M60 0v300M150 0v300M250 0v300M330 0v300" stroke="#FFFFFF" strokeWidth="10" fill="none" />
            <path d="M0 60h390M110 0v300M290 0v300" stroke="#F7F8F2" strokeWidth="5" fill="none" />
            <path d="M60 236H150V120H250V120H330V60" fill="none" stroke="#0F3D2E" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="1 9" />
            <g>
              <circle cx="60" cy="236" r="16" fill="#0F3D2E" />
              <path d="M53 233h14l-1.5 9h-11zM55 233l1-4h8l1 4" fill="none" stroke="#F4B63B" strokeWidth="2" strokeLinejoin="round" />
            </g>
            <g>
              <circle cx="330" cy="60" r="18" fill="#F4B63B" stroke="#14201A" strokeWidth="2.4" />
              <path d="M322 60l8-7 8 7v8h-16z" fill="none" stroke="#14201A" strokeWidth="2.2" strokeLinejoin="round" />
            </g>
            <circle cx="60" cy="236" r="9" fill="#FFFFFF" stroke="#14201A" strokeWidth="2.4" opacity={step < 2 ? 1 : 0} />
            <circle r="10" fill="#FFFFFF" stroke="#14201A" strokeWidth="2.6" opacity={step === 2 ? 1 : 0}>
              <animateMotion dur="9s" repeatCount="indefinite" path="M60 236H150V120H250V120H330V60" />
            </circle>
            <circle cx="330" cy="60" r="9" fill="#FFFFFF" stroke="#14201A" strokeWidth="2.4" opacity={step >= 3 ? 1 : 0} />
          </svg>
          <button type="button" className="round-btn float" style={{ position: "absolute", left: 16, top: 10 }} onClick={goHome} aria-label={t("backHome")}>
            <Icon name="i-back" size={20} stroke={2.2} />
          </button>
          <button
            type="button"
            onClick={() => setHelp(true)}
            style={{ position: "absolute", right: 16, top: 10, height: 44, padding: "0 14px", borderRadius: 22, border: 0, background: "#fff", color: "var(--ink)", display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 14, boxShadow: "0 1px 6px rgba(20,32,26,.18)" }}
          >
            <Icon name="i-help" size={18} />
            {t("help")}
          </button>
        </div>

        <div className="stack gap12" style={{ position: "relative", margin: "-36px 16px 0" }}>
          <div className="track-card">
            <span className="eyebrow" style={{ color: "var(--amber)" }}>
              {t(TAGS[step])}
            </span>
            <span className="display" style={{ fontWeight: 800, fontSize: 30, lineHeight: 1.05, letterSpacing: "-0.02em" }}>
              {t(HEADS[step])}
            </span>
            <div className="steps" aria-hidden="true">
              {[0, 1, 2, 3].map((i) => (
                <span key={i} className={i <= step ? "on" : ""} />
              ))}
            </div>
            <span style={{ fontSize: 13, color: "#d8e6de" }}>{t("trackSub", { label: addrLabel || t("deliveryAddress"), slot })}</span>
            <span style={{ fontSize: 12, color: "var(--on-forest)" }}>
              {t("orderId", { id: order.id })} · {t("trackDemo")}
            </span>
          </div>

          <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 18 }}>
            <img src={shopkeeper} alt="" style={{ width: 46, height: 46, borderRadius: "50%", objectFit: "cover", flex: "none" }} />
            <span className="stack gap2" style={{ flex: 1 }}>
              <span style={{ fontWeight: 700, fontSize: 15 }}>Ravi K.</span>
              <span className="note">{t(RIDERS[step])}</span>
            </span>
            <button type="button" className="round-btn" style={{ borderColor: "var(--forest)", color: "var(--forest)" }} onClick={() => setHelp(true)} aria-label={t("callPartner")}>
              <Icon name="i-phone" size={20} />
            </button>
          </div>

          <div className="panel stack gap10">
            <span className="display" style={{ fontWeight: 700, fontSize: 17 }}>
              {t("orderSummary")}
            </span>
            {order.lines.map((l) => {
              const p = asCatalog(l.product);
              return (
                <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="mini-thumb">
                    <ProductImage product={{ image: p.image, category: "home", name: p.name }} size={24} />
                  </span>
                  <span style={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: 14 }}>
                    {displayName(p, lang)} <span style={{ fontWeight: 500, color: "var(--muted)" }}>· {p.size} · ×{l.qty}</span>
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>₹{l.line_total}</span>
                </div>
              );
            })}
            <div className="rule" />
            <div className="bill-row" style={{ alignItems: "baseline" }}>
              <span>{t("billTitle")}</span>
              <span className="display" style={{ fontWeight: 800, fontSize: 22, color: "var(--ink)" }}>
                ₹{order.total}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn-outline" style={{ flex: 1, height: 50, borderRadius: 16 }} onClick={() => setHelp(true)}>
              <Icon name="i-receipt" size={18} />
              {t("invoice")}
            </button>
            <button type="button" className="btn btn-forest" style={{ flex: 1, height: 50, borderRadius: 16, fontSize: 15 }} onClick={goHome}>
              {t("backHome")}
            </button>
          </div>
        </div>
      </div>
      {help && <HelpSheet onClose={() => setHelp(false)} />}
    </div>
  );
}
