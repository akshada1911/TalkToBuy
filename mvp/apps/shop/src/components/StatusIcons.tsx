import { useEffect, useState } from "react";

export function clock(): string {
  const d = new Date();
  return `${d.getHours() % 12 || 12}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** The current time, refreshed every few seconds. */
export function useClock(): string {
  const [time, setTime] = useState(clock);
  useEffect(() => {
    const id = setInterval(() => setTime(clock()), 15_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

/** Signal, Wi-Fi and battery, drawn in the current text colour. */
export function StatusIcons() {
  return (
    <span className="status-icons">
      <svg width="16" height="12" viewBox="0 0 16 12" fill="currentColor">
        <rect x="0" y="8" width="3" height="4" rx="1" />
        <rect x="4.3" y="5.5" width="3" height="6.5" rx="1" />
        <rect x="8.6" y="3" width="3" height="9" rx="1" />
        <rect x="12.9" y="0" width="3" height="12" rx="1" />
      </svg>
      <svg width="16" height="12" viewBox="0 0 16 12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M1.5 4.2a9.5 9.5 0 0 1 13 0" />
        <path d="M4 7a6 6 0 0 1 8 0" />
        <circle cx="8" cy="10" r="1" fill="currentColor" stroke="none" />
      </svg>
      <svg width="24" height="12" viewBox="0 0 24 12" fill="none">
        <rect x="0.75" y="0.75" width="20" height="10.5" rx="3" stroke="currentColor" strokeWidth="1.5" />
        <rect x="2.5" y="2.5" width="14" height="7" rx="1.6" fill="currentColor" />
        <rect x="22" y="4" width="1.8" height="4" rx="0.9" fill="currentColor" />
      </svg>
    </span>
  );
}
