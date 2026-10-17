"""Server-observable shopper confirmation for inferred items (T058, FR-015).

The server arms a pending confirmation when it proposes inferred items; the next shopper input
confirms or clears it; non-`named` adds require a confirmed, matching, unexpired confirmation.
"""

import asyncio
import re

from session_server.core.runtime import Runtime
from session_server.models.domain import PendingConfirmation

EXPIRY_S = 60.0  # a "yes" must be acted on within this long
# Reading a long list aloud (a dish for 50 people) takes minutes, and the shopper's "yes" comes after
# it: the wait for the answer must outlive the reading, or the yes is thrown away.
ASK_EXPIRY_S = 300.0

_AFFIRMATIVE = re.compile(
    r"(^|\s)(हाँ|हां|हा|हाँजी|हांजी|जी\s*हाँ|ठीक\s*है|कर\s*दो|डाल\s*दो|जोड़\s*दो|बिल्कुल|"
    r"चलेगा|चलिए|चलो|चलता\s*है|करिए|कीजिए|डालिए|जोड़िए|अच्छा|सही\s*है|ज़रूर|जरूर|वही|"
    r"chalega|chalo|chaliye|kariye|kijiye|daaliye|achha|accha|sahi\s*hai|zaroor|jarur|"
    r"go\s*ahead|add\s*(it|them|all)|that'?s\s*(fine|right|good)|fine|correct|right|"
    r"haan|haa|han|ha|haanji|ji\s*haan|theek\s*hai|thik\s*hai|kar\s*do|daal\s*do|dal\s*do|"
    r"jod\s*do|bilkul|yes|yeah|yep|ok|okay|sure|please\s*add)(?=$|\s|[,.!?।])",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"(^|\s)(नहीं|नही|मत|रहने\s*दो|nahin|nahi|nahi\s*chahiye|mat|rehne\s*do|no|nope|don'?t|cancel)"
    r"(?=$|\s|[,.!?।])",
    re.IGNORECASE,
)


# An explicit instruction to add: it counts as a yes even when a plain "no" is in the same sentence
# ("No, I don't have any, please add everything").
_ADD_NOW = re.compile(
    r"(add\s*(it|them|all|everything|the\s*rest|these)|go\s*ahead|put\s*(it|them|everything)\s*in|"
    r"kar\s*do|daal\s*do|dal\s*do|jod\s*do|dal\s*dijiye|daal\s*dijiye|कर\s*दो|डाल\s*दो|जोड़\s*दो|डाल\s*दीजिए)",
    re.IGNORECASE,
)
# An explicit refusal or cancellation: the pending list is dropped.
_STOP = re.compile(
    r"(don'?t\s*add|do\s*not\s*add|never\s*mind|cancel|rehne\s*do|mat\s*(daal|dal|jod|add|kar)|nahi\s*chahiye|"
    r"नहीं\s*चाहिए|रहने\s*दो|मत\s*(डाल|जोड़|कर)|remove\s*(it|them|all|everything))",
    re.IGNORECASE,
)


# An explicit instruction to add: it counts as a yes even when a plain "no" is in the same sentence
# ("No, I don't have any, please add everything").
_ADD_NOW = re.compile(
    r"(add\s*(it|them|all|everything|the\s*rest|these)|go\s*ahead|put\s*(it|them|everything)\s*in|"
    r"kar\s*do|daal\s*do|dal\s*do|jod\s*do|dal\s*dijiye|daal\s*dijiye|कर\s*दो|डाल\s*दो|जोड़\s*दो|डाल\s*दीजिए)",
    re.IGNORECASE,
)
# An explicit refusal or cancellation: the pending list is dropped.
_STOP = re.compile(
    r"(don'?t\s*add|do\s*not\s*add|never\s*mind|cancel|rehne\s*do|mat\s*(daal|dal|jod|add|kar)|nahi\s*chahiye|"
    r"नहीं\s*चाहिए|रहने\s*दो|मत\s*(डाल|जोड़|कर)|remove\s*(it|them|all|everything))",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRMATIVE.search(text)) and not is_negative(text)


