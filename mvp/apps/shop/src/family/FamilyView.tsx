import { useEffect, useState } from "react";
import { tr, type Lang } from "../lang";

interface Notification {
  id: string;
  message: string;
  created_at: string | number;
}

const POLL_MS = 3000;
const CONTACT = "Rohit (son)";

/** Family view (US5, T091): what "Rohit (son)" sees in the app. Polls every 3 s. */
export function FamilyView({ shopperId, lang }: { shopperId: string; lang: Lang }) {
  const [items, setItems] = useState<Notification[]>([]);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const res = await fetch(`/demo/family/notifications?shopper_id=${encodeURIComponent(shopperId)}`);
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
  }, [shopperId]);

  return (
    <section className="family" aria-labelledby="family-title">
      <h1 id="family-title">
        {lang === "en" ? `Alerts for ${CONTACT}` : "परिवार के लिए सूचनाएँ"}
      </h1>
      <p className="family-sub">
        {tr(lang, "घनश्याम जी", "Ghanshyam ji")} · {tr(lang, "हर 3 सेकंड में अपडेट", "updates every 3 s")}
      </p>
      {offline && (
        <p className="family-offline" role="status">
          {tr(lang, "सर्वर से नहीं जुड़ पाए, फिर कोशिश कर रहे हैं…", "Can't reach the server, retrying…")}
        </p>
      )}
      <ul className="family-list" aria-live="polite">
        {items.length === 0 && !offline && <li className="family-empty">{tr(lang, "अभी कोई सूचना नहीं", "No alerts yet")}</li>}
        {items.map((n) => (
          <li key={n.id} className="family-item">
            <span className="family-icon" aria-hidden="true">
              🔔
            </span>
            <div>
              <p className="family-msg">{n.message}</p>
              <time className="family-time" dateTime={String(n.created_at)}>
                {formatTime(n.created_at, lang)}
              </time>
            </div>
          </li>
        ))}
      </ul>
      <p>
        <a className="nav-link" href="/">
          ← {tr(lang, "दुकान पर वापस", "Back to shop")}
        </a>
      </p>
    </section>
  );
}

function formatTime(iso: string | number, lang: Lang): string {
  const raw = String(iso);
  // Accept ISO strings and Unix seconds/milliseconds.
  const d = /^\d+(\.\d+)?$/.test(raw) ? new Date(Number(raw) < 1e12 ? Number(raw) * 1000 : Number(raw)) : new Date(raw);
  return Number.isNaN(d.getTime()) ? raw : d.toLocaleString(lang === "en" ? "en-IN" : "hi-IN", { dateStyle: "medium", timeStyle: "short" });
}
