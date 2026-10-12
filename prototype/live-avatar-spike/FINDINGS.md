# Live Avatar spike: findings (T009)

**Status**: Partially done. A headless probe (`probe.py`) ran on 2026-10-12 against project
`talktobuy`, region `us-central1`. Questions 3–5 still need the browser run of `spike.py` with a
person speaking Hindi into the microphone.

| # | Question | Result | Notes |
|---|---|---|---|
| 1 | Does `gemini-3.8-live` + preset avatar open on our project? | **Yes** | Avatar `Kai`, voice `Charon`. Connected in 3.8 s. Billing on; Vertex AI API enabled. |
| 2 | Is audio muxed into the MP4 chunks, or sent separately? | **Muxed** | Only `video/mp4` parts arrive (203 chunks, 4.8 MB for one short reply). The first chunk is a fragmented-MP4 init segment (`ftyp` + `moov`) with two tracks: H.264 baseline `avc1.42C01F` video and AAC `mp4a` audio. **The widget uses `avatar-audio="muxed"`**; the shop is set to it. MSE codec string: `video/mp4; codecs="avc1.42C01F, mp4a.40.2"`. |
| 3 | Do streamed chunks play smoothly via Media Source Extensions (`sequence` mode)? | Not yet | Run `spike.py` in Chrome. |
| 4 | Hindi quality with `language_code="hi-IN"` + voice | Text OK | Reply: "जी हाँ, आज ताज़ा टमाटर उपलब्ध हैं।" Natural and polite. The spoken voice still needs a native listener's judgement. |
| 5 | Does the session survive > 2 minutes with sliding-window compression? Any `goAway`? | Not yet | |
| 6 | Latency | First media 2.6 s after a **text** turn | That figure includes response generation. The spec target is < 1.5 s from end of **speech**; measure it with the mic in `spike.py`. Bandwidth is about 4.8 MB for about 8 s of avatar video (~4–5 Mbit/s), which is why the audio-only fallback matters on venue Wi-Fi. |
