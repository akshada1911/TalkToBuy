"""Server-observable shopper confirmation for inferred items (T058, FR-015).

The server arms a pending confirmation when it proposes inferred items; the next shopper input
confirms or clears it; non-`named` adds require a confirmed, matching, unexpired confirmation.
"""

import re

from session_server.core.runtime import Runtime
from session_server.models.domain import PendingConfirmation

EXPIRY_S = 60.0

_AFFIRMATIVE = re.compile(
    r"(^|\s)(हाँ|हां|हा|हाँजी|हांजी|जी\s*हाँ|ठीक\s*है|कर\s*दो|डाल\s*दो|जोड़\s*दो|बिल्कुल|"
    r"haan|haa|han|ha|haanji|ji\s*haan|theek\s*hai|thik\s*hai|kar\s*do|daal\s*do|dal\s*do|"
    r"jod\s*do|bilkul|yes|yeah|yep|ok|okay|sure|please\s*add)(?=$|\s|[,.!?।])",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"(^|\s)(नहीं|नही|मत|रहने\s*दो|nahin|nahi|nahi\s*chahiye|mat|rehne\s*do|no|nope|don'?t|cancel)"
    r"(?=$|\s|[,.!?।])",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRMATIVE.search(text)) and not is_negative(text)


def is_negative(text: str) -> bool:
    return bool(_NEGATIVE.search(text))


def arm(rt: Runtime, kind: str, product_ids: list[str]) -> None:
    rt.session.pending_confirmation = PendingConfirmation(
        kind=kind, product_ids=list(product_ids), armed_at=rt.clock(), confirmed=False
    )


def _expired(rt: Runtime, pc: PendingConfirmation) -> bool:
    return rt.clock() - pc.armed_at > EXPIRY_S


def on_shopper_input(rt: Runtime, text: str) -> None:
    """Confirm or clear the pending confirmation from the shopper's words."""
    pc = rt.session.pending_confirmation
    if pc is None:
        return
    if _expired(rt, pc) or is_negative(text):
        rt.session.pending_confirmation = None
    elif is_affirmative(text):
        pc.confirmed = True
        pc.armed_at = rt.clock()  # the 60 s window restarts from the "yes"


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


def consume(rt: Runtime) -> None:
    rt.session.pending_confirmation = None
