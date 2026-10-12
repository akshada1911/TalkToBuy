"""Server-side tool guards. They run before every handler and are what the tests rely on —
the prompt alone is never trusted for approval or safety (Principles I and II)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from session_server.core import confirm
from session_server.core.runtime import Runtime


@dataclass(frozen=True)
class Refusal:
    message: str
    retryable: bool = True


Guard = Callable[[Runtime, str, dict[str, Any]], Refusal | None]

SAFETY_BLOCKED = {"search_catalog", "show_products", "add_to_cart", "start_checkout", "confirm_checkout"}
SAFETY_REFUSAL = (
    "Refused: a warning sign was reported, so no products may be shown, added or bought now. "
    "Gently suggest seeing a doctor, and offer to tell their family member in the app."
)


def safety_guard(rt: Runtime, name: str, args: dict[str, Any]) -> Refusal | None:
    if rt.session.safety_hold and name in SAFETY_BLOCKED:
        return Refusal(SAFETY_REFUSAL, retryable=False)
    return None


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
        return None if confirm.allows(rt, "goal", ids) else Refusal(ask_first)
    if args.get("usual"):
        return None if confirm.allows(rt, "usual", []) else Refusal(ask_first)
    source = args.get("source", "named")
    pid = args["product_id"]
    if source != "named":
        return None if confirm.allows(rt, source, [pid]) else Refusal(ask_first)
    if confirm.pending_unconfirmed_for(rt, pid):
        return Refusal("This item was proposed by you (camera or usual order). " + ask_first)
    return None


GUARDS: list[Guard] = [safety_guard, problem_limit_guard, add_form_guard, approval_guard]
