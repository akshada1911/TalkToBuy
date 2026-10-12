"""show_products, add_to_cart, update_cart (T051, T076, T096)."""

from typing import Any

from session_server.core import confirm, goal
from session_server.core.cart import apply_lines, current_lines, request_key
from session_server.core.runtime import Runtime
from session_server.core.tool_router import ToolError
from session_server.core.ui import cards_msg, model_cart
from session_server.logging import get_logger
from session_server.ports.commerce import CommerceError

log = get_logger(__name__)


async def show_products(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    if args.get("goal_list"):
        g = await goal.build(rt, args["goal_list"])
        listed = {i.product_id for i in g.items if i.product_id}
        in_cart_not_listed = [
            {"product_id": pid, "name": rt.products[pid].name}
            for pid in current_lines(rt) if pid not in listed and pid in rt.products
        ]
        result = {"ok": True, **goal.model_goal(g, rt.goal_problems.get(g.goal_id)),
                  "instruction": "Read it out, say what was left out and why, ask once; on yes "
                                 "add_to_cart(goal_id)."}
        if in_cart_not_listed:
            result["already_in_cart"] = in_cart_not_listed
            result["check"] = ("If the goal needs any already_in_cart item (e.g. milk for a cake), "
                               "show the list again with it struck_reason 'in_cart'.")
        return result
    ids = args.get("ids", [])
    await rt.ensure_products(ids)
    shown = [rt.products[i] for i in ids if i in rt.products]
    await rt.ui.send_json(cards_msg(shown, "suggest"))
    return {"ok": True, "goal_id": None, "shown": [p.id for p in shown]}


async def _put(rt: Runtime, lines: dict[str, int], added: list[str]) -> dict[str, Any]:
    try:
        view = await apply_lines(rt, lines, added)
    except CommerceError as exc:
        log.warning("store_rejected_cart", code=exc.code, message=exc.message, lines=lines)
        raise ToolError(f"Store refused the cart change: {exc.message}", retryable=False) from exc
    return model_cart(view, rt.products)


async def add_to_cart(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    key = request_key(args)
    lines = current_lines(rt)
    if "goal_id" in args:
        additions = goal.confirm_goal(rt, args["goal_id"])
        source = "goal"
    elif args.get("usual"):
        if rt.usual is None:
            raise ToolError("Call get_usual_order first.")
        additions = [(p.id, qty) for p, qty in rt.usual.lines]
        source = "usual"
    else:
        await rt.ensure_products([args["product_id"]])
        product = rt.products.get(args["product_id"])
        if product is None:
            raise ToolError(f"Unknown product {args['product_id']}; search the catalogue first.")
        if not product.in_stock:
            raise ToolError(f"{product.name} is out of stock. Offer the closest in-stock "
                            f"alternative and say why.", retryable=False)
        additions = [(product.id, args["qty"])]
        source = args.get("source", "named")

    for pid, qty in additions:
        lines[pid] = lines.get(pid, 0) + qty
        rt.line_sources[pid] = source
    if source != "named":
        confirm.consume(rt)
    result = await _put(rt, lines, [pid for pid, _ in additions])
    rt.turn_adds.add(key)
    return result


async def update_cart(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    lines = current_lines(rt)
    pid, qty = args["product_id"], args["qty"]
    if pid not in lines:
        raise ToolError(f"{pid} is not in the cart; use add_to_cart to add it.")
    if qty == 0:
        lines.pop(pid)
        rt.line_sources.pop(pid, None)
    else:
        lines[pid] = qty
    return await _put(rt, lines, [])
