import { useState } from "react";
import { addAddress, fullAddress, type NewAddress } from "../api";
import { TopBar } from "../components/TopBar";
import { Icon } from "../design/Icon";
import type { StringKey } from "../i18n";
import { useApp } from "../state";

const FIELDS: { key: keyof NewAddress; label: StringKey; mode?: "numeric" | "tel"; max: number }[] = [
  { key: "label", label: "fieldLabel", max: 40 },
  { key: "name", label: "fieldName", max: 80 },
  { key: "line1", label: "fieldLine1", max: 160 },
  { key: "area", label: "fieldArea", max: 80 },
  { key: "city", label: "fieldCity", max: 80 },
  { key: "pincode", label: "fieldPincode", mode: "numeric", max: 6 },
  { key: "phone", label: "fieldPhone", mode: "tel", max: 10 },
];
const EMPTY: NewAddress = { label: "", name: "", line1: "", area: "", city: "", pincode: "", phone: "" };

export function Address() {
  const { t, addresses, addressesError, preferred, setPreferred, reloadAddresses } = useApp();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<NewAddress>(EMPTY);
  const [error, setError] = useState<StringKey | null>(null);
  const [saving, setSaving] = useState(false);

  const validate = (): StringKey | null => {
    const required: (keyof NewAddress)[] = ["name", "line1", "area", "city", "pincode", "phone"];
    if (required.some((k) => !form[k].trim())) return "errFill";
    if (!/^[1-9][0-9]{5}$/.test(form.pincode.trim())) return "errPincode";
    if (!/^[6-9][0-9]{9}$/.test(form.phone.replace(/[\s-]/g, ""))) return "errPhone";
    return null;
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate();
    setError(problem);
    if (problem) return;
    setSaving(true);
    try {
      const saved = await addAddress({ ...form, label: form.label.trim(), phone: form.phone.replace(/[\s-]/g, "") });
      await reloadAddresses();
      setPreferred(saved.id);
      setForm(EMPTY);
      setAdding(false);
    } catch {
      setError("errSave");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="screen">
      <TopBar plain title={t("addressTitle")} />
      <div className="scroll grow stack gap12" style={{ padding: "20px 16px 28px" }}>
        {addressesError && (
          <p className="form-error" role="alert">
            {t("addressLoadError")}
          </p>
        )}
        {addresses.map((a) => {
          const on = preferred?.id === a.id;
          return (
            <button type="button" key={a.id} className={`addr-opt ${on ? "on" : ""}`} aria-pressed={on} onClick={() => setPreferred(a.id)}>
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

        {adding ? (
          <form className="panel stack gap12" onSubmit={save} noValidate>
            {FIELDS.map((f) => (
              <label className="field" key={f.key}>
                {t(f.label)}
                <input
                  type="text"
                  name={f.key}
                  inputMode={f.mode ?? "text"}
                  maxLength={f.max}
                  autoComplete="off"
                  value={form[f.key]}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              </label>
            ))}
            {error && (
              <p className="form-error" role="alert">
                {t(error)}
              </p>
            )}
            <div style={{ display: "flex", gap: 10 }}>
              <button type="submit" className="btn btn-forest" style={{ flex: 1 }} disabled={saving}>
                {t("addressSave")}
              </button>
              <button type="button" className="btn btn-outline" onClick={() => setAdding(false)}>
                {t("cancel")}
              </button>
            </div>
          </form>
        ) : (
          <button type="button" className="btn btn-outline" style={{ alignSelf: "flex-start" }} onClick={() => setAdding(true)}>
            <Icon name="i-plus" size={20} />
            {t("addressNew")}
          </button>
        )}
        <span className="note">{t("addressNote")}</span>
      </div>
    </div>
  );
}
