"""Health response (T088, FR-032, FR-033): on a warning sign the assistant suggests a doctor and offers
to tell the family. Shopping is NOT paused: products, cart and checkout keep working."""

import re

from session_server.core import confirm
from session_server.core.runtime import Runtime
from session_server.core.safety.detector import lexicon_verdict, mentions_health
from session_server.ports.classifier import SafetyVerdict

HOLD_NOTE = (
    "[SERVER NOTE — HEALTH] A warning sign was mentioned ({sign}). Once, gently and respectfully "
    "suggest seeing a doctor soon (or emergency help if it sounds serious), then ask whether they "
    "would like you to tell their family member inside the app. Call notify_family only if they "
    "clearly say yes. Shopping is NOT paused: keep helping with any product, cart or checkout "
    "request as usual. Still never offer medicines or supplements."
)

_DOCTOR = re.compile(r"डॉक्टर|डाक्टर|चिकित्सक|अस्पताल|doctor|hospital|clinic", re.IGNORECASE)


async def apply(rt: Runtime, verdict: SafetyVerdict) -> None:
    if not verdict.warning_sign or rt.health_noted:
        return
    rt.health_noted = True  # the doctor suggestion and family offer happen once per session
    confirm.arm(rt, "family", [])
    await rt.live.send_text(HOLD_NOTE.format(sign=verdict.sign or "health"), role="system_note")


def on_assistant_text(rt: Runtime, text: str) -> None:
    if rt.session.safety_hold and _DOCTOR.search(text):
        rt.doctor_suggested = True


async def maybe_clear(rt: Runtime, shopper_text: str) -> None:
    """Clear the hold when, after the doctor suggestion, the shopper asks for something unrelated."""
    if not rt.session.safety_hold or not rt.doctor_suggested:
        return
    if lexicon_verdict(shopper_text).warning_sign or mentions_health(shopper_text):
        return
    is_short_answer = len(shopper_text.split()) <= 3 and (
        confirm.is_affirmative(shopper_text) or confirm.is_negative(shopper_text)
    )
    if is_short_answer:
        return  # a bare yes/no answers the family question; it is not a new request
    rt.session.safety_hold = False
    await rt.ui.send_json(state_msg(rt))
