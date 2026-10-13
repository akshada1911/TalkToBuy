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
  UiAddress,
  UiCart,
  UiDelivery,
} from "./types/messages.generated";
import { FRAME, SessionClient, routeServerMessage, type ClientStatus, type FrameType } from "./protocol/client";
import { NetQualityReporter } from "./protocol/net-quality";
import { AudioPlayback } from "./audio/playback";
import { CaptureStartError, MicCapture } from "./audio/capture";
import { AvatarPlayer, type AvatarAudio } from "./avatar/avatar-player";
import shopkeeperUrl from "./avatar/shopkeeper.png?url";
import { base, tokens } from "./styles/tokens";
import { define } from "./define";
import { tr } from "./i18n";
import type { TtbCaptions } from "./captions/captions";
import type { TtbCartView, Pace } from "./cards/cart-view";
import type { TtbCamera } from "./camera/camera";
import "./captions/captions";
import "./captions/text-input";
import "./cards/cart-view";
import "./cards/goal-list";
import "./checkout/address-picker";
import type { NewAddressFields } from "./checkout/address-picker";
import "./checkout/readback";
import "./checkout/confirmation";
import "./camera/camera";
import "./protocol/net-quality";

export type MediaMode = "avatar" | "audio_only";

export interface CartChangedDetail {
  cart: UiCart;
  /** The store cart this is (null when there is no cart any more: cancelled or ordered). */
  cart_id: string | null;
}
export interface PaymentRequestedDetail {
  checkout_id: string;
  total: number;
  currency: "INR";
  item_count: number;
  delivery: UiDelivery;
  /** The chosen delivery address, e.g. "Home: Flat 12, Kothrud, Pune 411038". */
  address_text?: string;
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
export type WidgetPhase = Phase;
/** "page" fills its container; "sheet" is the compact bottom-sheet layout (no cart panel). */
export type WidgetLayout = "page" | "sheet";
export interface PhaseDetail {
  phase: Phase;
}

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
 * Events: ttb:cart-changed, ttb:payment-requested, ttb:payment-cancelled, ttb:order-placed, ttb:session-ended,
 * ttb:phase, ttb:open-cart.
 * Method: resolvePayment({checkout_id, approved, mandate}).
 */
export class TalkToBuyAssistant extends LitElement {
  static styles = [
    tokens,
    base,
    css`
      :host {
        display: block;
        position: relative;
        height: 100%;
        min-height: 0;
        overflow: hidden;
        background: var(--ttb-forest);
        color: #ffffff;
      }
      .root {
        height: 100%;
        display: flex;
        flex-direction: column;
        min-height: 0;
      }
      /* The scrolling part: orb + status, the conversation, any checkout panels, the cart. */
      .scroller {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 58px 16px 8px;
      }
      .scroller::-webkit-scrollbar {
        display: none;
      }
      .hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding-top: 6px;
      }
      .orb {
        position: relative;
        width: 120px;
        height: 120px;
        flex: none;
        color: var(--ttb-amber);
      }
      .orb img,
      .orb video {
        position: relative;
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover;
        border-radius: 50%;
        border: 3px solid var(--ttb-amber);
        background: var(--ttb-forest-2);
      }
      .orb video[hidden],
      .orb img[hidden] {
        display: none;
      }
      .ring {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        border: 2px solid currentColor;
        opacity: 0;
      }
      .orb.live .ring {
        animation: ripple 2.1s ease-out infinite;
      }
      .orb.live .r2 {
        animation-delay: 0.7s;
      }
      .orb.live .r3 {
        animation-delay: 1.4s;
      }
      .orb.speak img {
        animation: bob 1.2s ease-in-out infinite;
      }
      @keyframes ripple {
        0% {
          transform: scale(0.86);
          opacity: 0.6;
        }
        100% {
          transform: scale(1.55);
          opacity: 0;
        }
      }
      @keyframes bob {
        0%,
        100% {
          transform: translateY(0);
        }
        50% {
          transform: translateY(-3px);
        }
      }
      .working {
        position: absolute;
        left: -20px;
        right: -20px;
        bottom: -14px;
        text-align: center;
        font-size: 12px;
        font-weight: 700;
        color: var(--ttb-on-forest);
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
      .status {
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ttb-on-forest);
        text-align: center;
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: center;
        gap: 6px;
      }
      .ai-label,
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 28px;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid rgba(255, 255, 255, 0.28);
        color: #ffffff;
        background: rgba(255, 255, 255, 0.08);
      }
      .ai-label {
        border-color: var(--ttb-amber);
        color: var(--ttb-amber);
      }
      button.end {
        min-width: 0;
        min-height: 28px;
        padding: 2px 12px;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.4);
        background: transparent;
        color: #ffffff;
        font-size: 12px;
      }
      .lines {
        padding: 0 8px;
      }
      /* checkout panels and the cart are light cards on the green page */
      .panels {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .panels > ttb-cart-view[hidden] {
        display: none;
      }
      .panels > ttb-cart-view {
        flex: 1;
        min-height: 150px;
        display: flex;
        flex-direction: column;
      }
      .banner {
        margin: 0;
        padding: 8px 12px;
        border-radius: var(--ttb-radius-small);
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.24);
        font-size: 14px;
      }
      .banner.error {
        border-color: var(--ttb-danger);
        background: rgba(180, 35, 24, 0.25);
      }
      .banner button {
        min-height: 32px;
        margin-left: 8px;
        padding: 2px 12px;
        border-color: #ffffff;
        background: transparent;
        color: #ffffff;
      }
      .en {
        color: var(--ttb-on-forest);
        font-size: 13px;
      }

      /* the bottom dock: suggestion chips, the message box, and the three round controls */
      .dock {
        flex: none;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 8px 16px 14px;
        padding-bottom: calc(14px + env(safe-area-inset-bottom));
      }
      .chips {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        margin: 0 -16px;
        padding: 0 16px;
      }
      .chips::-webkit-scrollbar {
        display: none;
      }
      .chips button {
        flex: none;
        min-width: 0;
        min-height: 40px;
        padding: 0 14px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.08);
        color: #ffffff;
        font-size: 13px;
        font-weight: 600;
        white-space: nowrap;
      }
      .controls {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        align-items: center;
        justify-items: center;
      }
      button.ctl {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        min-width: 0;
        min-height: 60px;
        padding: 0 6px;
        border: 0;
        background: none;
        color: #ffffff;
        font-size: 12px;
        font-weight: 600;
      }
      button.ctl .disc {
        position: relative;
        width: 46px;
        height: 46px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.28);
      }
      button.ctl[aria-pressed="true"] .disc {
        background: var(--ttb-amber);
        color: var(--ttb-forest);
      }
      button.ctl .count {
        position: absolute;
        top: -4px;
        right: -4px;
        min-width: 18px;
        height: 18px;
        padding: 0 4px;
        border-radius: 9px;
        background: var(--ttb-amber);
        color: var(--ttb-forest);
        font-size: 11px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      button.mic {
        width: 76px;
        height: 76px;
        min-width: 0;
        min-height: 0;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 50%;
        background: var(--ttb-amber);
        color: var(--ttb-forest);
      }
      button.mic[aria-pressed="true"] {
        background: rgba(255, 255, 255, 0.18);
        color: #ffffff;
      }
      .eq {
        display: flex;
        align-items: center;
        gap: 4px;
        height: 28px;
      }
      .eq i {
        display: block;
        width: 4px;
        height: 26px;
        border-radius: 2px;
        background: currentColor;
        transform: scaleY(0.3);
        animation: bars 0.9s ease-in-out infinite;
      }
      .eq i:nth-child(2) {
        animation-delay: 0.15s;
      }
      .eq i:nth-child(3) {
        animation-delay: 0.3s;
      }
      .eq i:nth-child(4) {
        animation-delay: 0.45s;
      }
      .eq i:nth-child(5) {
        animation-delay: 0.6s;
      }
      @keyframes bars {
        0%,
        100% {
          transform: scaleY(0.3);
        }
        50% {
          transform: scaleY(1);
        }
      }

      /* idle / ended: the start screen */
      .start {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 58px 24px 24px;
        text-align: center;
      }
      button.start-btn {
        min-height: 60px;
        padding: 0 28px;
        border: 0;
        border-radius: 30px;
        background: var(--ttb-amber);
        color: var(--ttb-forest);
        font-size: 17px;
      }
      .hint {
        margin: 0;
        max-width: 28em;
        font-size: 13px;
        color: var(--ttb-on-forest);
      }
      .headline {
        margin: 0;
        font-family: var(--ttb-font-display);
        font-weight: 600;
        font-size: 21px;
        line-height: 1.22;
      }

      /* layout="sheet": the compact bottom sheet (no cart panel; the shop's buttons sit top right) */
      :host([layout="sheet"]) .scroller {
        padding: 12px 16px 4px;
        gap: 6px;
      }
      :host([layout="sheet"]) .hero {
        flex-direction: row;
        align-items: center;
        gap: 12px;
        padding: 0 108px 0 0;
      }
      :host([layout="sheet"]) .orb {
        width: 48px;
        height: 48px;
      }
      :host([layout="sheet"]) .orb img,
      :host([layout="sheet"]) .orb video {
        border-width: 2px;
      }
      :host([layout="sheet"]) .hero-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
        align-items: flex-start;
        min-width: 0;
      }
      :host([layout="sheet"]) .status {
        text-align: left;
        font-size: 12px;
      }
      :host([layout="sheet"]) .meta {
        justify-content: flex-start;
      }
      :host([layout="sheet"]) .lines {
        --ttb-talk-min: 92px;
        --ttb-talk-size: 19px;
        text-align: left;
        padding: 0 2px;
      }
      :host([layout="sheet"]) .start {
        padding-top: 24px;
      }
      :host([layout="sheet"]) button.mic {
        width: 64px;
        height: 64px;
      }
      :host([layout="sheet"]) .dock {
        gap: 8px;
        padding-top: 4px;
      }
      :host([layout="sheet"]) button.ctl {
        min-height: 52px;
      }
    `,
  ];

