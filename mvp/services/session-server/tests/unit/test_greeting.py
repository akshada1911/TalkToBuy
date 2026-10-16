"""The opening line: recorded ahead of time, played at once, and the live model carries on after it."""

from session_server.adapters.memory.state import MemoryState
from session_server.config import Settings
from session_server.core import greeting
from session_server.core.prompts import build_system_instruction, opening_text
from session_server.core.session import FRAME_PCM_OUT, ConversationSession
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.models.domain import Shopper
from session_server.testing.fakes import make_runtime

SHOPPER = Shopper(id="u", display_name="Vaibhav", language="hi", address_form="neutral")


def test_the_opening_line_greets_by_name_and_asks_the_opening_question() -> None:
    assert opening_text(SHOPPER, "en") == "Namaste Vaibhav! What would you like today?"
    assert opening_text(SHOPPER, "hi").startswith("नमस्ते Vaibhav!")


def test_the_model_is_told_not_to_repeat_a_greeting_the_app_already_played() -> None:
    said = opening_text(SHOPPER, "en")
    after = build_system_instruction(SHOPPER, "guided", language="en", greeted=said)
    assert "ALREADY greeted" in after and said in after and "{" not in after
    before = build_system_instruction(SHOPPER, "guided", language="en")
    assert "ALREADY greeted" not in before and "greet briefly" in before


async def test_playing_the_greeting_sends_audio_frames_and_a_caption() -> None:
    rt = make_runtime()
    convo = ConversationSession(rt, ToolRouter(rt, HANDLERS), MemoryState())
    pcm = bytes(48000)  # one second of silence
    await convo.play_greeting("Namaste Vaibhav! Step by step, or quickly?", pcm)
    assert len(rt.ui.frames) == 5 and all(f[0] == FRAME_PCM_OUT for f in rt.ui.frames)
    assert sum(len(f) - 1 for f in rt.ui.frames) == len(pcm)
    caption = rt.ui.of("caption")[-1]
    assert caption["who"] == "assistant" and caption["final"] and caption["text_hi"].startswith("Namaste Vaibhav")
    assert rt.session.usage.audio_out_s == 1.0


async def test_a_recorded_line_is_kept_and_found_again(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, greeting_cache_dir=str(tmp_path))
    greeting._CACHE.clear()
    calls = []

    async def fake_synth(s, text, language):
        calls.append(text)
        return b"\x01\x02" * 100

    monkeypatch.setattr(greeting, "synthesize", fake_synth)
    assert greeting.get(settings, "hello", "en") is None
    assert await greeting.ensure(settings, "hello", "en") == b"\x01\x02" * 100
    assert await greeting.ensure(settings, "hello", "en") == b"\x01\x02" * 100  # second time: no new recording
    assert calls == ["hello"]
    greeting._CACHE.clear()  # a new process finds it on disk
    assert greeting.get(settings, "hello", "en") == b"\x01\x02" * 100


async def test_a_failed_recording_never_raises(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, greeting_cache_dir=str(tmp_path))
    greeting._CACHE.clear()

    async def boom(s, text, language):
        raise RuntimeError("no tts")

    monkeypatch.setattr(greeting, "synthesize", boom)
    assert await greeting.ensure(settings, "x", "en") is None
    assert greeting.get(settings, "x", "en") is None
