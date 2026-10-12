/**
 * Browser voice detection for the mic (cost control): only chunks that contain speech, plus a
 * short lead-in and tail, are sent to the server. Silence is never streamed, so the Live model
 * is not billed for an older shopper's long pauses.
 *
 * Energy-based with an adaptive noise floor. Works on the 40 ms 16-bit PCM chunks from the
 * capture worklet:
 * - opens after `openChunks` consecutive loud chunks (> max(minOpenRms, floor × openRatio));
 * - sends the `prerollChunks` buffered just before opening, so the first syllable isn't lost;
 * - stays open for `hangoverChunks` after the level drops, so short pauses don't cut a sentence;
 * - reports one "pause" when it closes, so the caller can tell the server the turn ended.
 */
export interface SpeechGateOptions {
  openRatio: number;
  closeRatio: number;
  minOpenRms: number;
  minCloseRms: number;
  openChunks: number;
  prerollChunks: number;
  hangoverChunks: number;
  floorAlpha: number;
}

export const DEFAULT_GATE: SpeechGateOptions = {
  openRatio: 3.0,
  closeRatio: 2.0,
  minOpenRms: 0.02, // ≈ −34 dBFS after browser AGC
  minCloseRms: 0.012,
  openChunks: 2, // 80 ms
  prerollChunks: 8, // 320 ms
  hangoverChunks: 20, // 800 ms
  floorAlpha: 0.05,
};

export interface GateResult {
  /** Chunks to send now, in order (pre-roll first when the gate opens). */
  send: ArrayBuffer[];
  /** True exactly once, when the gate closes after speech. */
  paused: boolean;
}

/** RMS of a 16-bit LE PCM chunk, normalised to [0, 1]. */
export function rms16(chunk: ArrayBuffer): number {
  const view = new DataView(chunk);
  const n = chunk.byteLength >> 1;
  if (!n) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const s = view.getInt16(i * 2, true) / 0x8000;
    sum += s * s;
  }
  return Math.sqrt(sum / n);
}

export class SpeechGate {
  private readonly o: SpeechGateOptions;
  private floor = 0.005;
  private open = false;
  private loudRun = 0;
  private quietRun = 0;
  private preroll: ArrayBuffer[] = [];

  constructor(options: Partial<SpeechGateOptions> = {}) {
    this.o = { ...DEFAULT_GATE, ...options };
  }

  get isOpen(): boolean {
    return this.open;
  }

  push(chunk: ArrayBuffer): GateResult {
    const level = rms16(chunk);
    const o = this.o;
    if (!this.open) {
      const loud = level > Math.max(o.minOpenRms, this.floor * o.openRatio);
      if (loud) {
        this.loudRun += 1;
      } else {
        this.loudRun = 0;
        this.floor = this.floor * (1 - o.floorAlpha) + level * o.floorAlpha;
      }
      this.preroll.push(chunk);
      if (this.preroll.length > o.prerollChunks) this.preroll.shift();
      if (this.loudRun >= o.openChunks) {
        this.open = true;
        this.quietRun = 0;
        const send = this.preroll;
        this.preroll = [];
        return { send, paused: false };
      }
      return { send: [], paused: false };
    }
    const quiet = level < Math.max(o.minCloseRms, this.floor * o.closeRatio);
    this.quietRun = quiet ? this.quietRun + 1 : 0;
    if (this.quietRun >= o.hangoverChunks) {
      this.open = false;
      this.loudRun = 0;
      this.quietRun = 0;
      return { send: [chunk], paused: true };
    }
    return { send: [chunk], paused: false };
  }

  reset(): void {
    this.open = false;
    this.loudRun = 0;
    this.quietRun = 0;
    this.preroll = [];
  }
}
