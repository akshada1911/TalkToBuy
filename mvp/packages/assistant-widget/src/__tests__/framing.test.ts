import { describe, expect, it } from "vitest";
import { FRAME, decodeFrame, encodeFrame } from "../protocol/framing";
import { sessionUrl } from "../protocol/client";
import { PcmChunker } from "../audio/pcm-worklet";

describe("binary framing", () => {
  it("prefixes the type byte and round-trips", () => {
    const pcm = new Int16Array([1, -2, 32767, -32768]);
    const buf = encodeFrame(FRAME.MIC_PCM, pcm);
    const bytes = new Uint8Array(buf);
    expect(bytes[0]).toBe(0x01);
    expect(bytes.byteLength).toBe(1 + pcm.byteLength);
    const f = decodeFrame(buf)!;
    expect(f.type).toBe(FRAME.MIC_PCM);
    expect(Array.from(new Int16Array(f.payload.slice().buffer))).toEqual([1, -2, 32767, -32768]);
  });

  it("encodes a sub-view without leaking the rest of its buffer", () => {
    const big = new Uint8Array([9, 9, 1, 2, 3, 9]);
    const buf = encodeFrame(FRAME.CAMERA_JPEG, big.subarray(2, 5));
    expect(Array.from(new Uint8Array(buf))).toEqual([0x02, 1, 2, 3]);
  });

  it("decodes server frames 0x11 and 0x12", () => {
    expect(decodeFrame(new Uint8Array([0x11, 7, 8]))).toMatchObject({ type: 0x11 });
    expect(Array.from(decodeFrame(new Uint8Array([0x12, 5]))!.payload)).toEqual([5]);
  });

  it("rejects empty and unknown frames", () => {
    expect(decodeFrame(new Uint8Array([]))).toBeNull();
    expect(decodeFrame(new Uint8Array([0x7f, 1]))).toBeNull();
  });
});

describe("sessionUrl", () => {
  const loc = { href: "https://shop.example/app", origin: "https://shop.example" } as Location;
  it("defaults to same origin over wss", () => {
    expect(sessionUrl("", "t 1", loc)).toBe("wss://shop.example/v1/session?ticket=t+1");
  });
  it("uses server-url", () => {
    expect(sessionUrl("http://localhost:8080/", "abc", loc)).toBe("ws://localhost:8080/v1/session?ticket=abc");
  });
});

describe("PcmChunker (worklet downsampler)", () => {
  it("turns 48 kHz into 40 ms chunks of 640 16-bit LE samples", () => {
    const c = new PcmChunker(48000, 16000, 40);
    const chunks = [...c.push(new Float32Array(1920).fill(0.5)), ...c.push(new Float32Array(1920).fill(0.5))];
    expect(chunks.length).toBe(2);
    expect(chunks[0].byteLength).toBe(1280);
    const v = new DataView(chunks[0]);
    expect(v.getInt16(0, true)).toBe(Math.round(0.5 * 0x7fff));
  });

  it("serialises into the worklet source", async () => {
    const { pcmWorkletSource } = await import("../audio/pcm-worklet");
    const src = pcmWorkletSource();
    expect(src).toContain("registerProcessor");
    // The embedded class must be evaluable on its own.
    const Ctor = new Function(`${src.split("class TtbPcmCapture")[0]}; return PcmChunker;`)();
    expect(new Ctor(32000, 16000, 40).push(new Float32Array(1280)).length).toBe(1);
  });
});
