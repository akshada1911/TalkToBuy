"""Goal-to-list state (T074, FR-022–FR-026).

The model plans the list; the server keeps it honest: items already in the cart or stated as
on hand are struck through with a reason, at most two questions are allowed (prompt-level), and
the whole list is added at once only after the shopper's yes.
"""

from typing import Any

from session_server.core import confirm
from session_server.core.cart import current_lines
from session_server.core.runtime import Runtime
from session_server.core.ui import ui_product
from session_server.models.domain import GoalItem, GoalList
from session_server.models.messages import GoalListMsg, UiGoalItem


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


# A "veg cake" is a vegetarian (eggless) cake, not a cake made of vegetables. Fresh produce does not
# belong in a baking goal unless the recipe really uses it (carrot cake, banana bread, ...).
_BAKING_WORDS = ("cake", "केक", "bake", "baking", "बेक", "cookie", "कुकी", "muffin", "मफिन",
                 "brownie", "ब्राउनी", "cupcake", "बिस्कुट")
_BAKING_PRODUCE_OK = ("carrot", "गाजर", "banana", "केला", "केले", "pumpkin", "कद्दू", "beetroot",
                      "चुकंदर", "zucchini", "apple", "सेब", "lemon", "नींबू", "orange", "संतरा",
                      "pineapple", "अनानास", "mango", "आम", "coconut", "नारियल", "strawberry",
                      "berry", "dates", "खजूर", "raisin", "किशमिश")


def _is_baking(goal_text: str) -> bool:
    t = goal_text.lower()
    return any(w in t for w in _BAKING_WORDS)


def _produce_misfit(goal_text: str, need: str, category: str | None) -> bool:
    if category != "produce" or not _is_baking(goal_text):
        return False
    t = f"{goal_text} {need}".lower()
    return not any(w in t for w in _BAKING_PRODUCE_OK)


async def build(rt: Runtime, goal_args: dict[str, Any]) -> GoalList:
    in_cart = set(current_lines(rt))
    on_hand = {_norm(x) for x in rt.session.on_hand}
    items: list[GoalItem] = []
    for raw in goal_args["items"]:
        need = raw["need"]
        pid = raw.get("product_id")
        struck = bool(raw.get("struck"))
        reason = raw.get("struck_reason")
        if struck and reason == "on_hand" and _norm(need) not in on_hand:
            rt.session.on_hand.append(need)
            on_hand.add(_norm(need))
        if not struck and pid and pid in in_cart:
            struck, reason = True, "in_cart"
        if not struck and _norm(need) in on_hand:
            struck, reason = True, "on_hand"
        if struck and reason is None:
            reason = "in_cart" if pid in in_cart else "on_hand"
        items.append(GoalItem(need=need, product_id=pid, qty=raw.get("qty") or 1, struck=struck,
                              struck_reason=reason if struck else None))

    # The store rejects a whole batch if one line is bad, so vet every proposed product now:
    # unknown IDs are cleared and out-of-stock items flagged, and the model is told to fix them.
    await rt.ensure_products([i.product_id for i in items if i.product_id])
    problems: list[str] = []
    unrelated: list[str] = []
    for item in list(items):
        product = rt.products.get(item.product_id) if item.product_id else None
        if not item.struck and product and _produce_misfit(goal_args["goal_text"], item.need, product.category):
            items.remove(item)
            unrelated.append(item.need)
    for item in items:
        if item.struck or not item.product_id:
            continue
        product = rt.products.get(item.product_id)
        if product is None:
            problems.append(f"'{item.need}': unknown product_id {item.product_id}; search_catalog for it again")
            item.product_id = None
        elif not product.in_stock:
            problems.append(f"'{item.need}': {product.name} is out of stock; offer an in-stock alternative")
            item.product_id = None

    goal = GoalList(goal_id=f"g{len(rt.goals) + 1}", goal_text=goal_args["goal_text"],
                    questions_asked=0, items=items, status="proposed")
    rt.goals[goal.goal_id] = goal
    rt.goal_problems[goal.goal_id] = problems
    if unrelated:
        rt.goal_removed[goal.goal_id] = unrelated
    confirm.arm(rt, "goal", [i.product_id for i in items if not i.struck and i.product_id])
    await rt.ui.send_json(GoalListMsg(
        type="goal_list", goal_id=goal.goal_id, goal_text=goal.goal_text,
        items=[
            UiGoalItem(
                need=i.need,
                product=ui_product(rt.products[i.product_id]) if i.product_id in rt.products else None,
                qty=i.qty, struck=i.struck, struck_reason=i.struck_reason,
            )
            for i in items
        ],
    ))
    return goal


def confirm_goal(rt: Runtime, goal_id: str) -> list[tuple[str, int]]:
    goal = rt.goals[goal_id]
    goal.status = "confirmed"
    return [(i.product_id, i.qty or 1) for i in goal.items if not i.struck and i.product_id]


def model_goal(goal: GoalList, problems: list[str] | None = None,
               removed: list[str] | None = None) -> dict[str, Any]:
    out = {
        "goal_id": goal.goal_id,
        "items": [i.model_dump() for i in goal.items],
        "left_out": [i.need for i in goal.items if i.struck],
    }
    if removed:
        out["removed_as_unrelated"] = removed
        out["removed_note"] = ("These do not belong in this dish and were taken off the list. Tell "
                               "the shopper they were left out and why; do not add them back.")
    if problems:
        out["problems"] = problems
        out["fix_first"] = ("Fix these before asking to add: search again and call show_products "
                            "with corrected product_ids. Items without a product are not added.")
    return out
