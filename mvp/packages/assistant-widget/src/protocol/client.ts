import type { ClientMessage, ServerMessage } from "../types/messages.generated";
import { decodeFrame, encodeFrame, FRAME, type FrameType } from "./framing";

export { FRAME, encodeFrame, decodeFrame } from "./framing";
export type { FrameType, DecodedFrame } from "./framing";

export type ServerType = ServerMessage["type"];
export type ServerMsgOf<K extends ServerType> = Extract<ServerMessage, { type: K }>;
export type ServerHandlers = { [K in ServerType]?: (msg: ServerMsgOf<K>) => void };

const SERVER_TYPES: ReadonlySet<string> = new Set<ServerType>([
  "caption",
  "interrupted",
  "cards",
  "goal_list",
  "cart",
  "addresses",
  "readback",
  "payment_request",
  "order",
  "family_notified",
  "state",
  "working",
  "error",
]);

/** Parse a JSON text frame into a ServerMessage. Returns null for malformed or unknown messages. */
export function parseServerMessage(raw: string): ServerMessage | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const type = (data as { type?: unknown }).type;
  if (typeof type !== "string" || !SERVER_TYPES.has(type)) return null;
  return data as ServerMessage;
}

/** Dispatch a parsed message to the handler for its `type`. Returns true if a handler ran. */
export function routeServerMessage(msg: ServerMessage, handlers: ServerHandlers): boolean {
  const handler = handlers[msg.type] as ((m: ServerMessage) => void) | undefined;
  if (!handler) return false;
  handler(msg);
  return true;
}

/** Build the session URL. An empty or missing server URL means "same origin". */
export function sessionUrl(
  serverUrl: string | null | undefined,
  ticket: string,
  loc: Location = location,
  mediaMode?: string | null,
  language?: string | null,
  cartId?: string | null,
): string {
  let base: URL;
  if (serverUrl && serverUrl.trim()) {
    base = new URL(serverUrl.trim(), loc.href);
  } else {
    base = new URL(loc.origin);
  }
  if (base.protocol === "http:") base.protocol = "ws:";
  else if (base.protocol === "https:") base.protocol = "wss:";
  const path = base.pathname.replace(/\/+$/, "");
  base.pathname = `${path}/v1/session`;
  base.search = "";
  base.searchParams.set("ticket", ticket);
  // The session starts in the switch's mode, so no avatar connection is paid for and then dropped.
  if (mediaMode) base.searchParams.set("media_mode", mediaMode);
  // Conversation language chosen by the shopper (hi = Hindi, en = English).
  if (language) base.searchParams.set("language", language);
  // A cart already filled in the shop is this conversation's cart too (one cart).
  if (cartId) base.searchParams.set("cart", cartId);
  return base.toString();
}

export type ClientStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export interface ClientOptions {
  serverUrl?: string | null;
  /** Called for every connect attempt, so a fresh ticket can be fetched after a drop. */
  getTicket: () => Promise<string>;
  /** Media mode to start the session in (cost control: "audio_only" unless the avatar is on). */
  getMediaMode?: () => string | null;
  /** Conversation language to start in: "hi" or "en". */
  getLanguage?: () => string | null;
  /** The store cart (checkout session) the shop already has, if any. */
  getCartId?: () => string | null;
  onMessage?: (msg: ServerMessage) => void;
  onBinary?: (type: FrameType, payload: Uint8Array) => void;
  onStatus?: (status: ClientStatus, detail?: { code?: number; reason?: string }) => void;
  /** Maximum reconnect attempts before giving up (default 6). */
  maxRetries?: number;
  /** Base backoff in ms (default 500), doubled each attempt and capped at 10 s. */
  baseDelayMs?: number;
  /** Injectable for tests. */
  WebSocketImpl?: typeof WebSocket;
}

/** Close codes after which we must not reconnect (normal closure, or the server ended the session). */
// Session server close codes that mean "don't reconnect" (session-server http/ws.py):
// 4401 bad/expired ticket, 4429 busy, 4503 assistant not configured.
const FINAL_CODES = new Set([1000, 4000, 4001, 4003, 4008, 4401, 4429, 4503]);

