"""Cost controls: audio pause, translation scope, idle timeout, slim tool results, start mode."""

import asyncio

from session_server.adapters.memory.state import MemoryState
from session_server.core.session import ConversationSession
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.core.tools.catalog import search_catalog
from session_server.ports import live as L
from session_server.testing.fakes import make_runtime


class Clock:
    def __init__(self) -> None:
        self.t = 10_000.0

    def __call__(self) -> float:
        return self.t


class EchoTranslate:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def to_english(self, text_hi: str) -> str:
        self.calls.append(text_hi)
        return f"EN:{text_hi}"


def _convo(rt, translate=None) -> ConversationSession:
    return ConversationSession(rt, ToolRouter(rt, HANDLERS), MemoryState(), translate=translate)


async def test_audio_pause_tells_the_model_the_stream_paused() -> None:
    rt = make_runtime()
    await _convo(rt).on_client_json({"type": "audio_pause"})
    assert rt.live.audio_ends == 1


async def test_english_is_off_by_default_and_only_assistant_lines_are_translated() -> None:
    rt = make_runtime()
    assert rt.session.show_translation is False
    tr = EchoTranslate()
    convo = _convo(rt, tr)
    rt.live.emit(L.InputTranscript("दो लीटर दूध", True), L.OutputTranscript("डाल दिया", True), None)
    await asyncio.wait_for(convo.run(), timeout=5)
    await asyncio.sleep(0)
    assert tr.calls == []  # English off: no translation calls at all

    rt = make_runtime()
    rt.session.show_translation = True
    tr = EchoTranslate()
    convo = _convo(rt, tr)
    rt.live.emit(L.InputTranscript("दो लीटर दूध", True), L.OutputTranscript("डाल दिया", True), None)
    await asyncio.wait_for(convo.run(), timeout=5)
    for _ in range(5):
        await asyncio.sleep(0)
    assert tr.calls == ["डाल दिया"]  # assistant only, not the shopper's line


async def test_idle_session_warns_at_50s_and_ends_at_60s() -> None:
    clock = Clock()
    rt = make_runtime(clock=clock)
    convo = _convo(rt)
    clock.t += 49
    assert await convo.idle_tick() is False and rt.live.texts == []
    clock.t += 1
    assert await convo.idle_tick() is False
    assert any("quiet" in text for role, text in rt.live.texts if role == "system_note")
    # the assistant's goodbye line must not reset the idle clock
    convo._last_assistant = clock.t
    clock.t += 10
    assert await convo.idle_tick() is True
    assert rt.ui.of("error")[-1]["code"] == "idle" and rt.live.closed


async def test_speaking_resets_idle_and_payment_step_never_times_out() -> None:
    clock = Clock()
    rt = make_runtime(clock=clock)
    convo = _convo(rt)
    clock.t += 55
    await convo.on_client_bytes(bytes([0x01]) + b"\x00\x01" * 320)  # shopper spoke
    clock.t += 30
    assert await convo.idle_tick() is False and convo.idle_for() == 30

    rt.payment_future = asyncio.get_running_loop().create_future()  # fingerprint screen open
    clock.t += 300
    assert await convo.idle_tick() is False
    rt.payment_future.cancel()


async def test_search_returns_at_most_five_slim_products() -> None:
    rt = make_runtime()
    out = await search_catalog(rt, {"query": "doodh milk butter tamatar maida cocoa paneer atta"})
    assert len(out["products"]) <= rt.settings.search_limit == 5
    assert set(out["products"][0]) <= {"id", "name", "local_name", "size", "price", "in_stock", "listing"}
    plans = (await search_catalog(rt, {"query": "doodh", "amount_phrase": "do litre"}))["pack_plans"]
    assert len(plans) <= 2 and "interpreted_en" not in plans[0]


async def test_english_sessions_never_call_translation() -> None:
    rt = make_runtime()
    rt.session.language = "en"
    rt.session.show_translation = True
    tr = EchoTranslate()
    convo = _convo(rt, tr)
    rt.live.emit(L.OutputTranscript("I added two litres of milk.", True), None)
    await asyncio.wait_for(convo.run(), timeout=5)
    for _ in range(5):
        await asyncio.sleep(0)
    assert tr.calls == []
