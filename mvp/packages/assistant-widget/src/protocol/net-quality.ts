import { LitElement, css, html } from "lit";
import { property } from "lit/decorators.js";
import type { NetQualityMsg } from "../types/messages.generated";
import { base } from "../styles/tokens";
import { define } from "../define";

export const NET_QUALITY_INTERVAL_MS = 5000;

interface NetworkInformationLike {
  downlink?: number; // Mbit/s
  rtt?: number; // ms
}

export interface NetQualitySources {
  /** Cumulative underrun counter from AudioPlayback. */
  underruns: () => number;
  /** Latest measured WebSocket RTT in ms, if any. */
  rttMs: () => number | null;
  send: (msg: NetQualityMsg) => void;
  connection?: () => NetworkInformationLike | undefined;
}

/** Build one `net_quality` report. `underruns` is the count since the previous report. */
export function buildNetQuality(
  conn: NetworkInformationLike | undefined,
  rttMs: number | null,
  underrunsDelta: number,
): NetQualityMsg {
  const downlink = typeof conn?.downlink === "number" ? Math.round(conn.downlink * 1000) : null;
  const rtt = rttMs ?? (typeof conn?.rtt === "number" ? conn.rtt : null);
  return { type: "net_quality", downlink_kbps: downlink, rtt_ms: rtt, underruns: Math.max(0, underrunsDelta) };
}

/**
 * Sends `net_quality` every 5 s (T101): Network Information API `downlink`, WebSocket RTT and the
 * number of playback buffer underruns since the last report. The server decides whether to force
 * audio-only (downlink < 1,000 kbps or 3 underruns in 10 s).
 */
export class NetQualityReporter {
  private timer: ReturnType<typeof setInterval> | null = null;
  private lastUnderruns = 0;

  constructor(private readonly src: NetQualitySources) {}

  start(): void {
    this.stop();
    this.lastUnderruns = this.src.underruns();
    this.timer = setInterval(() => this.report(), NET_QUALITY_INTERVAL_MS);
  }

  report(): NetQualityMsg {
    const total = this.src.underruns();
    const conn =
      this.src.connection?.() ?? (navigator as Navigator & { connection?: NetworkInformationLike }).connection;
    const msg = buildNetQuality(conn, this.src.rttMs(), total - this.lastUnderruns);
    this.lastUnderruns = total;
    this.src.send(msg);
    return msg;
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}

/**
 * Manual avatar / audio-only switch (FR-006). Emits `ttb-media-mode` {mode}; the main element
 * sends `set_media_mode`. Shows the server's current mode.
 */
export class TtbMediaToggle extends LitElement {
  static styles = [
    base,
    css`
      button {
        min-width: var(--ttb-tap);
        min-height: var(--ttb-tap);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: var(--ttb-font-small);
        padding: 6px 14px;
      }
      .icon {
        font-size: 22px;
      }
    `,
  ];

  @property() mode: "avatar" | "audio_only" = "avatar";
  @property({ type: Boolean }) disabled = false;

  private flip() {
    const next = this.mode === "avatar" ? "audio_only" : "avatar";
    this.dispatchEvent(new CustomEvent("ttb-media-mode", { detail: { mode: next }, bubbles: true, composed: true }));
  }

  render() {
    const audio = this.mode === "audio_only";
    return html`<button
      type="button"
      ?disabled=${this.disabled}
      aria-pressed=${audio ? "true" : "false"}
      aria-label=${audio ? "वीडियो चालू करें / Turn on avatar video" : "सिर्फ़ आवाज़ / Switch to audio only"}
      @click=${this.flip}
    >
      <span class="icon" aria-hidden="true">${audio ? "🔈" : "🎥"}</span>
      <span>${audio ? "वीडियो चालू करें / Video on" : "सिर्फ़ आवाज़ / Audio only"}</span>
    </button>`;
  }
}

define("ttb-media-toggle", TtbMediaToggle);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-media-toggle": TtbMediaToggle;
  }
}
