import { describe, expect, it } from "vitest";
import { AudioPlayback, ASSISTANT_RATE, type PlaybackContext } from "../audio/playback";

class FakeSource {
  buffer: { duration: number } | null = null;
  startedAt: number | null = null;
  stopped = false;
  onended: (() => void) | null = null;
  connect() {}
  disconnect() {}
  start(t: number) {
    this.startedAt = t;
  }
  stop() {
    this.stopped = true;
  }
}

function fakeContext() {
  const sources: FakeSource[] = [];
  const ctx = {
    currentTime: 0,
    state: "running",
    destination: {} as AudioNode,
    createBuffer: (_c: number, length: number, rate: number) => {
      const data = new Float32Array(length);
      return { duration: length / rate, getChannelData: () => data } as unknown as AudioBuffer;
    },
    createBufferSource: () => {
      const s = new FakeSource();
      sources.push(s);
      return s as unknown as AudioBufferSourceNode;
    },
    resume: async () => undefined,
  };
  return { ctx: ctx as PlaybackContext & { currentTime: number }, sources };
}

/** 100 ms of 24 kHz 16-bit PCM. */
const chunk = () => new Uint8Array((ASSISTANT_RATE / 10) * 2);

describe("AudioPlayback", () => {
  it("schedules chunks back to back (gapless)", () => {
    const { ctx, sources } = fakeContext();
    const p = new AudioPlayback(() => ctx);
    p.enqueue(chunk());
    p.enqueue(chunk());
    p.enqueue(chunk());
    expect(sources.length).toBe(3);
    const t0 = sources[0].startedAt!;
    expect(sources[1].startedAt).toBeCloseTo(t0 + 0.1, 6);
    expect(sources[2].startedAt).toBeCloseTo(t0 + 0.2, 6);
    expect(p.scheduledCount).toBe(3);
  });

  it("flush() stops every source and resets the schedule", () => {
    const { ctx, sources } = fakeContext();
    const p = new AudioPlayback(() => ctx);
    p.enqueue(chunk());
    p.enqueue(chunk());
    expect(p.nextTime).toBeGreaterThan(0);
    p.flush();
    expect(sources.every((s) => s.stopped)).toBe(true);
    expect(p.nextTime).toBe(0);
    expect(p.scheduledCount).toBe(0);
    // A new turn starts fresh at "now + lead", not after the flushed audio.
    ctx.currentTime = 0.05;
    p.enqueue(chunk());
    expect(sources[2].startedAt!).toBeLessThan(0.05 + 0.1);
  });

  it("counts a mid-turn underrun", () => {
    const { ctx } = fakeContext();
    const p = new AudioPlayback(() => ctx);
    p.enqueue(chunk()); // ends at ~0.16
    ctx.currentTime = 0.4; // next chunk arrives late
    p.enqueue(chunk());
    expect(p.underruns).toBe(1);
  });
});
