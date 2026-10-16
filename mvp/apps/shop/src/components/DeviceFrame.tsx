import { useState, type ReactNode } from "react";
import { useApp } from "../state";
import { PhoneIntro } from "./PhoneIntro";
import { StatusIcons, useClock } from "./StatusIcons";

/**
 * The intro plays on wide screens (where the phone frame is drawn), on every load, unless the page
 * says `?intro=off`. Automated browsers and people who prefer less motion skip it (`?intro=on` forces it).
 */
function introAllowed(): boolean {
  try {
    const flag = new URLSearchParams(window.location.search).get("intro");
    if (flag === "off") return false;
    if (!window.matchMedia("(min-width: 700px) and (min-height: 600px)").matches) return false;
    if (flag === "on") return true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    return !navigator.webdriver;
  } catch {
    return false;
  }
}

/**
 * A phone around the app, for laptops and projectors. It is drawn only on wide screens (see
 * styles.css); on a real phone it disappears and the app fills the screen. Looks only: nothing in
 * here changes how the app works.
 */
export function DeviceFrame({ children }: { children: ReactNode }) {
  const { route } = useApp();
  const time = useClock();
  const [intro, setIntro] = useState(introAllowed);
  const [run, setRun] = useState(0);
  const dark = route.screen === "talk"; // the Talk page is forest green: the status bar follows it

  return (
    <div className="device-stage">
      <div className="device">
        <span className="device-btn device-btn-power" aria-hidden="true" />
        <span className="device-btn device-btn-volume" aria-hidden="true" />
        <div className="device-screen">
          <div className={`status-bar ${dark ? "dark" : ""}`} aria-hidden="true">
            <span className="status-time">{time}</span>
            <span className="status-camera" />
            <StatusIcons />
          </div>
          {children}
          <div className={`nav-bar ${dark ? "dark" : ""}`} aria-hidden="true">
            <span />
          </div>
          {intro && <PhoneIntro key={run} onDone={() => setIntro(false)} />}
        </div>
      </div>
      <button
        type="button"
        className="intro-replay"
        onClick={() => {
          setRun((n) => n + 1);
          setIntro(true);
        }}
      >
        ↻ Replay intro
      </button>
    </div>
  );
}