  @property() ticket: string | null = null;
  @property({ attribute: "ticket-url" }) ticketUrl: string | null = null;
  @property({ attribute: "server-url" }) serverUrl: string | null = null;
  @property() language = "hi";
  @property({ reflect: true }) layout: WidgetLayout = "page";
  /** The store cart (checkout session) the shop already has: the conversation uses the same cart. */
  @property({ attribute: "cart-id" }) cartId: string | null = null;
  /** The host has hidden the assistant: the microphone is muted so nothing is heard in the background. */
  @property({ type: Boolean, reflect: true }) muted = false;
  /** The shopper's preferred saved address id: highlighted when the assistant asks where to deliver. */
  @property({ attribute: "preferred-address" }) preferredAddress: string | null = null;
  // Cost control: English captions and the avatar are opt-in (judges' screen / demo switch).
  @property({ attribute: "show-translation", converter: boolAttr, reflect: true }) showTranslation = false;
  @property({ attribute: "media-mode" }) mediaMode: MediaMode = "audio_only";
  @property({ attribute: "avatar-audio" }) avatarAudio: AvatarAudio = "separate";

  @state() private phase: Phase = "idle";
  @state() private pace: Pace = "guided";
  @state() private serverMode: MediaMode | null = null;
  @state() private safetyHold = false;
  @state() private remaining: number | null = null;
  @state() private working: { label_hi?: string; label_en?: string } | null = null;
  @state() private cart: UiCart | null = null;
  @state() private goal: GoalListMsg | null = null;
  @state() private addresses: UiAddress[] | null = null;
  @state() private readback: ReadbackMsg | null = null;
  @state() private pendingPayment: PaymentRequestMsg | null = null;
  @state() private order: OrderMsg | null = null;
  @state() private familyName: string | null = null;
  @state() private error: ErrorMsg | null = null;
  @state() private micProblem: "denied" | "unavailable" | "unsupported" | null = null;
  @state() private avatarFailed = false;
  @state() private avatarPlaying = false;
  @state() private micOff = false;
  @state() private hearing = false;
  @state() private talking: "assistant" | "shopper" | null = null;
  @state() private cameraOn = false;

