/**
 * Gapless playback of assistant PCM (24 kHz 16-bit LE mono, frame 0x11).
 * Each chunk becomes an AudioBuffer scheduled exactly where the previous one ends. `flush()`
 * stops everything immediately (well inside the 300 ms budget of FR-004) and resets the schedule.
 */
export const ASSISTANT_RATE = 24000;
/** Lead time added when (re)starting a schedule, to absorb jitter. */
const START_LEAD_S = 0.06;
/** A gap shorter than this between chunks counts as a buffer underrun (mid-turn starvation). */
const UNDERRUN_WINDOW_S = 1.0;

/** The subset of AudioContext we use; lets tests inject a fake. */
export interface PlaybackContext {
  readonly currentTime: number;
  readonly state: string;
  readonly destination: AudioNode;
  createBuffer(channels: number, length: number, sampleRate: number): AudioBuffer;
  createBufferSource(): AudioBufferSourceNode;
  createGain?(): GainNode;
  resume(): Promise<void>;
  close?(): Promise<void>;
}

export function pcm16ToFloat32(bytes: Uint8Array): Float32Array {
  const n = bytes.byteLength >> 1;
  const view = new DataView(bytes.buffer, bytes.byteOffset, n * 2);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

export class AudioPlayback {
  private ctx: PlaybackContext | null = null;
  private output: AudioNode | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  /** Context time at which the next chunk should start; 0 = nothing scheduled. */
  nextTime = 0;
  /** Cumulative count of mid-turn underruns. */
  underruns = 0;
  private volume = 1;

  constructor(private readonly makeContext: () => PlaybackContext = () => new AudioContext()) {}

  /** Create/resume the context. Call from a user gesture to satisfy autoplay rules. */
  async resume(): Promise<void> {
    const ctx = this.ensure();
    if (ctx.state === "suspended") await ctx.resume();
  }

  get scheduledCount(): number {
    return this.sources.size;
  }

  /** True while audio is scheduled to play. */
  get playing(): boolean {
    return !!this.ctx && this.nextTime > this.ctx.currentTime;
  }

  setVolume(v: number): void {
    this.volume = v;
    const gain = this.output as GainNode | null;
    if (gain && "gain" in gain) gain.gain.value = v;
  }

  enqueue(pcm: Uint8Array): void {
    const samples = pcm16ToFloat32(pcm);
    if (!samples.length) return;
    const ctx = this.ensure();
    const buffer = ctx.createBuffer(1, samples.length, ASSISTANT_RATE);
    buffer.getChannelData(0).set(samples);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.output ?? ctx.destination);

    const now = ctx.currentTime;
    if (this.nextTime < now) {
      if (this.nextTime > 0 && now - this.nextTime < UNDERRUN_WINDOW_S) this.underruns += 1;
      this.nextTime = now + START_LEAD_S;
    }
    src.start(this.nextTime);
    this.nextTime += buffer.duration;
    this.sources.add(src);
    src.onended = () => {
      this.sources.delete(src);
    };
  }

  /** Stop all queued and playing audio now and reset the schedule (on `interrupted`). */
  flush(): void {
    for (const src of this.sources) {
      src.onended = null;
      try {
        src.stop();
      } catch {
        /* not started yet / already stopped */
      }
      try {
        src.disconnect();
      } catch {
        /* ignore */
      }
    }
    this.sources.clear();
    this.nextTime = 0;
  }

  close(): void {
    this.flush();
    void this.ctx?.close?.().catch(() => undefined);
    this.ctx = null;
    this.output = null;
  }

  private ensure(): PlaybackContext {
    if (!this.ctx) {
      this.ctx = this.makeContext();
      if (this.ctx.createGain) {
        const g = this.ctx.createGain();
        g.gain.value = this.volume;
        g.connect(this.ctx.destination);
        this.output = g;
      }
    }
    return this.ctx;
  }
}
