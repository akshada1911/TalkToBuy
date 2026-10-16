"""A greeting the app can play the moment a session opens.

Connecting to the live voice model takes several seconds, so the first line (the greeting and the
opening question) is recorded ahead of time with the same voice, kept in memory and on disk, and
played at once while the live session connects. If a line is not ready yet the live model says it
instead, as before.
"""

import asyncio
import hashlib
from pathlib import Path

from session_server.config import Settings
from session_server.logging import get_logger

log = get_logger(__name__)

_CACHE: dict[tuple[str, str], bytes] = {}
_BUSY: set[tuple[str, str]] = set()

TTS_LANGUAGE_CODES = {"hi": "hi-IN", "en": "en-IN"}


def _path(settings: Settings, text: str, language: str) -> Path:
    key = hashlib.sha1(f"{settings.greeting_tts_model}|{settings.voice_name}|{language}|{text}".encode()).hexdigest()
    return Path(settings.greeting_cache_dir) / f"{key}.pcm"


def get(settings: Settings, text: str, language: str) -> bytes | None:
    """The recorded line (24 kHz mono 16-bit PCM), if it is ready."""
    hit = _CACHE.get((language, text))
    if hit is not None:
        return hit
    try:
        path = _path(settings, text, language)
        if path.is_file():
            _CACHE[(language, text)] = path.read_bytes()
            return _CACHE[(language, text)]
    except OSError:
        pass
    return None


async def synthesize(settings: Settings, text: str, language: str) -> bytes | None:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=settings.require_gcp(), location=settings.gcp_location)
    resp = await asyncio.wait_for(
        client.aio.models.generate_content(
            model=settings.greeting_tts_model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    language_code=TTS_LANGUAGE_CODES.get(language, "en-IN"),
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.voice_name)),
                ),
            ),
        ),
        40,
    )
    blob = resp.candidates[0].content.parts[0].inline_data
    return bytes(blob.data) if blob and blob.data and "pcm" in (blob.mime_type or "") else None


async def ensure(settings: Settings, text: str, language: str) -> bytes | None:
    """Record the line if it is not ready (one attempt at a time per line); never raises."""
    hit = get(settings, text, language)
    if hit is not None or (language, text) in _BUSY:
        return hit
    _BUSY.add((language, text))
    try:
        pcm = await synthesize(settings, text, language)
        if pcm:
            _CACHE[(language, text)] = pcm
            try:
                path = _path(settings, text, language)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(pcm)
            except OSError:
                log.warning("greeting_cache_write_failed")
            log.info("greeting_ready", language=language, seconds=round(len(pcm) / 48000, 1))
        return pcm
    except Exception:
        log.warning("greeting_tts_failed", language=language)
        return None
    finally:
        _BUSY.discard((language, text))
