import { useEffect } from "react";
import type { StringKey } from "../i18n";
import { Icon } from "../design/Icon";
import { useFingerprint } from "../payment/useFingerprint";
import { BackButton } from "../components/TopBar";
import { useApp, type PayMethod } from "../state";

const METHODS: { id: PayMethod; label: StringKey; sub: StringKey; icon: string }[] = [
  { id: "upi", label: "payUpi", sub: "payUpiSub", icon: "i-phone" },
  { id: "card", label: "payCard", sub: "payCardSub", icon: "i-card" },
  { id: "wallet", label: "payWallet", sub: "payWalletSub", icon: "i-wallet" },
  { id: "cod", label: "payCod", sub: "payCodSub", icon: "i-cash" },
];

export function Pay() {
  const { lang, t, paymentRequest: req, resolvePayment, back, demo, setDemo } = useApp();
  const fp = useFingerprint(req, resolvePayment);

  // Escape = go back (decline), like the old payment dialog.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") fp.decline();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [req]);

  if (!req) {
    return (
      <div className="screen">
        <div className="topbar">
          <BackButton />
          <div className="topbar-title">
            <b>{t("payTitle")}</b>
          </div>
        </div>
        <div className="empty">
          <p>{t("payNoRequest")}</p>
          <button type="button" className="btn btn-pill" onClick={back}>
            {t("back")}
          </button>
        </div>
      </div>
    );
  }

  const total = `₹${req.total}`;
  const slot = lang === "hi" ? req.delivery.label_hi : req.delivery.label_en;
  const [addrLabel, ...addrRest] = (req.address_text ?? "").split(": ");
  const addrText = addrRest.join(": ");

  return (
    <div className="screen">
      <div className="topbar">
        <button type="button" className="round-btn" onClick={fp.decline} disabled={fp.busy} aria-label={t("back")}>
          <Icon name="i-back" size={20} stroke={2.2} />
        </button>
        <div className="topbar-title">
          <b>{t("payTitle")}</b>
          <small>{t("payToPay", { x: total })}</small>
        </div>
        <span className="demo-tag">{t("payTestMode")}</span>
      </div>

      <div className="scroll grow stack" style={{ padding: "14px 16px 120px", gap: 14 }}>
        <div className="panel" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="ico-box">
            <Icon name="i-pin" size={22} />
          </span>
          <span className="stack gap2" style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{addrText ? t("deliveringTo", { label: addrLabel }) : t("deliveryAddress")}</span>
            {addrText && <span className="note" style={{ lineHeight: 1.3 }}>{addrText}</span>}
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--green)" }}>
              {t("slot")}: {slot}
            </span>
          </span>
        </div>

        <span className="display" style={{ fontWeight: 700, fontSize: 18, padding: "0 2px" }}>
          {t("payWith")} <span className="demo-tag">{t("demo")}</span>
        </span>
        <div className="stack gap10">
          {METHODS.map((m) => {
            const on = demo.pay === m.id;
            return (
              <button type="button" key={m.id} className={`option ${on ? "on" : ""}`} aria-pressed={on} onClick={() => setDemo({ pay: m.id })}>
                <span className="ico-box light">
                  <Icon name={m.icon} size={22} />
                </span>
                <span className="stack gap2" style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 700, fontSize: 15 }}>{t(m.label)}</span>
                  <span className="note">{t(m.sub)}</span>
                </span>
                <span className="radio">
                  <Icon name="i-check" size={14} stroke={3} />
                </span>
              </button>
            );
          })}
        </div>
        <span className="note" style={{ padding: "0 4px" }}>
          {t("payNote")}
        </span>
        {fp.error && (
          <p className="form-error" role="alert">
            {t(fp.error)}
          </p>
        )}
      </div>

      <div className="bottom-bar">
        <div className="total" style={{ minWidth: 96 }}>
          <small>{t("payTotal")}</small>
          <b>{total}</b>
        </div>
        <button type="button" className="btn btn-forest" style={{ flex: 1 }} onClick={() => void fp.approve()} disabled={fp.busy}>
          <span aria-hidden="true">☝️</span>
          {fp.status === "registering" ? t("paySettingUp") : fp.busy ? t("payWait") : t("payFingerprint", { x: total })}
        </button>
      </div>
    </div>
  );
}
