"""LivePort for gemini-3.8-live + Live Avatar on Gemini Enterprise Agent Platform (T029, R1).

Vertex mode only (Live Avatar is not on the Gemini API). Uses sliding-window compression and
session resumption; reconnects transparently on goAway or a media-mode switch.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any, Literal

from google import genai
from google.genai import types

from session_server.adapters.gemini_live.tools import to_function_declarations
from session_server.config import Settings
from session_server.logging import get_logger
from session_server.ports import live as L

log = get_logger(__name__)


class GeminiLive:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = genai.Client(
            vertexai=True, project=settings.require_gcp(), location=settings.gcp_location
        )
        self._config: L.LiveConfig | None = None
        self._cm: Any = None
        self._session: Any = None
        self._handle: str | None = None
        self._closed = False
        self._swapped = asyncio.Event()

    def _build(self) -> types.LiveConnectConfig:
        cfg = self._config
        assert cfg is not None
        transcription = types.AudioTranscriptionConfig(
            language_codes=[cfg.language_code],
            custom_vocabulary=cfg.vocabulary[:1000] or None,
        )
        avatar = cfg.media_mode == "avatar"
        return types.LiveConnectConfig(
            response_modalities=["VIDEO"] if avatar else ["AUDIO"],
            avatar_config=types.AvatarConfig(avatar_name=self.settings.avatar_name) if avatar else None,
            speech_config=types.SpeechConfig(
                language_code=cfg.language_code,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.settings.voice_name)
                ),
            ),
            system_instruction=cfg.system_instruction,
            tools=[types.Tool(function_declarations=to_function_declarations(cfg.tools))],
            input_audio_transcription=transcription,
            output_audio_transcription=types.AudioTranscriptionConfig(language_codes=[cfg.language_code]),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),
            session_resumption=types.SessionResumptionConfig(handle=self._handle),
        )

    async def _open(self) -> None:
        cm = self.client.aio.live.connect(model=self.settings.live_model, config=self._build())
        session = await cm.__aenter__()
        old_cm, self._cm, self._session = self._cm, cm, session
        self._swapped.set()
        if old_cm is not None:
            with contextlib.suppress(Exception):
                await old_cm.__aexit__(None, None, None)

    async def connect(self, config: L.LiveConfig) -> None:
        self._config = config
        await self._open()

    async def reconnect(self, media_mode: L.MediaMode) -> None:
        assert self._config is not None
        self._config.media_mode = media_mode
        log.info("live_reconnect", media_mode=media_mode, resumable=self._handle is not None)
        await self._open()

    async def events(self) -> AsyncIterator[L.LiveEvent]:
        while not self._closed:
            session = self._session
            self._swapped.clear()
            try:
                async for msg in session.receive():
                    for event in self._map(msg):
                        yield event
                    if self._session is not session:
                        break
            except Exception:
                if self._closed:
                    return
                if self._session is session:
                    raise
            if self._session is session and not self._closed:
                await asyncio.sleep(0)  # receive() ends per turn; loop for the next turn

    def _map(self, msg: types.LiveServerMessage) -> list[L.LiveEvent]:
        out: list[L.LiveEvent] = []
        if msg.session_resumption_update and msg.session_resumption_update.new_handle:
            self._handle = msg.session_resumption_update.new_handle
        sc = msg.server_content
        if sc:
            if sc.input_transcription and sc.input_transcription.text:
                out.append(L.InputTranscript(sc.input_transcription.text, bool(sc.input_transcription.finished)))
            if sc.model_turn:
                for part in sc.model_turn.parts or []:
                    blob = part.inline_data
                    if blob and blob.data:
                        mime = blob.mime_type or ""
                        out.append(L.VideoChunk(blob.data) if mime.startswith("video/") else L.AudioOut(blob.data))
            if sc.output_transcription and sc.output_transcription.text:
                out.append(L.OutputTranscript(sc.output_transcription.text, bool(sc.output_transcription.finished)))
            if sc.interrupted:
                out.append(L.Interrupted())
            if sc.turn_complete:
                out.append(L.TurnComplete())
        if msg.tool_call:
            for fc in msg.tool_call.function_calls or []:
                out.append(L.ToolCall(id=fc.id or "", name=fc.name or "", args=dict(fc.args or {})))
        if msg.tool_call_cancellation and msg.tool_call_cancellation.ids:
            out.append(L.ToolCallCancelled(tuple(msg.tool_call_cancellation.ids)))
        if msg.go_away:
            left = msg.go_away.time_left
            out.append(L.GoAway(float(left.total_seconds()) if hasattr(left, "total_seconds") else None))
        if msg.usage_metadata:
            u = msg.usage_metadata
            out.append(L.Usage(u.prompt_token_count or 0, u.response_token_count or 0))
        return out

    async def send_audio(self, pcm_16k: bytes) -> None:
        await self._session.send_realtime_input(audio=types.Blob(data=pcm_16k, mime_type="audio/pcm;rate=16000"))

    async def send_video(self, jpeg: bytes) -> None:
        await self._session.send_realtime_input(video=types.Blob(data=jpeg, mime_type="image/jpeg"))

    async def send_text(self, text: str, *, role: Literal["user", "system_note"] = "user") -> None:
        await self._session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=text)]), turn_complete=True
        )

    async def send_tool_response(self, call_id: str, name: str, response: dict[str, Any],
                                 scheduling: L.Scheduling) -> None:
        await self._session.send_tool_response(function_responses=[types.FunctionResponse(
            id=call_id, name=name, response=response,
            scheduling=types.FunctionResponseScheduling[scheduling],
        )])

    async def close(self) -> None:
        self._closed = True
        if self._cm is not None:
            with contextlib.suppress(Exception):
                await self._cm.__aexit__(None, None, None)
