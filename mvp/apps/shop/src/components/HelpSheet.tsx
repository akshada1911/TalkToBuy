import { useState } from "react";
import { Icon } from "../design/Icon";
import type { StringKey } from "../i18n";
import { useApp } from "../state";

const OPTIONS: { icon: string; label: StringKey; note: StringKey }[] = [
  { icon: "i-phone", label: "helpCall", note: "helpCallNote" },
  { icon: "i-help", label: "helpChat", note: "helpChatNote" },
  { icon: "i-receipt", label: "helpInvoice", note: "helpInvoiceNote" },
  { icon: "i-tag", label: "helpReport", note: "helpReportNote" },
];

/** Demo help sheet: each row only shows a note. Nothing is sent anywhere. */
export function HelpSheet({ onClose }: { onClose: () => void }) {
  const { t } = useApp();
  const [note, setNote] = useState<StringKey | null>(null);
  return (
    <>
      <button type="button" className="scrim-btn scrim" onClick={onClose} aria-label={t("close")} />
      <div className="bottom-sheet sheet" role="dialog" aria-label={t("helpTitle")}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="sheet-title">{t("helpTitle")}</span>
          <button type="button" className="round-btn" onClick={onClose} aria-label={t("close")}>
            <Icon name="i-close" size={20} stroke={2.2} />
          </button>
        </div>
        {OPTIONS.map((o) => (
          <button type="button" key={o.label} className="help-row" onClick={() => setNote(o.note)}>
            <Icon name={o.icon} size={22} />
            <span style={{ flex: 1 }}>{t(o.label)}</span>
            <Icon name="i-chev" size={20} />
          </button>
        ))}
        {note && (
          <span className="help-note line">
            <span className="demo-tag">{t("demo")}</span> {t(note)}
          </span>
        )}
      </div>
    </>
  );
}
