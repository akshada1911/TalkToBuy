import { useEffect, useState } from "react";
import { SHOPPER_ID } from "../config";
import { TopBar } from "../components/TopBar";
import type { Lang } from "../lang";
import { useApp } from "../state";

interface Notification {
  id: string;
  message: string;
  created_at: string | number;
}

const POLL_MS = 3000;
const CONTACT = "Rohit (son)";

function formatTime(iso: string | number, lang: Lang): string {
  const raw = String(iso);
  // Accept ISO strings and Unix seconds/milliseconds.
  const d = /^\d+(\.\d+)?$/.test(raw) ? new Date(Number(raw) < 1e12 ? Number(raw) * 1000 : Number(raw)) : new Date(raw);
  return Number.isNaN(d.getTime()) ? raw : d.toLocaleString(lang === "en" ? "en-IN" : "hi-IN", { dateStyle: "medium", timeStyle: "short" });
}

/** What "Rohit (son)" sees in the app: the real family alerts, polled every 3 seconds. */
function Alerts() {
  const { lang, t } = useApp();
  const [items, setItems] = useState<Notification[]>([]);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const res = await fetch(`/demo/family/notifications?shopper_id=${encodeURIComponent(SHOPPER_ID)}`);
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as Notification[];
        if (!stop) {
          setItems([...data].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))));
          setOffline(false);
        }
      } catch {
        if (!stop) setOffline(true);
      }
      if (!stop) timer = setTimeout(poll, POLL_MS);
    };
    void poll();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return (
    <div className="stack gap10">
      <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
        {t("alertsFor", { name: CONTACT })}
      </span>
      <span className="note">{t("alertsEvery")}</span>
      {offline && (
        <p className="note" role="status">
          {t("alertsOffline")}
        </p>
      )}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {items.length === 0 && !offline && (
          <li className="note" style={{ fontSize: 15 }}>
            {t("alertsEmpty")}
          </li>
        )}
        {items.map((n) => (
          <li key={n.id} className="alert-item">
            <span aria-hidden="true" style={{ fontSize: 24 }}>
              🔔
            </span>
            <div className="stack gap2">
              <p style={{ fontWeight: 700, fontSize: 15 }}>{n.message}</p>
              <time className="note" dateTime={String(n.created_at)}>
                {formatTime(n.created_at, lang)}
              </time>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Family() {
  const { t, demo, setDemo } = useApp();
  const toggleShare = () => setDemo({ share: !demo.share });
  const toggleMember = (id: string) =>
    setDemo({ members: demo.members.map((m) => (m.id === id ? { ...m, canOrder: !m.canOrder } : m)) });

  return (
    <div className="screen">
      <TopBar plain title={t("familyView")} />
      <div className="scroll grow stack" style={{ padding: "20px 16px 28px", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: 16, background: "var(--forest)", color: "#fff", borderRadius: 22 }}>
          <span className="stack" style={{ flex: 1, gap: 3 }}>
            <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
              {t("shareTitle")}
            </span>
            <span style={{ fontSize: 13, color: "var(--on-forest)", lineHeight: 1.35 }}>{t("shareSub")}</span>
          </span>
          <button type="button" className="switch" role="switch" aria-checked={demo.share} aria-label={t("shareAria")} onClick={toggleShare}>
            <span className="track">
              <span className="knob" />
            </span>
          </button>
        </div>

        <div className="stack gap10">
          <span className="display" style={{ fontWeight: 700, fontSize: 18 }}>
            {t("familyWho")}
          </span>
          {demo.members.map((m) => (
            <div key={m.id} className="row-card" style={{ minHeight: 68, padding: "10px 12px" }}>
              <span className="avatar-chip" style={{ width: 44, height: 44, fontSize: 18 }}>
                {(m.id === "me" ? t("you") : m.name).charAt(0)}
              </span>
              <span className="stack gap2" style={{ flex: 1 }}>
                <span style={{ fontWeight: 700, fontSize: 16 }}>{m.id === "me" ? t("you") : m.name}</span>
                <span className="note">{m.locked ? t("roleOwner") : m.canOrder ? t("roleCanOrder") : t("roleViewOnly")}</span>
              </span>
              <button type="button" className={`pill ${m.locked ? "owner" : m.canOrder ? "on" : ""}`} disabled={m.locked} onClick={() => toggleMember(m.id)}>
                {m.locked ? t("roleOwner") : m.canOrder ? t("roleCanOrder") : t("roleViewOnly")}
              </button>
            </div>
          ))}
          <span className="note">{t("familyNote")}</span>
        </div>

        <Alerts />
      </div>
    </div>
  );
}