/**
 * One WebSocket per session. Text frames are JSON (typed ClientMessage / ServerMessage),
 * binary frames carry media with a one-byte prefix.
 */
export class SessionClient {
  private ws: WebSocket | null = null;
  private retries = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private openedAt = 0;
  /** Approximate RTT from the WebSocket handshake (TCP + TLS + upgrade ≈ 1–3 RTT), in ms. */
  handshakeMs: number | null = null;
  status: ClientStatus = "idle";

  constructor(private readonly opts: ClientOptions) {}

  async connect(): Promise<void> {
    this.stopped = false;
    this.setStatus(this.retries > 0 ? "reconnecting" : "connecting");
    let ticket: string;
    try {
      ticket = await this.opts.getTicket();
    } catch (err) {
      this.scheduleReconnect({ reason: String(err) });
      return;
    }
    if (this.stopped) return;
    const Impl = this.opts.WebSocketImpl ?? WebSocket;
    const ws = new Impl(sessionUrl(this.opts.serverUrl, ticket, location, this.opts.getMediaMode?.() ?? null, this.opts.getLanguage?.() ?? null, this.opts.getCartId?.() ?? null));
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    this.openedAt = performance.now();
    ws.onopen = () => {
      this.handshakeMs = Math.round(performance.now() - this.openedAt);
      this.retries = 0;
      this.setStatus("open");
    };
    ws.onmessage = (ev: MessageEvent) => this.handleData(ev.data);
    ws.onclose = (ev: CloseEvent) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (this.stopped || FINAL_CODES.has(ev.code)) {
        this.setStatus("closed", { code: ev.code, reason: ev.reason });
        return;
      }
      this.scheduleReconnect({ code: ev.code, reason: ev.reason });
    };
    ws.onerror = () => {
      /* onclose follows and handles reconnect */
    };
  }

  /** Visible for tests: route one incoming WebSocket payload. */
  handleData(data: unknown): void {
    if (typeof data === "string") {
      const msg = parseServerMessage(data);
      if (msg) this.opts.onMessage?.(msg);
      return;
    }
    if (data instanceof ArrayBuffer || data instanceof Uint8Array) {
      const frame = decodeFrame(data);
      if (frame) this.opts.onBinary?.(frame.type, frame.payload);
    }
  }

  get isOpen(): boolean {
    return !!this.ws && this.ws.readyState === 1;
  }

  send(msg: ClientMessage): boolean {
    if (!this.isOpen) return false;
    this.ws!.send(JSON.stringify(msg));
    return true;
  }

  sendBinary(type: typeof FRAME.MIC_PCM | typeof FRAME.CAMERA_JPEG, payload: ArrayBuffer | ArrayBufferView): boolean {
    if (!this.isOpen) return false;
    // Drop media rather than queue it when the socket is backed up (live audio must stay live).
    if (this.ws!.bufferedAmount > 512 * 1024) return false;
    this.ws!.send(encodeFrame(type, payload));
    return true;
  }

  /** Close for good (no reconnect). */
  close(code = 1000, reason = "client_closed"): void {
    this.stopped = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    const ws = this.ws;
    this.ws = null;
    if (ws && ws.readyState <= 1) ws.close(code, reason);
    this.setStatus("closed", { code, reason });
  }

  private scheduleReconnect(detail: { code?: number; reason?: string }): void {
    const max = this.opts.maxRetries ?? 6;
    if (this.stopped || this.retries >= max) {
      this.setStatus("closed", detail);
      return;
    }
    const base = this.opts.baseDelayMs ?? 500;
    const delay = Math.min(10_000, base * 2 ** this.retries) * (0.8 + Math.random() * 0.4);
    this.retries += 1;
    this.setStatus("reconnecting", detail);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.connect();
    }, delay);
  }

  private setStatus(status: ClientStatus, detail?: { code?: number; reason?: string }): void {
    this.status = status;
    this.opts.onStatus?.(status, detail);
  }
}
