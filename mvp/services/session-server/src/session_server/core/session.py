"""Session orchestrator (T032): pumps Live events to the widget and widget input to Live.

Responsibilities:
- relay media (0x11 PCM, 0x12 MP4) unchanged; turn transcripts into captions with translations;
- run the shopper-input hooks (safety lexicon on every partial; confirmation; pace; hold clearing);
- dispatch tool calls to the router as background tasks (no dead air);
- enforce the 10-minute cap with a warning at 9 minutes; write usage at the end (FR-043);
- never persist audio, video or transcripts (FR-040).
"""

import asyncio
import contextlib
import re
from typing import Any

from session_server.core import confirm, pace
from session_server.core.cost import estimate_usd
from session_server.core.runtime import Runtime
from session_server.core.safety import detector, hold
from session_server.core.tool_router import ToolRouter
from session_server.core.ui import state_msg
from session_server.logging import get_logger
from session_server.models.messages import CaptionMsg, ErrorMsg, InterruptedMsg
from session_server.ports import live as L
from session_server.ports.classifier import ClassifierPort
from session_server.ports.state import StatePort
from session_server.ports.translate import TranslatePort

log = get_logger(__name__)

FRAME_MIC, FRAME_JPEG, FRAME_PCM_OUT, FRAME_MP4_OUT = 0x01, 0x02, 0x11, 0x12
NO_SPEECH = re.compile(r"^\s*<\s*no[ _-]?speech", re.IGNORECASE)
LOW_DOWNLINK_KBPS = 1000
UNDERRUNS_LIMIT = 3

TIME_WARNING_NOTE = (
    "[SERVER NOTE] About one minute is left in this session. Politely tell the shopper, and offer "
    "to finish the order now if the cart has items."
)


