"""Day 1 Live Avatar spike (T009). Adapted from Google's intro_live_avatar.ipynb.

Opens a gemini-3.8-live session with a preset Live Avatar, then relays microphone audio from
player.html to the model and the avatar's MP4 chunks back, so we can check:
  1. access works, 2. whether audio is muxed into the MP4, 3. MSE playback quality,
  4. Hindi quality, 5. survival past 2 minutes with compression, 6. latency.

Run (from mvp/, after setting GCP_PROJECT to the TalkToBuy project, never the gcloud default):
    uv run --package session-server python ../prototype/live-avatar-spike/spike.py
then open http://localhost:8765 in Chrome.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

PROJECT = os.environ.get("GCP_PROJECT", "")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
AVATAR = os.environ.get("AVATAR_NAME", "Kai")
VOICE = os.environ.get("VOICE_NAME", "Charon")
MODEL = "gemini-3.8-live"
FORBIDDEN_PROJECTS = {"zeroqueue-503710"}

if not PROJECT or PROJECT.startswith("REPLACE_") or PROJECT in FORBIDDEN_PROJECTS:
    raise SystemExit("Set GCP_PROJECT to the dedicated TalkToBuy project (not the gcloud default).")

client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
app = FastAPI()
HERE = Path(__file__).parent


def build_config(handle: str | None) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["VIDEO"],
        avatar_config=types.AvatarConfig(avatar_name=AVATAR),
        speech_config=types.SpeechConfig(
            language_code="hi-IN",
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
            ),
        ),
        system_instruction="आप एक विनम्र किराना दुकानदार हैं। हमेशा आदरपूर्वक हिंदी में बात कीजिए।",
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
        session_resumption=types.SessionResumptionConfig(handle=handle),
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(HERE / "player.html")


@app.websocket("/ws")
async def relay(ws: WebSocket) -> None:
    await ws.accept()
    started = time.monotonic()
    findings: dict = {"chunks": 0, "mime_types": set(), "first_chunk_s": None}
    async with client.aio.live.connect(model=MODEL, config=build_config(None)) as session:

        async def upstream() -> None:
            while True:
                pcm = await ws.receive_bytes()
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000")
                )

        async def downstream() -> None:
            # session.receive() ends after every completed turn, so keep re-entering it;
            # reading it only once was why the spike stopped responding after its first reply.
            turns = 0
            while True:
                async for msg in session.receive():
                    await handle(msg)
                turns += 1
                await ws.send_text(json.dumps({"type": "turn_complete", "turns": turns}))

        async def handle(msg) -> None:
            if True:
                sc = msg.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            findings["chunks"] += 1
                            findings["mime_types"].add(part.inline_data.mime_type)
                            if findings["first_chunk_s"] is None:
                                findings["first_chunk_s"] = round(time.monotonic() - started, 2)
                            await ws.send_text(json.dumps({
                                "type": "media",
                                "mime": part.inline_data.mime_type,
                                "b64": base64.b64encode(part.inline_data.data).decode(),
                            }))
                if sc and sc.output_transcription and sc.output_transcription.text:
                    await ws.send_text(json.dumps({"type": "caption", "text": sc.output_transcription.text}))
                if sc and sc.interrupted:
                    await ws.send_text(json.dumps({"type": "interrupted"}))
                if msg.go_away:
                    await ws.send_text(json.dumps({"type": "go_away", "time_left": str(msg.go_away.time_left)}))
                await ws.send_text(json.dumps({
                    "type": "stats",
                    "elapsed_s": round(time.monotonic() - started, 1),
                    "chunks": findings["chunks"],
                    "mime_types": sorted(findings["mime_types"]),
                    "first_chunk_s": findings["first_chunk_s"],
                }))

        await asyncio.gather(upstream(), downstream())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
