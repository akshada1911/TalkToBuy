/**
 * MSE codec selection for the avatar MP4 stream.
 *
 * The server relays the model's MP4 chunks unchanged and the contract carries no MIME string, so
 * the widget sniffs the codec from the first (initialisation) chunk: it looks for the sample-entry
 * configuration boxes (`avcC`, `hvcC`, `av1C`, `vpcC`) and audio sample entries (`mp4a`, `Opus`)
 * and builds an RFC 6381 codecs string. If sniffing finds nothing, it falls back to a list of common
 * H.264 strings and picks the first one `MediaSource.isTypeSupported` accepts.
 */
export interface SniffResult {
  video?: string;
  audio?: string;
}

function findAscii(bytes: Uint8Array, tag: string, from = 0): number {
  const c0 = tag.charCodeAt(0),
    c1 = tag.charCodeAt(1),
    c2 = tag.charCodeAt(2),
    c3 = tag.charCodeAt(3);
  for (let i = from; i + 3 < bytes.length; i++) {
    if (bytes[i] === c0 && bytes[i + 1] === c1 && bytes[i + 2] === c2 && bytes[i + 3] === c3) return i;
  }
  return -1;
}

const hex2 = (n: number) => n.toString(16).padStart(2, "0").toUpperCase();

export function sniffCodecs(init: Uint8Array): SniffResult {
  const res: SniffResult = {};
  // H.264: avcC payload = configurationVersion, AVCProfileIndication, profile_compatibility, AVCLevelIndication
  const avcc = findAscii(init, "avcC");
  if (avcc >= 0 && avcc + 8 <= init.length) {
    const p = init[avcc + 5],
      c = init[avcc + 6],
      l = init[avcc + 7];
    res.video = `avc1.${hex2(p)}${hex2(c)}${hex2(l)}`;
  } else if (findAscii(init, "hvcC") >= 0) {
    res.video = findAscii(init, "hev1") >= 0 ? "hev1.1.6.L93.B0" : "hvc1.1.6.L93.B0";
  } else if (findAscii(init, "av1C") >= 0) {
    res.video = "av01.0.04M.08";
  } else if (findAscii(init, "vpcC") >= 0) {
    res.video = "vp09.00.10.08";
  }
  if (findAscii(init, "mp4a") >= 0) res.audio = "mp4a.40.2";
  else if (findAscii(init, "Opus") >= 0) res.audio = "opus";
  return res;
}

export const FALLBACK_TYPES = [
  'video/mp4; codecs="avc1.42E01E, mp4a.40.2"',
  'video/mp4; codecs="avc1.42E01E"',
  'video/mp4; codecs="avc1.4D401F"',
  'video/mp4; codecs="avc1.64001F"',
];

/** Pick the MSE type for this stream. `isSupported` is injectable for tests. */
export function chooseMseType(
  init: Uint8Array,
  isSupported: (t: string) => boolean = (t) => typeof MediaSource !== "undefined" && MediaSource.isTypeSupported(t),
): string | null {
  const s = sniffCodecs(init);
  const candidates: string[] = [];
  if (s.video) {
    candidates.push(`video/mp4; codecs="${[s.video, s.audio].filter(Boolean).join(", ")}"`);
    candidates.push(`video/mp4; codecs="${s.video}"`);
  }
  candidates.push(...FALLBACK_TYPES);
  return candidates.find((t) => isSupported(t)) ?? null;
}
