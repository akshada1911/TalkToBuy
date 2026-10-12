import { chooseMseType } from "./codec";

export type AvatarAudio = "muxed" | "separate";

export interface AvatarPlayerOptions {
  /**
   * `separate` (default): the MP4 is played muted and assistant speech comes from 0x11 PCM.
   * `muxed`: the MP4 carries the audio track, so the video element is unmuted.
   */
  audio?: AvatarAudio;
  /** Called when MSE cannot play the stream; the widget then shows the illustrated shopkeeper. */
  onFailure?: (reason: string) => void;
  /** Called once the first frame is decodable (the video can replace the illustration). */
  onPlaying?: () => void;
}

/** Keep at most this much video buffered behind the playhead. */
const KEEP_BEHIND_S = 10;
/** If the playhead falls further than this behind the live edge, jump forward. */
const MAX_LAG_S = 1.5;

/**
 * Plays avatar MP4 chunks (frame 0x12) through Media Source Extensions in `sequence` mode, so
 * chunk timestamps need not be continuous across turns. Chunks are queued and appended one at a
 * time; `flush()` drops everything queued and buffered (on `interrupted`).
 */
export class AvatarPlayer {
  private ms: MediaSource | null = null;
  private sb: SourceBuffer | null = null;
  private queue: Uint8Array<ArrayBuffer>[] = [];
  private init: Uint8Array | null = null;
  private failed = false;
  private started = false;
  private objectUrl: string | null = null;
  private audio: AvatarAudio;
  mimeType: string | null = null;

  constructor(
    readonly video: HTMLVideoElement,
    private readonly opts: AvatarPlayerOptions = {},
  ) {
    this.audio = opts.audio ?? "separate";
    video.playsInline = true;
    video.autoplay = true;
    video.muted = this.audio === "separate";
  }

  static get supported(): boolean {
    return typeof MediaSource !== "undefined";
  }

  setAudioMode(mode: AvatarAudio): void {
    this.audio = mode;
    this.video.muted = mode === "separate";
  }

  get audioMode(): AvatarAudio {
    return this.audio;
  }

  get hasFailed(): boolean {
    return this.failed;
  }

  append(chunk: Uint8Array): void {
    if (this.failed) return;
    // Copy: the payload is a view into the WebSocket buffer.
    const data = new Uint8Array(chunk); // copy into a fresh ArrayBuffer
    if (!this.ms) {
      if (!AvatarPlayer.supported) return this.fail("MediaSource unsupported");
      const type = chooseMseType(data);
      if (!type) return this.fail("no supported MP4 codec");
      this.mimeType = type;
      this.init = data;
      this.open(type);
    }
    this.queue.push(data);
    // Bound memory if the decoder stalls.
    if (this.queue.length > 120) this.queue.splice(0, this.queue.length - 120);
    this.pump();
  }

  /** Drop queued and buffered video (interrupted turn). */
  flush(): void {
    this.queue = [];
    const sb = this.sb;
    if (!sb || !this.ms || this.ms.readyState !== "open") return;
    try {
      if (sb.updating) sb.abort();
      const b = sb.buffered;
      if (b.length) sb.remove(b.start(0), b.end(b.length - 1));
    } catch {
      /* ignore: next append resumes */
    }
  }

  destroy(): void {
    this.queue = [];
    try {
      if (this.ms?.readyState === "open") this.ms.endOfStream();
    } catch {
      /* ignore */
    }
    this.video.removeAttribute("src");
    this.video.load();
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.ms = null;
    this.sb = null;
    this.objectUrl = null;
    this.init = null;
    this.started = false;
  }

  private open(type: string): void {
    const ms = new MediaSource();
    this.ms = ms;
    this.objectUrl = URL.createObjectURL(ms);
    this.video.src = this.objectUrl;
    ms.addEventListener(
      "sourceopen",
      () => {
        try {
          const sb = ms.addSourceBuffer(type);
          sb.mode = "sequence";
          sb.addEventListener("updateend", () => this.onUpdateEnd());
          sb.addEventListener("error", () => this.fail("SourceBuffer error"));
          this.sb = sb;
          this.pump();
        } catch (err) {
          this.fail(`addSourceBuffer failed: ${String(err)}`);
        }
      },
      { once: true },
    );
    this.video.addEventListener("error", () => this.fail("video element error"), { once: true });
  }

  private pump(): void {
    const sb = this.sb;
    if (!sb || sb.updating || !this.queue.length || this.ms?.readyState !== "open") return;
    const next = this.queue.shift()!;
    try {
      sb.appendBuffer(next);
    } catch (err) {
      if ((err as DOMException)?.name === "QuotaExceededError") {
        this.queue.unshift(next);
        this.trimBehind(0);
      } else {
        this.fail(`appendBuffer failed: ${String(err)}`);
      }
    }
  }

  private onUpdateEnd(): void {
    const v = this.video;
    const b = this.sb?.buffered;
    if (b && b.length) {
      const start = b.start(0);
      const end = b.end(b.length - 1);
      // After a flush (or a gap) the playhead can sit outside the buffered range: move it in.
      if (v.currentTime < start || v.currentTime > end) v.currentTime = start;
      else if (end - v.currentTime > MAX_LAG_S) v.currentTime = Math.max(start, end - 0.3);
      if (v.paused) void v.play().catch(() => undefined);
      if (!this.started) {
        this.started = true;
        this.opts.onPlaying?.();
      }
      if (v.currentTime - start > KEEP_BEHIND_S * 2) {
        this.trimBehind(KEEP_BEHIND_S);
        return;
      }
    }
    this.pump();
  }

  private trimBehind(keep: number): void {
    const sb = this.sb;
    if (!sb || sb.updating || !sb.buffered.length) return;
    const start = sb.buffered.start(0);
    const until = this.video.currentTime - keep;
    if (until > start) {
      try {
        sb.remove(start, until);
      } catch {
        /* ignore */
      }
    }
  }

  private fail(reason: string): void {
    if (this.failed) return;
    this.failed = true;
    this.queue = [];
    this.opts.onFailure?.(reason);
  }

  /** For diagnostics: the cached initialisation chunk. */
  get initSegment(): Uint8Array | null {
    return this.init;
  }
}