class ConversationSession:
    def __init__(
        self,
        rt: Runtime,
        router: ToolRouter,
        state: StatePort,
        translate: TranslatePort | None = None,
        classifier: ClassifierPort | None = None,
    ):
        self.rt = rt
        self.router = router
        self.state = state
        self.translate = translate
        self.classifier = classifier
        self._turns = {"shopper": 0, "assistant": 0}
        self._text = {"shopper": "", "assistant": ""}
        self._ended = asyncio.Event()

    # ---------- lifecycle ----------

    async def run(self) -> None:
        timer = self.rt.spawn(self._cap_timer())
        try:
            await self.rt.ui.send_json(state_msg(self.rt))
            async for event in self.rt.live.events():
                await self._on_live_event(event)
                if self._ended.is_set():
                    break
        finally:
            timer.cancel()
            await self.end("live_closed")

    async def end(self, reason: str) -> None:
        if self._ended.is_set():
            return
        self._ended.set()
        s = self.rt.session
        s.ended_at = self.rt.clock()
        s.usage.est_cost_usd = estimate_usd(s.usage)
        current = asyncio.current_task()
        in_flight = [t for t in self.rt.background if t is not current and not t.done()]
        if in_flight:  # let tool calls already received finish (cart writes), briefly
            await asyncio.wait(in_flight, timeout=1.0)
        for task in list(self.rt.background):
            if task is not current:
                task.cancel()
        with contextlib.suppress(Exception):
            await self.state.save(s)
        with contextlib.suppress(Exception):
            await self.rt.live.close()
        log.info("session_ended", session_id=s.session_id, reason=reason,
                 usage=s.usage.model_dump())

    async def _cap_timer(self) -> None:
        cfg = self.rt.settings
        elapsed = self.rt.clock() - self.rt.session.started_at
        await asyncio.sleep(max(0, cfg.session_warn_s - elapsed))
        await self.rt.live.send_text(TIME_WARNING_NOTE, role="system_note")
        await self.rt.ui.send_json(state_msg(self.rt))
        await asyncio.sleep(max(0, cfg.session_cap_s - cfg.session_warn_s))
        await self.rt.ui.send_json(ErrorMsg(type="error", code="time_cap",
                                            message_hi="समय पूरा हुआ। धन्यवाद!",
                                            message_en="Session time is up. Thank you!"))
        await self.end("time_cap")

    # ---------- widget → server ----------

    async def on_client_bytes(self, data: bytes) -> None:
        if not data:
            return
        kind, payload = data[0], data[1:]
        usage = self.rt.session.usage
        if kind == FRAME_MIC:
            usage.audio_in_s += len(payload) / 32000  # 16 kHz × 2 bytes
            await self.rt.live.send_audio(payload)
        elif kind == FRAME_JPEG and self.rt.camera_active:
            usage.video_in_s += 1.0  # ≤ 1 fps
            await self.rt.live.send_video(payload)

    async def on_client_json(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        s = self.rt.session
        if kind == "text":
            text = str(msg.get("text", ""))[:500]
            await self._shopper_text(text, final=True)
            await self.rt.live.send_text(text, role="user")
        elif kind == "camera":
            self.rt.camera_active = bool(msg.get("active"))
        elif kind == "set_translation":
            s.show_translation = bool(msg.get("on"))
        elif kind == "set_media_mode":
            await self._switch_media(msg.get("mode", "avatar"))
        elif kind == "net_quality":
            downlink = msg.get("downlink_kbps")
            poor = (downlink is not None and downlink < LOW_DOWNLINK_KBPS) or (
                msg.get("underruns", 0) >= UNDERRUNS_LIMIT
            )
            if poor and s.media_mode == "avatar":
                await self._switch_media("audio_only")
        elif kind == "payment_result":
            fut = self.rt.payment_future
            if fut is not None and not fut.done() and msg.get("checkout_id") == s.checkout_id:
                fut.set_result({"approved": bool(msg.get("approved")), "mandate": msg.get("mandate")})
        elif kind == "end":
            await self.end("shopper_closed")

    async def _switch_media(self, mode: str) -> None:
        if mode not in ("avatar", "audio_only") or mode == self.rt.session.media_mode:
            return
        self.rt.session.media_mode = mode
        await self.rt.live.reconnect(mode)  # same conversation via session resumption (R12)
        await self.rt.ui.send_json(state_msg(self.rt))

    # ---------- Live → widget ----------

    async def _on_live_event(self, ev: L.LiveEvent) -> None:
        rt = self.rt
        if isinstance(ev, L.AudioOut):
            rt.session.usage.audio_out_s += len(ev.pcm) / 48000  # 24 kHz × 2 bytes
            await rt.ui.send_bytes(bytes([FRAME_PCM_OUT]) + ev.pcm)
        elif isinstance(ev, L.VideoChunk):
            await rt.ui.send_bytes(bytes([FRAME_MP4_OUT]) + ev.mp4)
        elif isinstance(ev, L.InputTranscript):
            await self._shopper_text(ev.text, final=ev.final, incremental=True)
        elif isinstance(ev, L.OutputTranscript):
            if NO_SPEECH.match(ev.text):
                return  # transcription markers like "<no speech>" are not captions
            await self._finish_turn("shopper")
            await self._assistant_text(ev.text, final=ev.final)
        elif isinstance(ev, L.ToolCall):
            await self._finish_turn("shopper")
            rt.spawn(self.router.handle(ev))
        elif isinstance(ev, L.Interrupted):
            await rt.ui.send_json(InterruptedMsg(type="interrupted", turn_id=self._turn_id("assistant")))
            await self._finish_turn("assistant")
        elif isinstance(ev, L.TurnComplete):
            await self._finish_turn("shopper")
            await self._finish_turn("assistant")
        elif isinstance(ev, L.GoAway):
            await rt.live.reconnect(rt.session.media_mode)
        elif isinstance(ev, L.Usage):
            rt.session.usage.tokens_in += ev.tokens_in
            rt.session.usage.tokens_out += ev.tokens_out

    # ---------- captions + hooks ----------

    def _turn_id(self, who: str) -> str:
        return f"{who[0]}{self._turns[who]}"

    async def _shopper_text(self, text: str, *, final: bool, incremental: bool = False) -> None:
        rt = self.rt
        self._text["shopper"] = (self._text["shopper"] + text) if incremental else text
        so_far = self._text["shopper"]
        # Cheap, deterministic checks on every partial, so guards are armed before any tool call.
        verdict = detector.lexicon_verdict(so_far)
        if verdict.warning_sign:
            await hold.apply(rt, verdict)
        confirm.on_shopper_input(rt, so_far)
        if final:
            await self._finish_turn("shopper")  # sends the single final caption
        else:
            await rt.ui.send_json(CaptionMsg(type="caption", who="shopper", turn_id=self._turn_id("shopper"),
                                             text_hi=so_far, text_en=None, final=False))

    async def _assistant_text(self, text: str, *, final: bool) -> None:
        self._text["assistant"] += text
        if final:
            await self._finish_turn("assistant")  # sends the single final caption
            return
        await self.rt.ui.send_json(CaptionMsg(type="caption", who="assistant",
                                              turn_id=self._turn_id("assistant"),
                                              text_hi=self._text["assistant"], text_en=None, final=False))

    async def _finish_turn(self, who: str) -> None:
        text = self._text[who].strip()
        if not text:
            return
        turn_id = self._turn_id(who)
        self._text[who] = ""
        self._turns[who] += 1
        rt = self.rt
        if who == "shopper":
            rt.shopper_turn_text = text
            rt.turn_adds.clear()  # a new request: identical adds are allowed again ("one more milk")
            verdict = await detector.evaluate(text, self.classifier)
            await hold.apply(rt, verdict)
            await hold.maybe_clear(rt, text)
            await pace.on_shopper_input(rt, text)
        else:
            hold.on_assistant_text(rt, text)
        await rt.ui.send_json(CaptionMsg(type="caption", who=who, turn_id=turn_id, text_hi=text,
                                         text_en=None, final=True))
        if self.translate is not None and rt.session.show_translation:
            rt.spawn(self._translate(who, turn_id, text))

    async def _translate(self, who: str, turn_id: str, text: str) -> None:
        english = await self.translate.to_english(text)  # type: ignore[union-attr]
        if english:
            await self.rt.ui.send_json(CaptionMsg(type="caption", who=who, turn_id=turn_id,
                                                  text_hi=text, text_en=english, final=True))
