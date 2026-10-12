"""Orchestrator flow (T032, gate path for US1) with a scripted fake Live session."""

import asyncio

from session_server.adapters.memory.state import MemoryState
from session_server.core.session import FRAME_MIC, FRAME_MP4_OUT, FRAME_PCM_OUT, ConversationSession
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.ports import live as L
from session_server.testing.fakes import make_runtime


async def _drain(convo: ConversationSession, rt) -> None:
    rt.live.emit(None)
    await asyncio.wait_for(convo.run(), timeout=5)


def _setup():
    rt = make_runtime()
    state = MemoryState()
    return rt, state, ConversationSession(rt, ToolRouter(rt, HANDLERS), state)


async def test_spoken_list_lands_in_cart_with_cards_and_captions() -> None:
    rt, state, convo = _setup()
    rt.live.emit(
        L.InputTranscript("दो लीटर दूध और ", False),
        L.InputTranscript("पाव किलो टमाटर", True),
        L.ToolCall("1", "search_catalog", {"query": "doodh", "amount_phrase": "दो लीटर"}),
        L.ToolCall("2", "search_catalog", {"query": "tamatar", "amount_phrase": "पाव किलो"}),
    )
    run = asyncio.ensure_future(convo.run())
    for _ in range(50):
        await asyncio.sleep(0)
        if rt.live.response_for("1") and rt.live.response_for("2"):
            break
    milk = rt.live.response_for("1")["result"]["pack_plans"][0]
    tomato = rt.live.response_for("2")["result"]["pack_plans"][0]
    assert (milk["product_id"], milk["qty"]) == ("p-0112", 2)
    assert (tomato["product_id"], tomato["qty"]) == ("p-0007", 1)

    rt.live.emit(
        L.ToolCall("3", "add_to_cart", {"product_id": "p-0112", "qty": 2}),
        L.ToolCall("4", "add_to_cart", {"product_id": "p-0007", "qty": 1}),
        L.OutputTranscript("दो लीटर दूध और 250 ग्राम टमाटर डाल दिए।", True),
        L.TurnComplete(),
        None,
    )
    await asyncio.wait_for(run, timeout=5)

    cart = rt.ui.of("cart")[-1]["cart"]
    assert {(line["product"]["id"], line["qty"]) for line in cart["lines"]} == {("p-0112", 2), ("p-0007", 1)}
    assert cart["total"] == 2 * 54 + 10
    captions = [c for c in rt.ui.of("caption") if c["final"]]
    assert captions[0]["who"] == "shopper" and captions[0]["text_hi"] == "दो लीटर दूध और पाव किलो टमाटर"
    assert any(c["who"] == "assistant" for c in captions)
    assert state.sessions["s-test"].ended_at is not None  # usage persisted at end


async def test_media_is_relayed_and_interruption_flushes() -> None:
    rt, _, convo = _setup()
    await convo.on_client_bytes(bytes([FRAME_MIC]) + b"\x00\x01" * 320)
    assert rt.live.audio and rt.session.usage.audio_in_s > 0
    rt.live.emit(L.AudioOut(b"\x00" * 480), L.VideoChunk(b"mp4"), L.Interrupted())
    await _drain(convo, rt)
    assert rt.ui.frames[0][0] == FRAME_PCM_OUT and rt.ui.frames[1][0] == FRAME_MP4_OUT
    assert rt.ui.of("interrupted")


async def test_warning_sign_in_partial_transcript_arms_hold_before_tool_call() -> None:
    rt, _, convo = _setup()
    rt.live.emit(
        L.InputTranscript("मैं कल गिर गया और पैर सुन्न", False),
        L.ToolCall("1", "show_products", {"ids": ["p-0112"]}),
    )
    run = asyncio.ensure_future(convo.run())
    for _ in range(50):
        await asyncio.sleep(0)
        if rt.live.response_for("1"):
            break
    assert rt.live.response_for("1")["status"] == "refused"
    rt.live.emit(None)
    await asyncio.wait_for(run, timeout=5)
    assert not rt.ui.of("cards")


async def test_no_speech_markers_are_not_captions() -> None:
    rt, _, convo = _setup()
    rt.live.emit(L.OutputTranscript("<no speech>", True), L.OutputTranscript("नमस्ते", True))
    await _drain(convo, rt)
    texts = [c["text_hi"] for c in rt.ui.of("caption")]
    assert "नमस्ते" in texts and not any("no speech" in t for t in texts)


async def test_new_shopper_turn_resets_duplicate_guard() -> None:
    rt, _, convo = _setup()
    rt.turn_adds.add(("item", "p-0112", 2, "named"))
    await convo.on_client_json({"type": "text", "text": "do litre aur"})
    assert rt.turn_adds == set()


async def test_typed_text_works_like_speech() -> None:
    rt, _, convo = _setup()
    await convo.on_client_json({"type": "text", "text": "do litre doodh"})
    assert ("user", "do litre doodh") in rt.live.texts
    assert rt.ui.of("caption")[-1]["text_hi"] == "do litre doodh"


async def test_low_bandwidth_switches_to_audio_only() -> None:
    rt, _, convo = _setup()
    await convo.on_client_json({"type": "net_quality", "downlink_kbps": 400, "underruns": 0})
    assert rt.session.media_mode == "audio_only" and rt.live.reconnects == ["audio_only"]
    assert rt.ui.of("state")[-1]["media_mode"] == "audio_only"


async def test_camera_frames_only_forwarded_while_active() -> None:
    rt, _, convo = _setup()
    await convo.on_client_bytes(bytes([0x02]) + b"jpeg")
    assert rt.live.video == []
    await convo.on_client_json({"type": "camera", "active": True})
    await convo.on_client_bytes(bytes([0x02]) + b"jpeg")
    assert rt.live.video == [b"jpeg"]
