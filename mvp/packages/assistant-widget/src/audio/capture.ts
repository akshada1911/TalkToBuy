import { PCM_WORKLET_NAME, pcmWorkletSource } from "./pcm-worklet";

export type CaptureError = "denied" | "unavailable" | "unsupported";

/**
 * Microphone capture → 40 ms chunks of 16 kHz 16-bit LE mono PCM (sent by the caller as 0x01).
 * `start()` must be called from a user gesture (the start button) so the permission prompt and
 * AudioContext are allowed.
 */
export class MicCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private muted = false;

  constructor(private readonly onChunk: (pcm: ArrayBuffer) => void) {}

  get active(): boolean {
    return !!this.node;
  }

  async start(): Promise<void> {
    if (this.node) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === "undefined") {
      throw new CaptureStartError("unsupported");
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      const name = (err as DOMException)?.name;
      throw new CaptureStartError(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unavailable");
    }
    const ctx = new AudioContext();
    this.ctx = ctx;
    const url = URL.createObjectURL(new Blob([pcmWorkletSource()], { type: "application/javascript" }));
    try {
      await ctx.audioWorklet.addModule(url);
    } finally {
      URL.revokeObjectURL(url);
    }
    this.source = ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(ctx, PCM_WORKLET_NAME, {
      numberOfInputs: 1,
      numberOfOutputs: 0,
      channelCount: 1,
      channelCountMode: "explicit",
      processorOptions: { targetRate: 16000, chunkMs: 40 },
    });
    this.node.port.onmessage = (ev: MessageEvent<ArrayBuffer>) => {
      if (!this.muted) this.onChunk(ev.data);
    };
    this.source.connect(this.node);
    if (ctx.state === "suspended") await ctx.resume();
  }

  /** Temporarily stop sending (e.g. while the session reconnects) without releasing the mic. */
  setMuted(muted: boolean): void {
    this.muted = muted;
  }

  stop(): void {
    this.source?.disconnect();
    this.node?.port.close();
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close().catch(() => undefined);
    this.ctx = null;
    this.stream = null;
    this.node = null;
    this.source = null;
  }
}

export class CaptureStartError extends Error {
  constructor(readonly kind: CaptureError) {
    super(`mic capture failed: ${kind}`);
  }
}
