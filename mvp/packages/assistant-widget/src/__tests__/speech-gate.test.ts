import { describe, expect, it } from "vitest";
import { rms16, SpeechGate } from "../audio/speech-gate";

/** A 40 ms chunk (640 samples) of a constant-amplitude square wave. */
function chunk(amplitude: number): ArrayBuffer {
  const buf = new ArrayBuffer(640 * 2);
  const v = new DataView(buf);
  for (let i = 0; i < 640; i++) v.setInt16(i * 2, Math.round((i % 2 ? 1 : -1) * amplitude * 0x7fff), true);
  return buf;
}
const silence = () => chunk(0.002);
const speech = () => chunk(0.2);

describe("SpeechGate (browser voice detection)", () => {
  it("measures RMS of 16-bit PCM", () => {
    expect(rms16(chunk(0.5))).toBeCloseTo(0.5, 2);
    expect(rms16(new ArrayBuffer(0))).toBe(0);
  });

  it("sends nothing while it is quiet", () => {
    const g = new SpeechGate();
    let sent = 0;
    for (let i = 0; i < 100; i++) sent += g.push(silence()).send.length;
    expect(sent).toBe(0);
    expect(g.isOpen).toBe(false);
  });

  it("opens on speech and includes the lead-in so the first syllable is kept", () => {
    const g = new SpeechGate({ prerollChunks: 8, openChunks: 2 });
    for (let i = 0; i < 20; i++) g.push(silence());
    expect(g.push(speech()).send).toHaveLength(0);
    const opened = g.push(speech());
    expect(g.isOpen).toBe(true);
    expect(opened.send).toHaveLength(8); // 6 quiet lead-in chunks + the 2 loud ones
  });

  it("keeps a short pause inside one turn, then reports a single pause", () => {
    const g = new SpeechGate({ hangoverChunks: 20 });
    for (let i = 0; i < 10; i++) g.push(silence());
    for (let i = 0; i < 10; i++) g.push(speech());
    let pauses = 0;
    for (let i = 0; i < 10; i++) pauses += g.push(silence()).paused ? 1 : 0; // 400 ms mid-sentence pause
    expect(g.isOpen).toBe(true);
    for (let i = 0; i < 5; i++) g.push(speech());
    for (let i = 0; i < 40; i++) pauses += g.push(silence()).paused ? 1 : 0;
    expect(pauses).toBe(1);
    expect(g.isOpen).toBe(false);
  });

  it("adapts to a noisy room instead of streaming the noise", () => {
    const g = new SpeechGate();
    let sent = 0;
    for (let i = 0; i < 200; i++) sent += g.push(chunk(0.015)).send.length; // steady fan noise
    expect(sent).toBe(0);
  });
});
