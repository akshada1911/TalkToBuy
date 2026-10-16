"""Server-side tool guards. They run before every handler and are what the tests rely on —
the prompt alone is never trusted for approval or safety (Principles I and II)."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from session_server.core import confirm
from session_server.core.runtime import Runtime
from session_server.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class Refusal:
    message: str
    retryable: bool = True


Guard = Callable[[Runtime, str, dict[str, Any]], Refusal | None]

def problem_limit_guard(rt: Runtime, name: str, args: dict[str, Any]) -> Refusal | None:
    if name == "show_products" and args.get("purpose") == "problem" and len(args.get("ids", [])) > 3:
        return Refusal("For a described problem, show at most 3 products (FR-034).")
    return None


def add_form_guard(rt: Runtime, name: str, args: dict[str, Any]) -> Refusal | None:
    if name != "add_to_cart":
        return None
    forms = [
        "product_id" in args or "qty" in args,
        "goal_id" in args,
        bool(args.get("usual")),
    ]
    if sum(forms) != 1:
        return Refusal("Use exactly one form: (product_id + qty) OR goal_id OR usual=true.")
    if forms[0] and not ("product_id" in args and "qty" in args):
        return Refusal("product_id and qty are both required for a single product.")
    return None


SOLO_WORDS = ("just me", "myself", "only me", "alone", "अकेला", "अकेले", "अकेली", "sirf main", "सिर्फ मैं", "सिर्फ़ मैं")


def _heard_number(text: str, n: int) -> bool:
    """Did this text say the number n, in digits or in words (English or Hindi)?"""
    from session_server.units.lexicon import DEVANAGARI_DIGITS, NUMBERS

    t = text.lower().translate(DEVANAGARI_DIGITS)
    if any(int(d) == n for d in re.findall(r"\d+", t)):
        return True
    if any(NUMBERS.get(w) == n for w in re.findall(r"[^\s,.!?।]+", t)):
        return True
    return n == 1 and any(w in t for w in SOLO_WORDS)


def people_guard(rt: Runtime, name: str, args: dict[str, Any]) -> Refusal | None:
    """The number of people must come from the shopper, not from a guess (it sets every quantity)."""
    if name != "plan_dish" or not args.get("people"):
        return None  # (no number yet: the dish is only being prepared)
    dish = " ".join(re.findall(r"[\w']+", args["dish"].lower()))
    if (dish, int(args["people"])) in rt.dish_confirmed:
        return None  # a repeat of a plan the shopper already heard (e.g. with items they have at home)
    if any(_heard_number(t, int(args["people"])) for t in rt.shopper_history[-3:]):
        return None
    return Refusal("The shopper has not told you the number of people. Ask 'how many people?', wait for their "
                   "answer, then call plan_dish with that number. Never guess it.")


def approval_guard(rt: Runtime, name: str, args: dict[str, Any]) -> Refusal | None:
    """Inferred items need the shopper's yes before they are added (FR-015)."""
    ask_first = (
        "NOT ADDED YET — this is not an availability problem; every item is in stock. The shopper "
        "has not clearly said yes to these items since you proposed them. Ask once, e.g. "
        "'क्या मैं ये सब डाल दूँ?', wait for a clear yes, then call add_to_cart again."
    )
    if name == "notify_family":
        if not args.get("shopper_consented") or not confirm.allows(rt, "family", []):
            return Refusal("The shopper has not agreed to tell their family. " + ask_first)
        return None
    if name != "add_to_cart":
        return None
    if "goal_id" in args:
        goal = rt.goals.get(args["goal_id"])
        if goal is None:
            return Refusal("Unknown goal_id; show the goal list first with show_products.")
        ids = [i.product_id for i in goal.items if not i.struck and i.product_id]
        if confirm.allows(rt, "goal", ids):
            return None
        log.info("approval_missing", goal=args["goal_id"], why=confirm.why_not(rt, "goal", ids))
        return Refusal(ask_first)
    if args.get("usual"):
        return None if confirm.allows(rt, "usual", []) else Refusal(ask_first)
    source = args.get("source", "named")
    pid = args["product_id"]
    if source != "named":
        return None if confirm.allows(rt, source, [pid]) else Refusal(ask_first)
    if confirm.pending_unconfirmed_for(rt, pid):
        return Refusal("This item was proposed by you (camera or usual order). " + ask_first)
    return None


GUARDS: list[Guard] = [problem_limit_guard, add_form_guard, approval_guard, people_guard]
