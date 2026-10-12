import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { base } from "../styles/tokens";
import { define } from "../define";

export const FRAME_SIZE = 768;
/** ≤ 1 fps: every frame enters model context (T080). */
export const FRAME_INTERVAL_MS = 1000;
const JPEG_QUALITY = 0.75;

type CamState = "off" | "starting" | "on" | "denied" | "unavailable";

/**
 * "दिखाइए / Show item" camera (US4, T080). While on, a preview is shown and ~768×768 JPEG frames
 * are emitted at ≤ 1 fps as `ttb-camera-frame` {jpeg: ArrayBuffer}; turning it on/off emits
 * `ttb-camera-active` {active}. The main element turns these into 0x02 frames and
 * `{type:"camera",active}` messages. If permission is denied, the button is replaced by
 * "बोलकर बताइए" (describe it by voice).
 */
export class TtbCamera extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      .wrap {
        display: flex;
        flex-direction: column;
        gap: var(--ttb-space-small);
        align-items: stretch;
      }
      button.toggle {
        min-height: var(--ttb-tap-large);
        font-size: var(--ttb-font-large);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
      }
      button.toggle[aria-pressed="true"] {
        background: var(--ttb-primary);
        color: var(--ttb-on-primary);
      }
      video {
        width: 100%;
        max-width: 360px;
        aspect-ratio: 1 / 1;
        object-fit: cover;
        border-radius: var(--ttb-radius);
        background: #000;
        align-self: center;
      }
      .note {
        margin: 0;
        font-size: var(--ttb-font-card);
        padding: 8px 12px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-surface-alt);
      }
      .en {
        font-size: var(--ttb-font-small);
        color: var(--ttb-translation);
      }
    `,
  ];

  /** Disable while the session is not connected. */
  @property({ type: Boolean }) disabled = false;
  @state() private cam: CamState = "off";
  private stream: MediaStream | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private busy = false;

  get active(): boolean {
    return this.cam === "on";
  }

  async toggle(): Promise<void> {
    if (this.cam === "on" || this.cam === "starting") this.stop();
    else await this.start();
  }

  async start(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) {
      this.cam = "unavailable";
      return;
    }
    this.cam = "starting";
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
    } catch (err) {
      const name = (err as DOMException)?.name;
      this.cam = name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unavailable";
      return;
    }
    if (this.cam !== "starting") {
      // Turned off while the prompt was open.
      this.releaseStream();
      return;
    }
    this.cam = "on";
    await this.updateComplete;
    const video = this.renderRoot.querySelector("video");
    if (video) {
      video.srcObject = this.stream;
      void video.play().catch(() => undefined);
    }
    this.emit("ttb-camera-active", { active: true });
    this.timer = setInterval(() => void this.capture(), FRAME_INTERVAL_MS);
  }

  stop(): void {
    const wasOn = this.cam === "on";
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.releaseStream();
    if (this.cam === "on" || this.cam === "starting") this.cam = "off";
    if (wasOn) this.emit("ttb-camera-active", { active: false });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.stop();
  }

  private releaseStream() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
  }

  /** Center-crop to a square and encode ~768×768 JPEG. */
  private async capture(): Promise<void> {
    if (this.cam !== "on" || this.busy) return;
    const video = this.renderRoot.querySelector("video");
    if (!video || video.readyState < 2 || !video.videoWidth) return;
    this.busy = true;
    try {
      const c = (this.canvas ??= document.createElement("canvas"));
      c.width = FRAME_SIZE;
      c.height = FRAME_SIZE;
      const ctx = c.getContext("2d");
      if (!ctx) return;
      const side = Math.min(video.videoWidth, video.videoHeight);
      const sx = (video.videoWidth - side) / 2;
      const sy = (video.videoHeight - side) / 2;
      ctx.drawImage(video, sx, sy, side, side, 0, 0, FRAME_SIZE, FRAME_SIZE);
      const blob = await new Promise<Blob | null>((res) => c.toBlob(res, "image/jpeg", JPEG_QUALITY));
      if (blob && this.cam === "on") this.emit("ttb-camera-frame", { jpeg: await blob.arrayBuffer() });
    } finally {
      this.busy = false;
    }
  }

  private emit(name: string, detail: unknown) {
    this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
  }

  render() {
    if (this.cam === "denied" || this.cam === "unavailable") {
      return html`<p class="note" role="status" lang="hi">
        बोलकर बताइए — कौन-सा सामान चाहिए।<br /><span class="en" lang="en">Camera not available: please describe the item by voice.</span>
      </p>`;
    }
    const on = this.cam === "on" || this.cam === "starting";
    return html`
      <div class="wrap">
        <button
          class="toggle"
          type="button"
          aria-pressed=${on ? "true" : "false"}
          ?disabled=${this.disabled}
          @click=${() => void this.toggle()}
        >
          <span aria-hidden="true">📷</span>
          ${on ? "कैमरा बंद करें / Stop showing" : "दिखाइए / Show item"}
        </button>
        ${on
          ? html`<video muted playsinline autoplay aria-label="कैमरा का दृश्य / Camera preview"></video>
              <p class="note" lang="hi">सामान कैमरे के सामने रखिए। <span class="en" lang="en">Hold the item up to the camera.</span></p>`
          : nothing}
      </div>
    `;
  }
}

define("ttb-camera", TtbCamera);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-camera": TtbCamera;
  }
}
