import { describe, expect, it, vi } from "vitest";
import { SessionClient, parseServerMessage, routeServerMessage } from "../protocol/client";
import type { ServerMessage } from "../types/messages.generated";

describe("JSON message routing", () => {
  it("parses known types and rejects junk", () => {
    expect(parseServerMessage('{"type":"working","on":true}')).toEqual({ type: "working", on: true });
    expect(parseServerMessage("not json")).toBeNull();
    expect(parseServerMessage('{"type":"nope"}')).toBeNull();
    expect(parseServerMessage("[1,2]")).toBeNull();
  });

  it("dispatches on the type discriminator", () => {
    const caption = vi.fn();
    const cart = vi.fn();
    const handlers = { caption, cart };
    const msg: ServerMessage = { type: "caption", who: "assistant", turn_id: "t1", text_hi: "नमस्ते", final: true };
    expect(routeServerMessage(msg, handlers)).toBe(true);
    expect(caption).toHaveBeenCalledWith(msg);
    expect(cart).not.toHaveBeenCalled();
    expect(routeServerMessage({ type: "interrupted" }, handlers)).toBe(false);
  });

  it("SessionClient routes text frames to onMessage and binary frames to onBinary", () => {
    const onMessage = vi.fn();
    const onBinary = vi.fn();
    const c = new SessionClient({ getTicket: async () => "t", onMessage, onBinary });
    c.handleData('{"type":"cart","cart":{"lines":[],"item_count":0,"total":0}}');
    c.handleData(new Uint8Array([0x11, 1, 2]).buffer);
    c.handleData(new Uint8Array([0x55]).buffer);
    expect(onMessage).toHaveBeenCalledWith({ type: "cart", cart: { lines: [], item_count: 0, total: 0 } });
    expect(onBinary).toHaveBeenCalledTimes(1);
    expect(onBinary.mock.calls[0][0]).toBe(0x11);
    expect(Array.from(onBinary.mock.calls[0][1] as Uint8Array)).toEqual([1, 2]);
  });

  it("sends typed JSON and prefixed binary over an open socket, and reconnects after a drop", async () => {
    vi.useFakeTimers();
    const sockets: FakeWs[] = [];
    class FakeWs {
      static OPEN = 1;
      readyState = 0;
      bufferedAmount = 0;
      binaryType = "blob";
      sent: unknown[] = [];
      onopen: (() => void) | null = null;
      onclose: ((e: { code: number; reason: string }) => void) | null = null;
      onmessage: ((e: { data: unknown }) => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(public url: string) {
        sockets.push(this);
      }
      send(d: unknown) {
        this.sent.push(d);
      }
      close() {
        this.readyState = 3;
      }
    }
    const statuses: string[] = [];
    const c = new SessionClient({
      serverUrl: "http://localhost:8080",
      getTicket: async () => "tk",
      onStatus: (s) => statuses.push(s),
      WebSocketImpl: FakeWs as unknown as typeof WebSocket,
      baseDelayMs: 10,
    });
    await c.connect();
    expect(sockets[0].url).toBe("ws://localhost:8080/v1/session?ticket=tk");
    expect(c.send({ type: "text", text: "दूध" })).toBe(false); // not open yet
    sockets[0].readyState = 1;
    sockets[0].onopen!();
    expect(c.send({ type: "text", text: "दूध" })).toBe(true);
    expect(JSON.parse(sockets[0].sent[0] as string)).toEqual({ type: "text", text: "दूध" });
    c.sendBinary(0x01, new Uint8Array([4, 5]));
    expect(Array.from(new Uint8Array(sockets[0].sent[1] as ArrayBuffer))).toEqual([1, 4, 5]);

    sockets[0].readyState = 3;
    sockets[0].onclose!({ code: 1006, reason: "" });
    expect(statuses).toContain("reconnecting");
    await vi.advanceTimersByTimeAsync(50);
    expect(sockets.length).toBe(2);

    c.close();
    expect(statuses[statuses.length - 1]).toBe("closed");
    vi.useRealTimers();
  });
});
