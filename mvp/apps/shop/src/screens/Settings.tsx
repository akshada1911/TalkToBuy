import { shortAddress } from "../api";
import { TopBar } from "../components/TopBar";
import { Icon } from "../design/Icon";
import type { Lang } from "../lang";
import { useApp } from "../state";

interface LangOption {
  id: string;
  label: string;
  /** Only Hindi and English are supported by the assistant today. */
  lang?: Lang;
}

const LANGS: LangOption[] = [
  { id: "en", label: "English", lang: "en" },
  { id: "hi", label: "हिन्दी", lang: "hi" },
  { id: "mr", label: "मराठी" },
  { id: "kn", label: "ಕನ್ನಡ" },
  { id: "ta", label: "தமிழ்" },
  { id: "te", label: "తెలుగు" },
];

export function Settings() {
  const { lang, setLang, t, go, demo, preferred } = useApp();
  const orderers = demo.members.filter((m) => m.canOrder).length;
  return (
    <div className="screen">
      <TopBar plain title={t("settingsTitle")} />
      <div className="scroll grow stack" style={{ padding: "20px 16px 28px", gap: 22 }}>
        <div className="stack gap12" role="group" aria-label={t("chooseLanguage")}>
          <div className="stack gap2">
            <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
              {t("languageTitle")}
            </span>
            <span style={{ fontSize: 14, color: "var(--muted)" }}>{t("languageSub")}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
            {LANGS.map((g) => {
              const supported = g.lang !== undefined;
              const on = g.lang === lang;
              return (
                <button
                  type="button"
                  key={g.id}
                  className={`choice ${on ? "on" : ""}`}
                  style={{ height: supported ? 48 : 60, borderRadius: 14, fontWeight: 600, fontSize: 15, opacity: supported ? 1 : 0.55, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 0 }}
                  aria-pressed={on}
                  disabled={!supported}
                  onClick={() => g.lang && setLang(g.lang)}
                >
                  {g.label}
                  {!supported && <span style={{ fontSize: 10, fontWeight: 600 }}>{t("comingSoon")}</span>}
                </button>
              );
            })}
          </div>
          <span className="note">{t("languageNote")}</span>
        </div>

        <div className="stack gap10">
          <button type="button" className="row-card big" onClick={() => go({ screen: "family" })}>
            <span className="ico-box">
              <Icon name="i-users" size={22} />
            </span>
            <span className="stack gap2" style={{ flex: 1 }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>{t("familyView")}</span>
              <span className="note">{t("familySummary", { share: demo.share ? t("sharingLive") : t("notSharing"), n: orderers })}</span>
            </span>
            <Icon name="i-chev" size={20} />
          </button>
          <button type="button" className="row-card big" onClick={() => go({ screen: "address" })}>
            <span className="ico-box">
              <Icon name="i-pin" size={22} />
            </span>
            <span className="stack gap2" style={{ flex: 1 }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>{t("deliveryAddress")}</span>
              <span className="note">{preferred ? `${preferred.label} · ${shortAddress(preferred)}` : "—"}</span>
            </span>
            <Icon name="i-chev" size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
