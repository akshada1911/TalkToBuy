"""Headless T009 probe: can we open a gemini-3.8-live + Live Avatar session, and what arrives?

Sends one Hindi text turn, records media MIME types / sizes / first-chunk latency, saves the first
avatar chunk to probe_first_chunk.bin for codec inspection, then closes. Uses only the explicit
TalkToBuy project from mvp/.env (never the gcloud default).

    cd mvp && uv run --package session-server python ../prototype/live-avatar-spike/probe.py
"""

import asyncio
import json
import time
from pathlib import Path

from google import genai
from google.genai import types

from session_server.config import get_settings

HERE = Path(__file__).parent


async def main() -> None:
    s = get_settings()
    project = s.require_gcp()
    client = genai.Client(vertexai=True, project=project, location=s.gcp_location)
    config = types.LiveConnectConfig(
        response_modalities=["VIDEO"],
        avatar_config=types.AvatarConfig(avatar_name=s.avatar_name),
        speech_config=types.SpeechConfig(
            language_code="hi-IN",
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=s.voice_name)),
        ),
        system_instruction="आप एक विनम्र किराना दुकानदार हैं। एक छोटे वाक्य में हिंदी में जवाब दीजिए।",
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    report: dict = {"project": project, "location": s.gcp_location, "model": s.live_model,
                    "avatar": s.avatar_name, "mimes": {}, "first_media_s": None, "transcript": ""}
    t0 = time.monotonic()
    try:
        async with client.aio.live.connect(model=s.live_model, config=config) as session:
            report["connected_s"] = round(time.monotonic() - t0, 2)
            t1 = time.monotonic()
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="नमस्ते, आज टमाटर हैं?")]),
                turn_complete=True,
            )
            async for msg in session.receive():
                sc = msg.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts or []:
                        blob = part.inline_data
                        if blob and blob.data:
                            m = report["mimes"].setdefault(blob.mime_type, {"chunks": 0, "bytes": 0})
                            m["chunks"] += 1
                            m["bytes"] += len(blob.data)
                            if report["first_media_s"] is None:
                                report["first_media_s"] = round(time.monotonic() - t1, 2)
                                (HERE / "probe_first_chunk.bin").write_bytes(blob.data)
                if sc and sc.output_transcription and sc.output_transcription.text:
                    report["transcript"] += sc.output_transcription.text
                if sc and sc.turn_complete:
                    break
                if time.monotonic() - t1 > 30:
                    report["note"] = "stopped after 30 s"
                    break
        report["ok"] = True
    except Exception as exc:  # report the access error verbatim
        report["ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"[:800]
    report["total_s"] = round(time.monotonic() - t0, 2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
