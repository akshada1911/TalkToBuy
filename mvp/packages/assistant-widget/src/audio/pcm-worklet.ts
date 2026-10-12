/**
 * Microphone AudioWorklet: downsample the context rate (usually 44.1/48 kHz) to 16 kHz,
 * convert to 16-bit LE mono and post one 40 ms chunk (640 samples, 1280 bytes) at a time.
 *
 * The worklet runs in its own global scope, so its source is shipped as a string and loaded
 * through a Blob URL. `PcmChunker` is self-contained (no outside references) so it can be both
 * unit-tested here and serialised into the worklet with `toString()`.
 */
export class PcmChunker {
  private readonly ratio: number;
  private readonly chunk: Int16Array;
  private filled = 0;
  /** Fractional read position into the incoming stream, relative to the current block. */
  private pos = 0;
  // Box-filter accumulator: averages the input samples that fall into one output sample.
  private acc = 0;
  private accN = 0;

  constructor(inputRate: number, outputRate = 16000, chunkMs = 40) {
    this.ratio = inputRate / outputRate;
    this.chunk = new Int16Array(Math.round((outputRate * chunkMs) / 1000));
  }

  /** Feed float samples in [-1, 1]. Returns zero or more complete chunks (each a fresh ArrayBuffer). */
  push(input: Float32Array): ArrayBuffer[] {
    const out: ArrayBuffer[] = [];
    if (this.ratio <= 1) {
      // Input already at (or below) 16 kHz: pass through.
      for (let i = 0; i < input.length; i++) this.emit(input[i], out);
      return out;
    }
    for (let i = 0; i < input.length; i++) {
      this.acc += input[i];
      this.accN += 1;
      if (i + 1 >= this.pos + this.ratio) {
        this.emit(this.acc / this.accN, out);
        this.acc = 0;
        this.accN = 0;
        this.pos += this.ratio;
      }
    }
    this.pos -= input.length;
    return out;
  }

  private emit(sample: number, out: ArrayBuffer[]): void {
    const s = sample < -1 ? -1 : sample > 1 ? 1 : sample;
    this.chunk[this.filled++] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
    if (this.filled === this.chunk.length) {
      // Int16Array is platform-endian; every browser platform we target is little-endian,
      // but write explicitly through a DataView to guarantee LE on the wire.
      const buf = new ArrayBuffer(this.chunk.length * 2);
      const view = new DataView(buf);
      for (let j = 0; j < this.chunk.length; j++) view.setInt16(j * 2, this.chunk[j], true);
      out.push(buf);
      this.filled = 0;
    }
  }
}

export const PCM_WORKLET_NAME = "ttb-pcm-capture";

/** Source of the AudioWorkletProcessor module. */
export function pcmWorkletSource(): string {
  return `
const PcmChunker = ${PcmChunker.toString()};
class TtbPcmCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const o = (options && options.processorOptions) || {};
    this.chunker = new PcmChunker(sampleRate, o.targetRate || 16000, o.chunkMs || 40);
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) {
      const chunks = this.chunker.push(ch);
      for (const c of chunks) this.port.postMessage(c, [c]);
    }
    return true;
  }
}
registerProcessor(${JSON.stringify(PCM_WORKLET_NAME)}, TtbPcmCapture);
`;
}
