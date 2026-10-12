import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { property, query, state } from "lit/decorators.js";
import type {
  CardsMsg,
  ClientMessage,
  ErrorMsg,
  GoalListMsg,
  OrderMsg,
  PaymentRequestMsg,
  ReadbackMsg,
  ServerMessage,
  StateMsg,
  UiCart,
  UiDelivery,
} from "./types/messages.generated";
import { FRAME, SessionClient, routeServerMessage, type ClientStatus, type FrameType } from "./protocol/client";
import { NetQualityReporter } from "./protocol/net-quality";
import { AudioPlayback } from "./audio/playback";
import { CaptureStartError, MicCapture } from "./audio/capture";
import { AvatarPlayer, type AvatarAudio } from "./avatar/avatar-player";
import shopkeeperUrl from "./avatar/shopkeeper.svg?url";
import { base, tokens } from "./styles/tokens";
import { define } from "./define";
import type { TtbCaptions } from "./captions/captions";
import type { TtbCartView, Pace } from "./cards/cart-view";
import "./captions/captions";
import "./captions/text-input";
import "./cards/cart-view";
import "./cards/goal-list";
import "./checkout/readback";
import "./checkout/confirmation";
import "./camera/camera";
import "./protocol/net-quality";

export type MediaMode = "avatar" | "audio_only";

export interface CartChangedDetail {
  cart: UiCart;
}
export interface PaymentRequestedDetail {
  checkout_id: string;
  total: number;
  currency: "INR";
  item_count: number;
  delivery: UiDelivery;
}
export interface OrderPlacedDetail {
  order_id: string;
  delivery: UiDelivery;
}
export interface SessionEndedDetail {
  reason: string;
}
export interface PaymentMandate {
  checkout_mandate: string;
  payment_mandate: string;
  [k: string]: unknown;
}
export interface PaymentResult {
  checkout_id: string;
  approved: boolean;
  mandate?: PaymentMandate | null;
}

type Phase = "idle" | "connecting" | "live" | "reconnecting" | "ended";

const boolAttr = {
  fromAttribute: (v: string | null) => v === null || v.toLowerCase() !== "false",
  toAttribute: (v: boolean) => (v ? "true" : "false"),
};

