import { useEffect, useRef, useState } from "react";
import { useApp, type PlacedOrder } from "../state";

const MIN_SCAN_MS = 1400; // the fingerprint always gets a short, visible "scan", even when the check is instant
const SUCCESS_MS = 1900;
const GIVE_UP_MS = 60_000;

/** Pay.tsx starts the animation when the shopper presses pay, and stops it if the payment fails. */
export const payFx = {
  start: () => window.dispatchEvent(new Event("ttb:payfx-start")),
  stop: () => window.dispatchEvent(new Event("ttb:payfx-stop")),
};

let audio: AudioContext | null = null;

/** Unlock sound while we are inside the shopper's tap. */
function prepareChime() {
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    audio = audio ?? new Ctx();
    void audio.resume();
  } catch {
    /* no sound */
  }
}

/** A short, soft two-note "done" chime, and a tiny buzz on phones that can. */
function chime() {
  try {
    navigator.vibrate?.(40);
  } catch {
    /* no vibration */
  }
  try {
    if (!audio) return;
    const t0 = audio.currentTime;
    [660, 990].forEach((freq, i) => {
      const osc = audio!.createOscillator();
      const gain = audio!.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      const start = t0 + i * 0.13;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.05, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.28);
      osc.connect(gain).connect(audio!.destination);
      osc.start(start);
      osc.stop(start + 0.3);
    });
  } catch {
    /* no sound */
  }
}

type Phase = "idle" | "scanning" | "success";

/**
 * The payment moment, as a picture: a fingerprint that gets scanned, then a green tick. It only
 * watches what the app already does (a payment was asked for, an order arrived), so it changes
 * nothing about how payment works.
 */
export function PayFx() {
  const { t, order, paymentRequest } = useApp();
  const [phase, setPhase] = useState<Phase>("idle");
  const startedAt = useRef(0);
  const baseOrder = useRef<PlacedOrder | null>(null);
  const orderRef = useRef<PlacedOrder | null>(order);
  orderRef.current = order;

  useEffect(() => {
    const onStart = () => {
      prepareChime();
      startedAt.current = Date.now();
      baseOrder.current = orderRef.current;
      setPhase("scanning");
    };
    const onStop = () => setPhase("idle");
    window.addEventListener("ttb:payfx-start", onStart);
    window.addEventListener("ttb:payfx-stop", onStop);
    return () => {
      window.removeEventListener("ttb:payfx-start", onStart);
      window.removeEventListener("ttb:payfx-stop", onStop);
    };
  }, []);

  // A new order arrived while scanning: finish the scan, then show the tick.
  useEffect(() => {
    if (phase !== "scanning" || !order || order === baseOrder.current) return;
    const wait = Math.max(0, MIN_SCAN_MS - (Date.now() - startedAt.current));
    const id = setTimeout(() => {
      setPhase("success");
      chime();
    }, wait);
    return () => clearTimeout(id);
  }, [phase, order]);

  // The payment was turned down or timed out (no payment waiting, no new order): drop the animation.
  useEffect(() => {
    if (phase === "scanning" && !paymentRequest && order === baseOrder.current) setPhase("idle");
  }, [phase, paymentRequest, order]);

  useEffect(() => {
    if (phase === "success") {
      const id = setTimeout(() => setPhase("idle"), SUCCESS_MS);
      return () => clearTimeout(id);
    }
    if (phase === "scanning") {
      const id = setTimeout(() => setPhase("idle"), GIVE_UP_MS);
      return () => clearTimeout(id);
    }
  }, [phase]);

  if (phase === "idle") return null;
  const done = phase === "success";

  return (
    <div className={`payfx ${done ? "done" : ""}`} role="status" aria-live="polite">
      <div className="payfx-stage">
        {done ? (
          <svg className="payfx-tick" viewBox="0 0 120 120" aria-hidden="true">
            <circle className="payfx-tick-disc" cx="60" cy="60" r="52" />
            <path className="payfx-tick-mark" d="M36 62 L54 80 L86 44" />
          </svg>
        ) : (
          <div className="payfx-finger" aria-hidden="true">
            <span className="payfx-ring r1" />
            <span className="payfx-ring r2" />
            <svg viewBox="0 0 120 120" className="payfx-print">
              <g fill="none" strokeWidth="5" strokeLinecap="round">
                <path d="M26 56a34 34 0 0 1 68 0" />
                <path d="M36 60a24 24 0 0 1 48 0c0 14 2 22 6 30" />
                <path d="M46 62a14 14 0 0 1 28 0c0 14 2 28 8 40" />
                <path d="M58 62a2 2 0 0 1 4 0c0 18 2 30 6 42" />
                <path d="M36 74c0 12-2 22-6 30" />
                <path d="M26 70c0 14-2 24-6 32" />
              </g>
            </svg>
            <span className="payfx-scan" />
          </div>
        )}
        <b className="payfx-title">{done ? t("trackTag0") : t("payFxScanning")}</b>
        <span className="payfx-sub">{done ? t("payFxDone") : t("payFxHint")}</span>
      </div>
    </div>
  );
}
