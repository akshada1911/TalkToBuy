/**
 * Binary frame helpers (widget-messages.schema.json, widget-protocol.md).
 * A binary frame is one prefix byte followed by the raw payload.
 */
export const FRAME = {
  /** Client → server: mic PCM, 16 kHz 16-bit LE mono. */
  MIC_PCM: 0x01,
  /** Client → server: camera JPEG ~768×768, ≤ 1 fps, only while the camera is active. */
  CAMERA_JPEG: 0x02,
  /** Server → client: assistant PCM, 24 kHz 16-bit LE mono. */
  ASSISTANT_PCM: 0x11,
  /** Server → client: avatar MP4 chunk. */
  AVATAR_MP4: 0x12,
} as const;

export type FrameType = (typeof FRAME)[keyof typeof FRAME];

const KNOWN = new Set<number>(Object.values(FRAME));

export interface DecodedFrame {
  type: FrameType;
  /** A view over the original buffer (no copy). */
  payload: Uint8Array;
}

/** Prefix `payload` with the frame type byte. Always returns a fresh, tightly sized ArrayBuffer. */
export function encodeFrame(type: FrameType, payload: ArrayBuffer | ArrayBufferView): ArrayBuffer {
  const body =
    payload instanceof ArrayBuffer
      ? new Uint8Array(payload)
      : new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength);
  const out = new Uint8Array(body.byteLength + 1);
  out[0] = type;
  out.set(body, 1);
  return out.buffer;
}

/** Split a received binary frame. Returns null for empty or unknown frames. */
export function decodeFrame(data: ArrayBuffer | Uint8Array): DecodedFrame | null {
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  if (bytes.byteLength < 1) return null;
  const type = bytes[0];
  if (!KNOWN.has(type)) return null;
  return {
    type: type as FrameType,
    payload: bytes.subarray(1),
  };
}
