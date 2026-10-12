"""get_usual_order (T052): proposes the last order; never adds anything by itself (FR-015)."""

from typing import Any

from session_server.core import confirm
from session_server.core.runtime import Runtime
from session_server.core.ui import model_product


async def get_usual_order(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    order = await rt.commerce.last_order(rt.session.shopper_id)
    if order is None or not order.lines:
        return {"order_id": None, "lines": [], "note": "No previous order found."}
    rt.usual = order
    rt.remember([p for p, _ in order.lines])
    confirm.arm(rt, "usual", [p.id for p, _ in order.lines])
    return {
        "order_id": order.order_id,
        "lines": [{"product": model_product(p), "qty": qty} for p, qty in order.lines],
        "instruction": "Name the item(s) and ask before adding. Add one item with "
                       "add_to_cart(product_id, qty, source='usual'), or all with usual=true.",
    }