  @query("ttb-captions") private captions?: TtbCaptions;
  @query("ttb-cart-view") private cartView?: TtbCartView;
  @query("ttb-camera") private cameraEl?: TtbCamera;
  @query("video.avatar-video") private videoEl?: HTMLVideoElement;

  private client: SessionClient | null = null;
  private playback = new AudioPlayback();
  private mic: MicCapture | null = null;
  private avatar: AvatarPlayer | null = null;
  private net: NetQualityReporter | null = null;
  private tick: ReturnType<typeof setInterval> | null = null;
  private hearTimer: ReturnType<typeof setInterval> | null = null;
  private endedEmitted = false;
  /** Messages/frames that arrive before the live view has rendered are held here. */
  private pending: Array<() => void> | null = null;

  /** Voice only: the video (avatar) mode is not offered, so the mode is always audio-only. */
  get effectiveMode(): MediaMode {
    return "audio_only";
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

    // Browser voice detection: audio is sent only while the shopper speaks (cost control); when
    // they stop, the server is told so the model can answer without waiting for more audio.
    this.mic = new MicCapture(
      (pcm) => this.client?.sendBinary(FRAME.MIC_PCM, pcm),
      () => this.client?.send({ type: "audio_pause" }),
    );
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
      getMediaMode: () => this.effectiveMode,
      getLanguage: () => (this.language === "en" ? "en" : "hi"),
      getCartId: () => this.cartId,
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

  /** The shop changed the cart by tapping: ask the conversation to re-read it. False if not connected. */
  syncCart(): boolean {
    return this.client?.send({ type: "cart_sync" }) ?? false;
  }

  /** Send a typed message (FR-003). */
  sendText(text: string): boolean {
    const t = text.trim().slice(0, 500);
    if (!t) return false;
    return this.client?.send({ type: "text", text: t }) ?? false;
  }

  /** A tapped saved address: said to the assistant exactly as if the shopper had spoken it. */
  private chooseAddress(a: { id: string; label: string }): void {
    this.sendText(`${tr(this.language, "पता चुना", "Address chosen")}: ${a.label} (${a.id})`);
  }

  /** A new address typed into the form (name, street, area, city, pincode, phone). */
  private addNewAddress(f: NewAddressFields): void {
    const L = this.language;
    this.sendText(
      `${tr(L, "नया पता", "New address")}: ${tr(L, "नाम", "name")} ${f.name}; ${tr(L, "मकान और गली", "house and street")} ${f.line1}; ` +
        `${tr(L, "इलाका", "area")} ${f.area}; ${tr(L, "शहर", "city")} ${f.city}; ` +
        `${tr(L, "पिनकोड", "pincode")} ${f.pincode}; ${tr(L, "फ़ोन", "phone")} ${f.phone}`,
    );
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
    if ((changed as Map<PropertyKey, unknown>).has("muted") || (changed as Map<PropertyKey, unknown>).has("micOff")) this.applyMute();
    if ((changed as Map<PropertyKey, unknown>).has("phase")) this.emit<PhaseDetail>("ttb:phase", { phase: this.phase });
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
      this.applyMute();
      this.startHearing();
      this.client?.send({ type: "set_translation", on: this.showTranslation });
      this.client?.send({ type: "set_media_mode", mode: this.effectiveMode });
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
      caption: (m) => {
        this.captions?.upsert(m);
        this.talking = m.final ? null : m.who;
      },
      interrupted: (m) => {
        this.playback.flush();
        this.avatar?.flush();
        this.captions?.markInterrupted(m.turn_id);
        this.talking = null;
      },
      cards: (m: CardsMsg) => this.cartView?.showCards(m),
      goal_list: (m) => (this.goal = m),
      cart: (m) => {
        this.cart = m.cart;
        this.cartView?.setCart(m.cart);
        this.emit<CartChangedDetail>("ttb:cart-changed", { cart: m.cart, cart_id: m.cart_id ?? null });
        if (m.cart.item_count === 0 && !this.order) {
          // The order was cancelled (or the cart emptied): close the checkout steps.
          if (this.pendingPayment) this.emit<Record<string, never>>("ttb:payment-cancelled", {});
          this.readback = null;
          this.addresses = null;
          this.pendingPayment = null;
          this.goal = null;
        }
      },
      addresses: (m) => {
        this.addresses = m.addresses;
        this.readback = null;
      },
      readback: (m) => {
        this.readback = m;
        this.addresses = null; // an address is chosen: on to the read-back and payment
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
          address_text: m.address_text,
        });
      },
      order: (m) => {
        this.order = m;
        this.pendingPayment = null;
        this.addresses = null;
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

  /** The microphone is heard only while this is live, unmuted by the host and not switched off. */
  private applyMute(): void {
    this.mic?.setMuted(this.muted || this.micOff || this.phase !== "live");
  }

  /** Poll the voice detector so the orb and mic button can show "listening". */
  private startHearing(): void {
    if (this.hearTimer) return;
    this.hearTimer = setInterval(() => {
      const h = !!this.mic?.speaking && !this.muted && !this.micOff;
      if (h !== this.hearing) this.hearing = h;
    }, 150);
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
    if (this.hearTimer) clearInterval(this.hearTimer);
    this.hearTimer = null;
    this.hearing = false;
    this.talking = null;
    this.cameraOn = false;
    this.working = null;
    this.renderRoot.querySelector("ttb-camera")?.stop();
  }

  private resetSessionState(): void {
    this.endedEmitted = false;
    this.error = null;
    this.avatarFailed = false;
    this.serverMode = null;
    this.readback = null;
    this.addresses = null;
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

  // ---------------------------------------------------------------- render

  private get isLive(): boolean {
    return this.phase === "live" || this.phase === "reconnecting";
  }

  private get micIsOff(): boolean {
    return this.micOff || this.muted;
  }

  private statusText(): string {
    const L = this.language;
    if (this.phase === "connecting") return tr(L, "जुड़ रहे हैं…", "Connecting…");
    if (this.phase === "reconnecting") return tr(L, "फिर से जुड़ रहे हैं…", "Reconnecting…");
    if (this.working) return tr(L, "सोच रहे हैं…", "Thinking…");
    if (this.talking === "assistant") return tr(L, "दुकानदार बोल रहे हैं", "Shopkeeper is speaking");
    if (this.micIsOff) return tr(L, "माइक बंद है", "Mic is off");
    if (this.hearing || this.talking === "shopper") return tr(L, "सुन रहे हैं…", "Listening…");
    return tr(L, "बोलिए, मैं सुन रहा हूँ", "Go ahead, I am listening");
  }

  /** Quick things to say, as chips above the message box. */
  private hints(): string[] {
    const L = this.language;
    const empty = (this.cart?.item_count ?? 0) === 0;
    return empty
      ? [
          tr(L, "दूध और ब्रेड डाल दीजिए", "Add milk and bread"),
          tr(L, "आटा और प्याज़ डाल दीजिए", "Add atta and onions"),
          tr(L, "पनीर और दही डाल दीजिए", "Add paneer and curd"),
        ]
      : [
          tr(L, "मेरे कार्ट में क्या है?", "What is in my cart?"),
          tr(L, "अंडे भी डाल दीजिए", "Add eggs too"),
          tr(L, "बस, चेकआउट कर दीजिए", "That is all, check out"),
        ];
  }

  private renderMeta(live: boolean) {
    const L = this.language;
    return html`
      <div class="meta">
        <span class="ai-label" role="note" aria-label=${tr(L, "AI सहायक — यह एक AI है, इंसान नहीं", "AI assistant, not a human")}>
          <span aria-hidden="true">🤖</span> ${tr(L, "AI सहायक", "AI assistant")}
        </span>
        ${live
          ? html`<span class="badge" aria-label=${`${tr(L, "रफ़्तार", "Pace")}: ${this.pace === "guided" ? tr(L, "धीरे-धीरे", "Step by step") : tr(L, "जल्दी", "Quick")}`}>
              ${this.pace === "guided" ? tr(L, "धीरे-धीरे", "Step by step") : tr(L, "जल्दी", "Quick")}
            </span>`
          : nothing}
        ${live && this.remaining !== null
          ? html`<span class="badge" role="timer" aria-label=${`${tr(L, "बचा समय", "Time left")} ${fmtTime(this.remaining)}`}
              >⏱ ${fmtTime(this.remaining)}</span
            >`
          : nothing}
        ${live ? html`<button class="end" type="button" @click=${() => this.end()}>${tr(L, "बातचीत खत्म", "End chat")}</button>` : nothing}
      </div>
    `;
  }

  private renderOrb() {
    const L = this.language;
    const showVideo = this.effectiveMode === "avatar" && this.avatarPlaying;
    const zone = this.talking === "assistant" ? "live speak" : this.hearing || this.talking === "shopper" ? "live" : "";
    return html`
      <div class="orb ${zone}">
        <span class="ring"></span><span class="ring r2"></span><span class="ring r3"></span>
        <video class="avatar-video" ?hidden=${!showVideo} playsinline autoplay muted aria-label=${tr(L, "दुकानदार (AI अवतार)", "Shopkeeper (AI avatar)")}></video>
        <img src=${shopkeeperUrl} alt=${tr(L, "दुकानदार का चित्र", "Shopkeeper illustration")} ?hidden=${showVideo} />
        ${this.working
          ? html`<span class="working" role="status" aria-live="polite" lang=${L}
              >${L === "en" ? this.working.label_en || "Working…" : this.working.label_hi || "देख रहे हैं"}<span class="dots"></span></span
            >`
          : nothing}
      </div>
    `;
  }

  private renderIdle() {
    const L = this.language;
    const ended = this.phase === "ended";
    return html`
      <div class="start">
        ${this.renderMeta(false)} ${this.renderOrb()}
        <p class="headline" lang=${L} role="status">
          ${ended ? tr(L, "बातचीत ख़त्म हुई। धन्यवाद!", "Conversation ended. Thank you!") : tr(L, "नमस्ते! आज क्या मँगवाना है?", "Namaste! What would you like to order today?")}
        </p>
        <button class="primary start-btn" type="button" ?disabled=${this.phase === "connecting"} @click=${() => void this.start()}>
          <span lang=${L}>${this.phase === "connecting" ? tr(L, "जुड़ रहे हैं…", "Connecting…") : tr(L, "दुकानदार से बात करें", "Talk to the shopkeeper")}</span>
        </button>
        <p class="hint" lang=${L}>
          ${tr(L, "बटन दबाने पर माइक की अनुमति माँगी जाएगी। आप लिखकर भी बात कर सकते हैं।", "Tapping asks for microphone permission. You can also type.")}
        </p>
      </div>
    `;
  }

  private renderBanners() {
    const L = this.language;
    return html`
      ${this.phase === "reconnecting" ? html`<p class="banner" role="status">${tr(L, "फिर से जुड़ रहे हैं…", "Reconnecting…")}</p>` : nothing}
      ${this.micProblem && (this.phase === "live" || this.phase === "connecting")
        ? html`<p class="banner" role="status" lang=${L}>
            ${tr(L, "माइक नहीं मिला — नीचे लिखकर बात कीजिए।", "Microphone not available: please type below.")}
          </p>`
        : nothing}
      ${this.safetyHold
        ? html`<p class="banner" role="status" lang=${L}>
            ${tr(L, "आपकी सेहत पहले — अभी खरीदारी रुकी है।", "Your health first: shopping is paused.")}
          </p>`
        : nothing}
      ${this.error
        ? html`<p class="banner error" role="alert">
            <span lang=${L}>${L === "en" ? this.error.message_en || this.error.message_hi : this.error.message_hi}</span>
            ${L !== "en" && this.showTranslation ? html`<span class="en" lang="en"> ${this.error.message_en}</span>` : nothing}
            <button type="button" @click=${() => (this.error = null)}>${tr(L, "ठीक है", "OK")}</button>
          </p>`
        : nothing}
    `;
  }

  private renderDock(L: string) {
    const live = this.phase === "live";
    const count = (this.cart?.lines ?? []).reduce((n, l) => n + l.qty, 0);
    const micLabel = this.micIsOff ? tr(L, "माइक चालू करें", "Turn the microphone on") : tr(L, "माइक बंद करें", "Turn the microphone off");
    return html`
      <div class="dock">
        ${live
          ? html`<div class="chips" aria-label=${tr(L, "सुझाए गए वाक्य", "Things you can say")}>
              ${this.hints().map((h) => html`<button type="button" @click=${() => this.sendText(h)}>${h}</button>`)}
            </div>`
          : nothing}
        <ttb-text-input
          tone="dark"
          .language=${L}
          ?disabled=${!live}
          @ttb-text=${(e: CustomEvent<{ text: string }>) => this.sendText(e.detail.text)}
        ></ttb-text-input>
        <div class="controls">
          <button class="ctl" type="button" aria-pressed=${this.cameraOn ? "true" : "false"} ?disabled=${!live} @click=${() => void this.cameraEl?.toggle()}>
            <span class="disc"
              ><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
                ><path d="M4 8h3l1.5-2h7L17 8h3v11H4z"></path><circle cx="12" cy="13" r="3.5"></circle></svg
            ></span>
            ${tr(L, "दिखाइए", "Show item")}
          </button>
          <button class="mic" type="button" aria-pressed=${this.micIsOff ? "true" : "false"} aria-label=${micLabel} ?disabled=${this.muted} @click=${() => (this.micOff = !this.micOff)}>
            ${this.hearing && !this.micIsOff
              ? html`<span class="eq"><i></i><i></i><i></i><i></i><i></i></span>`
              : html`<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
                  ><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0M12 18v3"></path>${this.micIsOff ? html`<path d="M4 4l16 16"></path>` : nothing}</svg
                >`}
          </button>
          <button class="ctl" type="button" @click=${() => this.emit<Record<string, never>>("ttb:open-cart", {})}>
            <span class="disc"
              ><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
                ><path d="M3 4h2.2l2.3 11h10.3l2-8H6.3"></path><circle cx="9" cy="19" r="1.4"></circle><circle cx="17" cy="19" r="1.4"></circle></svg
              >${count > 0 ? html`<span class="count">${count}</span>` : nothing}</span
            >
            ${tr(L, "पूरा कार्ट", "Full cart")}
          </button>
        </div>
      </div>
    `;
  }

  render() {
    const L = this.language === "en" ? "en" : "hi";
    const live = this.isLive;
    if (!live) return html`<div class="root" lang=${L}>${this.renderIdle()}</div>`;
    const sheet = this.layout === "sheet";
    return html`
      <div class="root" lang=${L}>
        <div class="scroller">
          <div class="hero">
            ${this.renderOrb()}
            <div class="hero-text">
              <span class="status">${this.statusText()}</span>
              ${this.renderMeta(true)}
            </div>
          </div>
          ${this.renderBanners()}
          <ttb-captions class="lines" variant="talk" .showTranslation=${this.showTranslation && L === "hi"} .language=${L}></ttb-captions>
          <div class="panels">
            ${this.order || this.familyName
              ? html`<ttb-confirmation .order=${this.order} .familyName=${this.familyName} .language=${L}></ttb-confirmation>`
              : nothing}
            ${this.addresses && !this.order
              ? html`<ttb-address-picker
                  .addresses=${this.addresses}
                  .preferredId=${this.preferredAddress}
                  .language=${L}
                  ?disabled=${this.phase !== "live"}
                  @ttb-address-select=${(e: CustomEvent<{ id: string; label: string }>) => this.chooseAddress(e.detail)}
                  @ttb-address-new=${(e: CustomEvent<{ fields: NewAddressFields }>) => this.addNewAddress(e.detail.fields)}
                ></ttb-address-picker>`
              : nothing}
            ${this.readback && !this.order
              ? html`<ttb-readback
                  .readback=${this.readback}
                  .awaitingPayment=${!!this.pendingPayment}
                  .showTranslation=${this.showTranslation}
                  .language=${L}
                ></ttb-readback>`
              : nothing}
            ${this.goal ? html`<ttb-goal-list .goal=${this.goal} .language=${L}></ttb-goal-list>` : nothing}
            <ttb-cart-view ?hidden=${sheet} compact .pace=${this.pace} .cart=${this.cart} .language=${L}></ttb-cart-view>
          </div>
        </div>
        ${this.renderDock(L)}
        <ttb-camera
          variant="overlay"
          .language=${L}
          ?disabled=${this.phase !== "live"}
          @ttb-camera-active=${(e: CustomEvent<{ active: boolean }>) => {
            this.cameraOn = e.detail.active;
            this.client?.send({ type: "camera", active: e.detail.active });
          }}
          @ttb-camera-frame=${(e: CustomEvent<{ jpeg: ArrayBuffer }>) => this.client?.sendBinary(FRAME.CAMERA_JPEG, e.detail.jpeg)}
        ></ttb-camera>
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
    "ttb:phase": CustomEvent<PhaseDetail>;
    "ttb:open-cart": CustomEvent<Record<string, never>>;
    "ttb:payment-cancelled": CustomEvent<Record<string, never>>;
  }
}