def is_negative(text: str) -> bool:
    return bool(_NEGATIVE.search(text))


def arm(rt: Runtime, kind: str, product_ids: list[str]) -> None:
    pc = rt.session.pending_confirmation
    # Re-proposing the same (or fewer) items must not wipe a "yes" already given — models often
    # re-show the list right after the shopper agrees (seen in live rehearsal).
    if (pc is not None and pc.confirmed and not _expired(rt, pc) and pc.kind == kind
            and set(product_ids) <= set(pc.product_ids)):
        pc.armed_at = rt.clock()
        return
    rt.session.pending_confirmation = PendingConfirmation(
        kind=kind, product_ids=list(product_ids), armed_at=rt.clock(), confirmed=False
    )


def _expired(rt: Runtime, pc: PendingConfirmation) -> bool:
    return rt.clock() - pc.armed_at > (EXPIRY_S if pc.confirmed else ASK_EXPIRY_S)


def on_shopper_input(rt: Runtime, text: str) -> None:
    """Confirm, revoke or clear the pending confirmation from the shopper's words.

    A plain "no" (often the answer to "do you have any at home?") only withdraws a yes; the list stays pending
    so a later "yes, add it" works. Only an explicit refusal ("cancel", "don't add", "rehne do") drops it."""
    pc = rt.session.pending_confirmation
    if pc is None:
        return
    if _expired(rt, pc) or _STOP.search(text):
        rt.session.pending_confirmation = None
    elif _ADD_NOW.search(text) or is_affirmative(text):
        pc.confirmed = True
        pc.armed_at = rt.clock()  # the 60 s window restarts from the "yes"
    elif is_negative(text):
        pc.confirmed = False


def allows(rt: Runtime, kind: str, product_ids: list[str]) -> bool:
    pc = rt.session.pending_confirmation
    return (
        pc is not None
        and pc.confirmed
        and not _expired(rt, pc)
        and pc.kind == kind
        and all(pid in pc.product_ids for pid in product_ids)
    )


def pending_unconfirmed_for(rt: Runtime, product_id: str) -> bool:
    """True if this product was proposed as an inferred item and the shopper hasn't said yes."""
    pc = rt.session.pending_confirmation
    return (
        pc is not None
        and not pc.confirmed
        and not _expired(rt, pc)
        and pc.kind in {"camera", "usual"}
        and product_id in pc.product_ids
    )


GRACE_S = 4.0  # how long a tool call may wait for the transcript of a "yes" the shopper is still saying
RECENT_SPEECH_S = 8.0


async def grace(rt: Runtime) -> None:
    """The model hears a spoken "yes" and may call add_to_cart before the transcript of that "yes" has reached
    us (the transcript is a separate, slightly slower stream, slower still over the network). If the shopper
    has just spoken and a confirmation is waiting, give the transcript a moment to arrive before judging."""
    deadline = rt.clock() + GRACE_S
    while rt.clock() < deadline:
        pc = rt.session.pending_confirmation
        if pc is None or pc.confirmed:
            return
        if rt.clock() - rt.last_shopper_signal > RECENT_SPEECH_S:
            return  # the shopper has not said anything lately: nothing to wait for
        await asyncio.sleep(0.15)


def why_not(rt: Runtime, kind: str, product_ids: list[str]) -> str:
    """For the log: why a confirmation was not found."""
    pc = rt.session.pending_confirmation
    if pc is None:
        return "no confirmation is pending"
    if pc.kind != kind:
        return f"pending is for {pc.kind}, not {kind}"
    if _expired(rt, pc):
        return "the confirmation expired"
    if not pc.confirmed:
        return "the shopper has not said yes yet"
    missing = [p for p in product_ids if p not in pc.product_ids]
    return f"the list changed since the yes ({len(missing)} items not in the confirmed list)"


def consume(rt: Runtime) -> None:
    rt.session.pending_confirmation = None
