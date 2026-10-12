"""Pace (guided | quick) tracking (T094, FR-027–FR-029). The app never asks the shopper's age."""

import re

from session_server.core.runtime import Runtime
from session_server.core.ui import state_msg

_REPEAT = re.compile(
    r"दोबारा|फिर\s*से|क्या\s*कहा|समझ\s*नहीं|dobara|phir\s*se|fir\s*se|kya\s*kaha|samajh\s*nahi|"
    r"samjha\s*nahi|repeat|say\s+(that\s+)?again|didn'?t\s+understand",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"^\s*(नहीं|नही|nahi|nahin|no)(?=$|\s|[,.!?।])|गलत|ग़लत|galat|wrong|मैंने\s*यह\s*नहीं|maine\s*ye\s*nahi|"
    r"i\s+didn'?t\s+say|not\s+that",
    re.IGNORECASE,
)

PACE_NOTES = {
    "guided": (
        "[SERVER NOTE — PACE] Pace is now GUIDED: one item at a time, read each item back, and "
        "confirm each step. Tell the shopper briefly that you will go step by step."
    ),
    "quick": "[SERVER NOTE — PACE] Pace is now QUICK: act on the request, then summarise once.",
}


async def set_pace(rt: Runtime, mode: str, reason: str = "shopper_asked", notify_model: bool = False) -> None:
    rt.session.pace = mode
    rt.session.correction_count = 0
    await rt.ui.send_json(state_msg(rt))
    if notify_model:
        await rt.live.send_text(PACE_NOTES[mode], role="system_note")


async def on_shopper_input(rt: Runtime, text: str) -> None:
    """Switch quick → guided on a repeat request or a second correction (FR-029)."""
    if rt.session.pace != "quick":
        return
    if _REPEAT.search(text):
        await set_pace(rt, "guided", "repeat_or_corrections", notify_model=True)
        return
    if _CORRECTION.search(text):
        rt.session.correction_count += 1
        if rt.session.correction_count >= 2:
            await set_pace(rt, "guided", "repeat_or_corrections", notify_model=True)
