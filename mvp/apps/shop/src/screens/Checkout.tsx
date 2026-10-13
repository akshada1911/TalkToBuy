import { useEffect, useState } from "react";
import { fullAddress, listSlots } from "../api";
import { TopBar } from "../components/TopBar";
import { Icon } from "../design/Icon";
import { useLoad } from "../hooks";
import { useApp } from "../state";

/** Check out by tapping: pick the address and delivery slot, then pay with the fingerprint. */
export function Checkout() {
  const { lang, t, go, count, total, addresses, addressesError, preferred, startManualCheckout } = useApp();
  const slots = useLoad(() => listSlots(), []);
  const [addressId, setAddressId] = useState<string | null>(null);
  const [slotId, setSlotId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Defaults: the saved default address and the earliest slot.
  useEffect(() => {
    if (!addressId && (preferred ?? addresses[0])) setAddressId((preferred ?? addresses[0]).id);
  }, [addressId, preferred, addresses]);
  useEffect(() => {
    if (!slotId && slots.data?.length) setSlotId(slots.data[0].id);
  }, [slotId, slots.data]);

  const label = (s: { label_hi: string; label_en: string }) => (lang === "hi" ? s.label_hi : s.label_en);
  const ready = count > 0 && !!addressId && !!slotId && !busy;

  const proceed = async () => {
    if (!addressId || !slotId) return;
    setBusy(true);
    await startManualCheckout(slotId, addressId);
    setBusy(false);
  };

  return (
    <div className="screen">
      <TopBar title={t("checkoutTitle")} sub={t("payToPay", { x: `₹${total}` })} />
      <div className="scroll grow stack" style={{ padding: "14px 16px 120px", gap: 16 }}>
        {count === 0 && <p className="note">{t("checkoutEmpty")}</p>}

        <div className="stack gap10">
          <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
            {t("checkoutDeliverTo")}
          </span>
          {addressesError && (
            <p className="form-error" role="alert">
              {t("addressLoadError")}
            </p>
          )}
          {addresses.map((a) => {
            const on = a.id === addressId;
            return (
              <button type="button" key={a.id} className={`addr-opt ${on ? "on" : ""}`} aria-pressed={on} onClick={() => setAddressId(a.id)}>
                <span className="ico-box">
                  <Icon name="i-pin" size={22} />
                </span>
                <span className="stack gap2" style={{ flex: 1 }}>
                  <span style={{ fontWeight: 700, fontSize: 16 }}>{a.label}</span>
                  <span style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.35 }}>{fullAddress(a)}</span>
                </span>
                <span className="radio">
                  <Icon name="i-check" size={16} stroke={3} />
                </span>
              </button>
            );
          })}
          <button type="button" className="btn-link" style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 8 }} onClick={() => go({ screen: "address" })}>
            <Icon name="i-plus" size={20} />
            {t("addressNew")}
          </button>
          {addresses.length === 0 && !addressesError && <p className="note">{t("checkoutNoAddress")}</p>}
        </div>

        <div className="stack gap10">
          <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
            {t("checkoutSlot")}
          </span>
          {slots.error && (
            <p className="form-error" role="alert">
              {t("checkoutSlotsError")}
            </p>
          )}
          <div className="hs" style={{ padding: 0, margin: 0, flexWrap: "wrap" }}>
            {(slots.data ?? []).map((s, i) => {
              const on = s.id === slotId;
              return (
                <button type="button" key={s.id} className={`chip ${on ? "on" : ""}`} aria-pressed={on} onClick={() => setSlotId(s.id)}>
                  {i === 0 ? `${t("slotEarliest")} · ` : ""}
                  {label(s)}
                </button>
              );
            })}
          </div>
        </div>

        <div className="panel stack gap10">
          <div className="bill-row">
            <span>{t("billItems")}</span>
            <span>₹{total}</span>
          </div>
          <div className="bill-row">
            <span>{t("billDelivery")}</span>
            <span style={{ color: "var(--green)" }}>{t("billFree")}</span>
          </div>
          <div className="rule" />
          <div className="bill-row" style={{ alignItems: "baseline" }}>
            <span style={{ fontWeight: 700, fontSize: 16, color: "var(--ink)" }}>{t("toPay")}</span>
            <span className="display" style={{ fontWeight: 800, fontSize: 22, color: "var(--ink)" }}>
              ₹{total}
            </span>
          </div>
        </div>
      </div>

      <div className="bottom-bar">
        <div className="total">
          <small>{t("payTotal")}</small>
          <b>₹{total}</b>
        </div>
        <button type="button" className="btn btn-forest" style={{ flex: 1 }} onClick={() => void proceed()} disabled={!ready}>
          {busy ? <span className="spinner" /> : t("checkoutContinue")}
        </button>
      </div>
    </div>
  );
}
