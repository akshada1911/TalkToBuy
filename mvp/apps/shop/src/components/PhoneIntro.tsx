import { useEffect, useState } from "react";
import { StatusIcons, useClock } from "./StatusIcons";

/** Simple line glyphs (24×24) for the pretend apps. Generic shapes, no real brands. */
const GLYPHS: Record<string, string[]> = {
  phone: ["M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"],
  messages: ["M4 5h16v11H9l-5 4z"],
  browser: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M3 12h18", "M12 3c3 3 3 15 0 18", "M12 3c-3 3-3 15 0 18"],
  camera: ["M4 8h4l2-3h4l2 3h4v11H4z", "M12 9.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"],
  photos: ["M4 4h16v16H4z", "M4 16l5-5 4 4 3-3 4 4"],
  clock: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", "M12 7v5l3.5 2"],
  notes: ["M6 3h12v18H6z", "M9 8h6M9 12h6M9 16h4"],
  weather: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"],
  files: ["M3 6h7l2 2h9v11H3z"],
  maps: ["M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z", "M12 7.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"],
  calendar: ["M4 6h16v14H4z", "M4 10h16M8 3v4M16 3v4"],
  mail: ["M3 6h18v12H3z", "M3 7l9 7 9-7"],
  settings: ["M4 7h10M18 7h2M4 17h2M10 17h10", "M16 5v4M8 15v4"],
  music: ["M9 18V6l10-2v12", "M9 18a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z", "M19 16a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z"],
  calculator: ["M6 3h12v18H6z", "M9 7h6M9 12h.01M12 12h.01M15 12h.01M9 16h.01M12 16h.01M15 16h.01"],
  tips: ["M9 18h6M10 21h4", "M12 3a6 6 0 0 0-4 10.5V15h8v-1.5A6 6 0 0 0 12 3z"],
  health: ["M12 20s-8-5-8-10a4.5 4.5 0 0 1 8-2.5A4.5 4.5 0 0 1 20 10c0 5-8 10-8 10z"],
};
const TONES = ["#3b82f6", "#22a06b", "#7c5cd6", "#e0702a", "#d94f70", "#0e9aa7", "#8a6d3b", "#5b6b7a"];

const PAGE_ONE = ["photos", "clock", "notes", "weather", "files", "maps", "calendar", "mail"];
const PAGE_TWO = ["settings", "music", "calculator", "tips", "health", "ECOMM"]; // the Ecomm App: second row, second column
const DOCK = ["phone", "messages", "browser", "camera"];

const label = (k: string) => (k === "ECOMM" ? "Ecomm App" : k[0].toUpperCase() + k.slice(1));

function Glyph({ name, size = 28 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {GLYPHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

function Bag({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#f4b63b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 8h14l1 12H4z" />
      <path d="M9 8V7a3 3 0 0 1 6 0v1" />
    </svg>
  );
}

function AppIcon({ name, tone }: { name: string; tone: string }) {
  const ecomm = name === "ECOMM";
  return (
    <div className={`intro-app ${ecomm ? "ecomm" : ""}`}>
      <span className="intro-ico" style={{ background: ecomm ? "#0f3d2e" : tone }}>
        {ecomm ? <Bag /> : <Glyph name={name} />}
      </span>
      <span>{label(name)}</span>
    </div>
  );
}

// How long each step lasts before the next begins (ms).
// 0 lock screen, waiting for a tap · 1 swipe up to unlock · 2 home screen · 3 swipe to the next page ·
// 4 finger glides to the Ecomm App · 5 tap · 6 the app opens · 7 fade away
const STEP_MS = [0, 650, 450, 750, 700, 380, 600];

/**
 * A short film at the start, inside the phone. It waits on the lock screen; tap the screen and it
 * unlocks, swipes to the page with the Ecomm App, taps it, and the app opens onto the screen the
 * shopper already has behind. It is only a picture on top of the app; "Skip" or Esc goes straight to
 * the app.
 */
export function PhoneIntro({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const time = useClock();

  useEffect(() => {
    if (step === 0) return; // waiting for the tap
    if (step >= STEP_MS.length) {
      const id = setTimeout(onDone, 320);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => setStep((s) => s + 1), STEP_MS[step]);
    return () => clearTimeout(id);
  }, [step, onDone]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDone();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDone]);

  const date = new Date().toLocaleDateString("en-US", { weekday: "long", day: "numeric", month: "long" });
  const flags = [
    step >= 1 && "is-unlocked",
    step >= 3 && "is-scrolled",
    step >= 4 && "is-gliding",
    step >= 5 && "is-tapped",
    step >= 6 && "is-opening",
    step >= 7 && "is-leaving",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={`intro ${flags} ${step === 0 ? "is-waiting" : ""}`} onClick={() => step === 0 && setStep(1)} aria-hidden="true">
      <div className="intro-wall" />

      <div className="intro-home">
        <div className="intro-pages">
          <div className="intro-page">
            {PAGE_ONE.map((k, i) => (
              <AppIcon key={k} name={k} tone={TONES[i % TONES.length]} />
            ))}
          </div>
          <div className="intro-page">
            {PAGE_TWO.map((k, i) => (
              <AppIcon key={k} name={k} tone={TONES[(i + 3) % TONES.length]} />
            ))}
          </div>
        </div>
        <div className="intro-dots">
          <span className="on" />
          <span />
        </div>
        <div className="intro-dock">
          {DOCK.map((k, i) => (
            <span key={k} className="intro-ico" style={{ background: TONES[(i + 1) % TONES.length] }}>
              <Glyph name={k} />
            </span>
          ))}
        </div>
      </div>

      <div className="intro-lock">
        <b className="intro-time">{time}</b>
        <span className="intro-date">{date}</span>
        <span className="intro-hint">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 15l6-6 6 6" />
          </svg>
          Tap to unlock
        </span>
        <button
          type="button"
          className="intro-skip"
          tabIndex={-1}
          onClick={(e) => {
            e.stopPropagation();
            onDone();
          }}
        >
          Skip
        </button>
      </div>

      <div className="intro-launch">
        <Bag size={30} />
      </div>
      <span className="intro-finger" />

      <div className="intro-bar">
        <span className="intro-clock">{time}</span>
        <span className="status-camera" />
        <StatusIcons />
      </div>
    </div>
  );
}