function fmtTime(s: number): string {
  const v = Math.max(0, Math.floor(s));
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, "0")}`;
}

/**
 * <talktobuy-assistant>: the embeddable Hindi voice + avatar shopping assistant
 * (specs/001-talktobuy-assistant/contracts/widget-protocol.md).
 *
 * Attributes: ticket, ticket-url, server-url, language, show-translation, media-mode, avatar-audio.
 * Events: ttb:cart-changed, ttb:payment-requested, ttb:order-placed, ttb:session-ended.
 * Method: resolvePayment({checkout_id, approved, mandate}).
 */
export class TalkToBuyAssistant extends LitElement {
  static styles = [
    tokens,
    base,
    css`
      :host {
        display: block;
        background: var(--ttb-bg);
        border-radius: var(--ttb-radius);
        border: 2px solid var(--ttb-border);
        padding: var(--ttb-space);
        container-type: inline-size;
      }
      .bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ttb-space-small);
        margin-bottom: var(--ttb-space);
      }
      .ai-label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        min-height: 36px;
        border-radius: 999px;
        background: var(--ttb-primary);
        color: var(--ttb-on-primary);
        font-weight: 800;
        font-size: var(--ttb-font-body);
      }
      .badge {
        display: inline-flex;
        align-items: center;
        min-height: 36px;
        padding: 4px 12px;
        border-radius: 999px;
        border: 2px solid var(--ttb-border);
        background: var(--ttb-surface);
        font-weight: 700;
        font-size: var(--ttb-font-body);
      }
      .spacer {
        flex: 1;
      }
      .stage {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: var(--ttb-space);
      }
      @container (min-width: 720px) {
        .stage {
          grid-template-columns: minmax(240px, 2fr) minmax(0, 3fr);
          align-items: start;
        }
      }
      .avatar {
        position: relative;
        border-radius: var(--ttb-radius);
        overflow: hidden;
        background: var(--ttb-surface-alt);
        aspect-ratio: 1 / 1;
        max-width: 420px;
        width: 100%;
        justify-self: center;
      }
      .avatar video,
      .avatar img {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .avatar video[hidden],
      .avatar img[hidden] {
        display: none;
      }
      .working {
        position: absolute;
        left: 8px;
        right: 8px;
        bottom: 8px;
        padding: 8px 12px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-surface);
        color: var(--ttb-text);
        font-weight: 700;
        box-shadow: var(--ttb-shadow);
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .dots::after {
        content: "…";
        animation: blink 1.2s infinite;
      }
      @keyframes blink {
        50% {
          opacity: 0.2;
        }
      }
      .side {
        display: flex;
        flex-direction: column;
        gap: var(--ttb-space);
        min-width: 0;
      }
      .start {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--ttb-space);
        text-align: center;
      }
      .start .avatar {
        max-width: 280px;
      }
      button.start-btn {
        min-height: 72px;
        padding: 12px 28px;
        font-size: var(--ttb-font-large);
        border-radius: var(--ttb-radius);
        display: inline-flex;
        flex-direction: column;
        align-items: center;
      }
      .start-btn .en {
        font-size: var(--ttb-font-body);
        font-weight: 600;
      }
      .hint {
        margin: 0;
        color: var(--ttb-muted);
        max-width: 36em;
      }
      .banner {
        padding: 10px 14px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-warning-soft);
        border: 2px solid var(--ttb-border);
        margin: 0 0 var(--ttb-space);
      }
      .banner.error {
        border-color: var(--ttb-danger);
      }
      .en {
        color: var(--ttb-translation);
        font-size: var(--ttb-font-small);
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ttb-space);
        margin-top: var(--ttb-space);
      }
      button.end {
        border-color: var(--ttb-danger);
        color: var(--ttb-danger);
      }
    `,
  ];

  @property() ticket: string | null = null;
  @property({ attribute: "ticket-url" }) ticketUrl: string | null = null;
  @property({ attribute: "server-url" }) serverUrl: string | null = null;
  @property() language = "hi";
  @property({ attribute: "show-translation", converter: boolAttr, reflect: true }) showTranslation = true;
  @property({ attribute: "media-mode" }) mediaMode: MediaMode = "avatar";
  @property({ attribute: "avatar-audio" }) avatarAudio: AvatarAudio = "separate";

  @state() private phase: Phase = "idle";
  @state() private pace: Pace = "guided";
  @state() private serverMode: MediaMode | null = null;
  @state() private safetyHold = false;
  @state() private remaining: number | null = null;
  @state() private working: { label_hi?: string; label_en?: string } | null = null;
  @state() private cart: UiCart | null = null;
  @state() private goal: GoalListMsg | null = null;
  @state() private readback: ReadbackMsg | null = null;
  @state() private pendingPayment: PaymentRequestMsg | null = null;
  @state() private order: OrderMsg | null = null;
  @state() private familyName: string | null = null;
  @state() private error: ErrorMsg | null = null;
  @state() private micProblem: "denied" | "unavailable" | "unsupported" | null = null;
  @state() private avatarFailed = false;
  @state() private avatarPlaying = false;

  @query("ttb-captions") private captions?: TtbCaptions;
  @query("ttb-cart-view") private cartView?: TtbCartView;
  @query("video.avatar-video") private videoEl?: HTMLVideoElement;

  private client: SessionClient | null = null;
  private playback = new AudioPlayback();
  private mic: MicCapture | null = null;
  private avatar: AvatarPlayer | null = null;
  private net: NetQualityReporter | null = null;
  private tick: ReturnType<typeof setInterval> | null = null;
  private endedEmitted = false;
  /** Messages/frames that arrive before the live view has rendered are held here. */
  private pending: Array<() => void> | null = null;

  /** Effective media mode: the server's word wins once a `state` arrives. */
  get effectiveMode(): MediaMode {
    if (this.avatarFailed) return "audio_only";
    return this.serverMode ?? (this.mediaMode === "audio_only" ? "audio_only" : "avatar");
  }

  // ---------------------------------------------------------------- public API

  /** Called by the host app's payment step (trusted surface) with the shopper's decision. */
  resolvePayment(result: PaymentResult): boolean {
    const msg: ClientMessage = {
      type: "payment_result",
      checkout_id: result.checkout_id,
      approved: !!result.approved,
      mandate: result.approved ? (result.mandate ?? null) : null,
    };
    const ok = this.client?.send(msg) ?? false;
    if (this.pendingPayment?.checkout_id === result.checkout_id) this.pendingPayment = null;
    return ok;
  }

  /** Start the session (same as tapping the start button). Must run in a user gesture. */
  async start(): Promise<void> {
    if (this.phase === "connecting" || this.phase === "live" || this.phase === "reconnecting") return;
    this.resetSessionState();
    this.phase = "connecting";
    // Create the playback AudioContext inside the gesture so autoplay is allowed.
    void this.playback.resume().catch(() => undefined);

    this.mic = new MicCapture((pcm) => this.client?.sendBinary(FRAME.MIC_PCM, pcm));
    try {
      await this.mic.start();
      this.micProblem = null;
    } catch (err) {
      this.micProblem = err instanceof CaptureStartError ? err.kind : "unavailable";
      this.mic = null;
    }

    this.client = new SessionClient({
      serverUrl: this.serverUrl,
      getTicket: () => this.getTicket(),
      onMessage: (m) => this.gate(() => this.onServerMessage(m)),
      onBinary: (t, p) => {
        if (this.pending) {
          const copy = p.slice();
          this.pending.push(() => this.onBinary(t, copy));
        } else this.onBinary(t, p);
      },
      onStatus: (s, d) => this.onStatus(s, d),
    });
    await this.client.connect();
  }

  /** End the session (shopper closed the assistant). */
  end(reason = "shopper_ended"): void {
    if (this.client) {
      this.client.send({ type: "end" });
      const c = this.client;
      this.client = null;
      setTimeout(() => c.close(1000, reason), 150);
    }
    this.teardown();
    this.phase = "ended";
    this.emitEnded(reason);
  }

  /** Send a typed message (FR-003). */
  sendText(text: string): boolean {
    const t = text.trim().slice(0, 500);
    if (!t) return false;
    return this.client?.send({ type: "text", text: t }) ?? false;
  }

  // ---------------------------------------------------------------- lifecycle

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.client) this.end("element_removed");
    this.playback.close();
  }

  protected updated(changed: PropertyValues<this>): void {
    if (changed.has("showTranslation") && changed.get("showTranslation") !== undefined) {
      this.client?.send({ type: "set_translation", on: this.showTranslation });
    }
    if (changed.has("avatarAudio")) this.avatar?.setAudioMode(this.avatarAudio);
  }

  // ---------------------------------------------------------------- session plumbing

  private async getTicket(): Promise<string> {
    if (this.ticketUrl) {
      const res = await fetch(this.ticketUrl, { method: "POST", credentials: "same-origin" });
      if (!res.ok) throw new Error(`ticket ${res.status}`);
      const body = (await res.json()) as { ticket?: string };
      if (!body.ticket) throw new Error("no ticket in response");
      return body.ticket;
    }
    if (this.ticket) return this.ticket;
    throw new Error("no ticket or ticket-url");
  }

  private gate(f: () => void): void {
    if (this.pending) this.pending.push(f);
    else f();
  }

  private onStatus(status: ClientStatus, detail?: { code?: number; reason?: string }): void {
    if (status === "open") {
      const firstOpen = this.phase !== "live" && this.phase !== "reconnecting";
      this.phase = "live";
      if (firstOpen) {
        // Hold incoming traffic until captions, cart view and the <video> exist
        // (updateComplete is read after the phase change, so it covers that render).
        this.pending = [];
        void this.updateComplete.then(() => {
          const q = this.pending ?? [];
          this.pending = null;
          q.forEach((f) => f());
        });
      }
      this.mic?.setMuted(false);
      this.client?.send({ type: "set_translation", on: this.showTranslation });
      if (this.mediaMode === "audio_only") this.client?.send({ type: "set_media_mode", mode: "audio_only" });
      this.net?.stop();
      this.net = new NetQualityReporter({
        underruns: () => this.playback.underruns,
        rttMs: () => this.client?.handshakeMs ?? null,
        send: (m) => this.client?.send(m),
      });
      this.net.start();
      this.startTick();
    } else if (status === "reconnecting") {
      if (this.phase === "live") this.phase = "reconnecting";
      this.mic?.setMuted(true);
      this.playback.flush();
      this.net?.stop();
    } else if (status === "closed") {
      if (!this.client) return; // we closed it ourselves in end()
      this.client = null;
      this.teardown();
      this.phase = "ended";
      this.emitEnded(detail?.reason || (detail?.code ? `closed_${detail.code}` : "closed"));
    }
  }

  private onBinary(type: FrameType, payload: Uint8Array): void {
    if (type === FRAME.ASSISTANT_PCM) {
      // With muxed avatar audio the MP4 carries the voice; play 0x11 only when it is the voice.
      const muxedAvatar = this.effectiveMode === "avatar" && this.avatarAudio === "muxed";
      if (!muxedAvatar) this.playback.enqueue(payload);
    } else if (type === FRAME.AVATAR_MP4) {
      if (this.effectiveMode !== "avatar") return;
      this.ensureAvatar()?.append(payload);
    }
  }

  private ensureAvatar(): AvatarPlayer | null {
    if (this.avatar) return this.avatar;
    const video = this.videoEl;
    if (!video) return null;
    this.avatar = new AvatarPlayer(video, {
      audio: this.avatarAudio,
      onPlaying: () => (this.avatarPlaying = true),
      onFailure: () => {
        this.avatarFailed = true;
        this.avatarPlaying = false;
        this.avatar?.destroy();
        this.avatar = null;
        // Ask the server for audio-only so the voice arrives as 0x11 PCM.
        this.client?.send({ type: "set_media_mode", mode: "audio_only" });
      },
    });
    return this.avatar;
  }

  private dropAvatar(): void {
    this.avatar?.destroy();
    this.avatar = null;
    this.avatarPlaying = false;
  }

  /** Visible for tests: route one server message. */
  onServerMessage(msg: ServerMessage): void {
    routeServerMessage(msg, {
      caption: (m) => this.captions?.upsert(m),
      interrupted: (m) => {
        this.playback.flush();
        this.avatar?.flush();
        this.captions?.markInterrupted(m.turn_id);
      },
      cards: (m: CardsMsg) => this.cartView?.showCards(m),
      goal_list: (m) => (this.goal = m),
      cart: (m) => {
        this.cart = m.cart;
        this.cartView?.setCart(m.cart);
        this.emit<CartChangedDetail>("ttb:cart-changed", { cart: m.cart });
      },
      readback: (m) => {
        this.readback = m;
        this.order = null;
      },
      payment_request: (m) => {
        this.pendingPayment = m;
        this.emit<PaymentRequestedDetail>("ttb:payment-requested", {
          checkout_id: m.checkout_id,
          total: m.total,
          currency: m.currency,
          item_count: m.item_count,
          delivery: m.delivery,
        });
      },
      order: (m) => {
        this.order = m;
        this.pendingPayment = null;
        this.emit<OrderPlacedDetail>("ttb:order-placed", { order_id: m.order_id, delivery: m.delivery });
      },
      family_notified: (m) => (this.familyName = m.contact_name),
      state: (m: StateMsg) => {
        this.pace = m.pace;
        this.safetyHold = m.safety_hold;
        this.remaining = m.remaining_s;
        if (m.media_mode !== this.serverMode) {
          if (m.media_mode === "audio_only") this.dropAvatar();
          this.serverMode = m.media_mode;
        }
      },
      working: (m) => (this.working = m.on ? { label_hi: m.label_hi, label_en: m.label_en } : null),
      error: (m) => (this.error = m),
    });
  }

  private startTick(): void {
    if (this.tick) return;
    this.tick = setInterval(() => {
      if (this.remaining !== null && this.remaining > 0 && this.phase === "live") this.remaining -= 1;
    }, 1000);
  }

  private teardown(): void {
    this.mic?.stop();
    this.mic = null;
    this.net?.stop();
    this.net = null;
    this.playback.flush();
    this.dropAvatar();
    if (this.tick) clearInterval(this.tick);
    this.tick = null;
    this.working = null;
    this.renderRoot.querySelector("ttb-camera")?.stop();
  }

  private resetSessionState(): void {
    this.endedEmitted = false;
    this.error = null;
    this.avatarFailed = false;
    this.serverMode = null;
    this.readback = null;
    this.pendingPayment = null;
    this.order = null;
    this.familyName = null;
    this.goal = null;
    this.working = null;
    this.remaining = null;
    this.captions?.clear();
  }

  private emitEnded(reason: string): void {
    if (this.endedEmitted) return;
    this.endedEmitted = true;
    this.emit<SessionEndedDetail>("ttb:session-ended", { reason });
  }

  private emit<T>(name: string, detail: T): void {
    this.dispatchEvent(new CustomEvent<T>(name, { detail, bubbles: true, composed: true }));
  }

  private setMode(mode: MediaMode): void {
    this.client?.send({ type: "set_media_mode", mode });
    if (mode === "avatar") this.avatarFailed = false;
    // Optimistic local switch; the server confirms with `state`.
    if (mode === "audio_only") this.dropAvatar();
    this.serverMode = mode;
  }

  // ---------------------------------------------------------------- render

  private renderBar() {
    const live = this.phase === "live" || this.phase === "reconnecting";
    return html`
      <div class="bar">
        <span class="ai-label" role="note" aria-label="AI सहायक — यह एक AI है, इंसान नहीं / AI assistant, not a human">
          <span aria-hidden="true">🤖</span> AI सहायक / AI assistant
        </span>
        ${live
          ? html`<span class="badge" aria-label=${`रफ़्तार: ${this.pace === "guided" ? "धीरे-धीरे" : "जल्दी"}`}>
              ${this.pace === "guided" ? "धीरे-धीरे / Step by step" : "जल्दी / Quick"}
            </span>`
          : nothing}
        ${live && this.remaining !== null
          ? html`<span class="badge" role="timer" aria-label=${`बचा समय ${fmtTime(this.remaining)}`}
              >⏱ बचा समय ${fmtTime(this.remaining)}</span
            >`
          : nothing}
        <span class="spacer"></span>
        ${live
          ? html`<ttb-media-toggle
                .mode=${this.effectiveMode}
                @ttb-media-mode=${(e: CustomEvent<{ mode: MediaMode }>) => this.setMode(e.detail.mode)}
              ></ttb-media-toggle>
              <button class="end" type="button" @click=${() => this.end()}>बंद करें / End</button>`
          : nothing}
      </div>
    `;
  }

  private renderAvatar() {
    const showVideo = this.effectiveMode === "avatar" && this.avatarPlaying;
    return html`
      <div class="avatar">
        <video class="avatar-video" ?hidden=${!showVideo} playsinline autoplay muted aria-label="दुकानदार (AI अवतार) / Shopkeeper (AI avatar)"></video>
        <img src=${shopkeeperUrl} alt="दुकानदार का चित्र / Shopkeeper illustration" ?hidden=${showVideo} />
        ${this.working
          ? html`<div class="working" role="status" aria-live="polite">
              <span lang="hi">${this.working.label_hi || "देख रहे हैं"}<span class="dots"></span></span>
              ${this.showTranslation ? html`<span class="en" lang="en">${this.working.label_en || "Working…"}</span>` : nothing}
            </div>`
          : nothing}
      </div>
    `;
  }

  private renderIdle() {
    const ended = this.phase === "ended";
    return html`
      <div class="start">
        <div class="avatar"><img src=${shopkeeperUrl} alt="दुकानदार का चित्र / Shopkeeper illustration" /></div>
        ${ended
          ? html`<p class="hint" role="status">बातचीत ख़त्म हुई। धन्यवाद! <span class="en" lang="en">Conversation ended. Thank you!</span></p>`
          : nothing}
        <button class="primary start-btn" type="button" ?disabled=${this.phase === "connecting"} @click=${() => void this.start()}>
          <span lang="hi">${this.phase === "connecting" ? "जुड़ रहे हैं…" : "दुकानदार से बात करें"}</span>
          <span class="en" lang="en">${this.phase === "connecting" ? "Connecting…" : "Talk to the shopkeeper"}</span>
        </button>
        <p class="hint" lang="hi">
          बटन दबाने पर माइक की अनुमति माँगी जाएगी। आप लिखकर भी बात कर सकते हैं।
          <span class="en" lang="en">Tapping asks for microphone permission. You can also type.</span>
        </p>
      </div>
    `;
  }

  private renderBanners() {
    return html`
      ${this.phase === "reconnecting"
        ? html`<p class="banner" role="status">फिर से जुड़ रहे हैं… <span class="en" lang="en">Reconnecting…</span></p>`
        : nothing}
      ${this.micProblem && (this.phase === "live" || this.phase === "connecting")
        ? html`<p class="banner" role="status" lang="hi">
            माइक नहीं मिला — नीचे लिखकर बात कीजिए।
            <span class="en" lang="en">Microphone not available: please type below.</span>
          </p>`
        : nothing}
      ${this.safetyHold
        ? html`<p class="banner" role="status" lang="hi">
            आपकी सेहत पहले — अभी खरीदारी रुकी है।
            <span class="en" lang="en">Your health first: shopping is paused.</span>
          </p>`
        : nothing}
      ${this.error
        ? html`<p class="banner error" role="alert">
            <span lang="hi">${this.error.message_hi}</span>
            ${this.showTranslation ? html`<span class="en" lang="en"> ${this.error.message_en}</span>` : nothing}
            <button type="button" @click=${() => (this.error = null)}>ठीक है / OK</button>
          </p>`
        : nothing}
    `;
  }

  render() {
    const live = this.phase === "live" || this.phase === "reconnecting";
    return html`
      <div lang=${this.language || "hi"}>
        ${this.renderBar()} ${this.renderBanners()}
        ${live
          ? html`
              <div class="stage">
                ${this.renderAvatar()}
                <div class="side">
                  <ttb-captions .showTranslation=${this.showTranslation}></ttb-captions>
                  <ttb-text-input
                    ?disabled=${this.phase !== "live"}
                    @ttb-text=${(e: CustomEvent<{ text: string }>) => this.sendText(e.detail.text)}
                  ></ttb-text-input>
                  <ttb-camera
                    ?disabled=${this.phase !== "live"}
                    @ttb-camera-active=${(e: CustomEvent<{ active: boolean }>) =>
                      this.client?.send({ type: "camera", active: e.detail.active })}
                    @ttb-camera-frame=${(e: CustomEvent<{ jpeg: ArrayBuffer }>) =>
                      this.client?.sendBinary(FRAME.CAMERA_JPEG, e.detail.jpeg)}
                  ></ttb-camera>
                </div>
              </div>
              <div class="panels">
                ${this.order || this.familyName
                  ? html`<ttb-confirmation .order=${this.order} .familyName=${this.familyName}></ttb-confirmation>`
                  : nothing}
                ${this.readback && !this.order
                  ? html`<ttb-readback
                      .readback=${this.readback}
                      .awaitingPayment=${!!this.pendingPayment}
                      .showTranslation=${this.showTranslation}
                    ></ttb-readback>`
                  : nothing}
                ${this.goal ? html`<ttb-goal-list .goal=${this.goal}></ttb-goal-list>` : nothing}
                <ttb-cart-view .pace=${this.pace} .cart=${this.cart}></ttb-cart-view>
              </div>
            `
          : this.renderIdle()}
      </div>
    `;
  }
}

define("talktobuy-assistant", TalkToBuyAssistant);

declare global {
  interface HTMLElementTagNameMap {
    "talktobuy-assistant": TalkToBuyAssistant;
  }
  interface HTMLElementEventMap {
    "ttb:cart-changed": CustomEvent<CartChangedDetail>;
    "ttb:payment-requested": CustomEvent<PaymentRequestedDetail>;
    "ttb:order-placed": CustomEvent<OrderPlacedDetail>;
    "ttb:session-ended": CustomEvent<SessionEndedDetail>;
  }
}
