"""cancel_order: the shopper says "cancel my order". Empties the cart and cancels the checkout."""

from typing import Any

from session_server.core.runtime import Runtime
from session_server.core.ui import cart_msg
from session_server.ports.commerce import CheckoutView, CommerceError


async def cancel_order(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    cart_ref = rt.session.cart_ref
    removed = len(rt.cart.lines) if rt.cart else 0
    if cart_ref is None and removed == 0:
        return {"status": "nothing_to_cancel",
                "instruction": ("There is nothing in the cart and no order open. Tell the shopper so; "
                                "an order that was already placed cannot be cancelled here.")}
    # Close an open payment step first so nothing can be approved for the cancelled order.
    if rt.payment_future is not None and not rt.payment_future.done():
        rt.payment_future.set_result({"cancelled": True})
    if cart_ref is not None:
        try:
            await rt.commerce.cancel(cart_ref)
        except CommerceError:
            pass  # already closed on the store side: the local state is cleared either way
    rt.session.cart_ref = None
    rt.session.checkout_id = None
    rt.session.checkout_ready = False
    rt.address = None
    rt.cart = None
    rt.line_sources.clear()
    rt.goals.clear()
    empty = CheckoutView(id="", status="incomplete", lines=(), item_count=0, total_minor=0)
    await rt.ui.send_json(cart_msg(empty, rt.products))
    return {"status": "cancelled", "removed_items": removed,
            "instruction": ("Tell the shopper in a few words that the order is cancelled and the cart "
                            "is empty, then ask if they would like to start again.")}
