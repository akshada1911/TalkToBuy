"""T093: pace defaults to guided, is set by the tool, and auto-switches on repeats/corrections."""

from session_server.core import pace
from session_server.core.tools.pace import set_pace
from session_server.testing.fakes import make_runtime


def test_default_is_guided() -> None:
    assert make_runtime().session.pace == "guided"


async def test_set_pace_updates_session_and_ui() -> None:
    rt = make_runtime()
    assert await set_pace(rt, {"mode": "quick", "reason": "opening_question"}) == {"pace": "quick"}
    assert rt.ui.of("state")[-1]["pace"] == "quick"


async def test_repeat_request_in_quick_switches_to_guided_and_tells_model() -> None:
    rt = make_runtime(pace="quick")
    await pace.on_shopper_input(rt, "क्या कहा? दोबारा बोलिए")
    assert rt.session.pace == "guided"
    assert any("GUIDED" in text for role, text in rt.live.texts if role == "system_note")


async def test_two_corrections_switch_to_guided() -> None:
    rt = make_runtime(pace="quick")
    await pace.on_shopper_input(rt, "नहीं, टमाटर नहीं")
    assert rt.session.pace == "quick"
    await pace.on_shopper_input(rt, "galat, maine ye nahi kaha")
    assert rt.session.pace == "guided"


async def test_guided_is_not_affected_by_corrections() -> None:
    rt = make_runtime(pace="guided")
    await pace.on_shopper_input(rt, "nahi galat")
    assert rt.session.pace == "guided" and rt.live.texts == []
