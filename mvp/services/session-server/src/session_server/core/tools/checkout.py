"""start_checkout and confirm_checkout (T067, FR-018–FR-021).

The read-back sentence is built here from the store's own numbers, never by the model. An order
is placed only with a mandate from the shop's payment step; a spoken yes is never enough.
confirm_checkout is non-blocking: the call stays open while the shopper approves (research R2).
"""

import asyncio
from typing import Any

from session_server.core.cart import current_lines
from session_server.core.runtime import Runtime
from session_server.core.tool_router import Deferred, ToolError
from session_server.core.ui import cart_msg, rupees, ui_delivery
from session_server.models.messages import OrderMsg, PaymentRequestMsg, ReadbackMsg
from session_server.ports.commerce import CheckoutView, CommerceError, Slot


def _readback(item_count: int, total: int, slot: Slot) -> tuple[str, str]:
    hi = (f"आपके कार्ट में कुल {item_count} सामान हैं, कुल ₹{total}। "
          f"डिलीवरी {slot.label_hi} के बीच होगी। क्या मैं ऑर्डर कर दूँ?")
    en = f"{item_count} items, ₹{total}, delivery {slot.label_en}. Shall I place the order?"
    return hi, en


async def _revert_to_incomplete(rt: Runtime) -> None:
    rt.session.checkout_ready = False
    if rt.session.cart_ref and rt.cart:
        rt.cart = await rt.commerce.put_cart(rt.session.cart_ref, list(current_lines(rt).items()), None)


async def start_checkout(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    if not rt.cart or not rt.cart.lines or rt.session.cart_ref is None:
        raise ToolError("The cart is empty; there is nothing to check out.", retryable=False)
    try:
        view = await rt.commerce.put_cart(
            rt.session.cart_ref, list(current_lines(rt).items()), args["delivery_slot"]
        )
    except CommerceError as exc:
        if exc.code == "OUT_OF_STOCK":
            raise ToolError(f"{exc.message} Tell the shopper, offer the closest in-stock "
                            f"alternative, then call start_checkout again.", retryable=False) from exc
        raise ToolError(f"Checkout could not start: {exc.message}") from exc
    if view.status != "ready_for_complete" or view.slot is None:
        raise ToolError("The store did not accept the delivery slot; try 'earliest'.")
    rt.cart = view
    rt.session.checkout_ready = True
    rt.session.checkout_id = view.id
    total = rupees(view.total_minor)
    hi, en = _readback(view.item_count, total, view.slot)
    await rt.ui.send_json(ReadbackMsg(
        type="readback", checkout_id=view.id, item_count=view.item_count, total=total,
        delivery=ui_delivery(view.slot), text_hi=hi, text_en=en,
    ))
    return {
        "checkout_id": view.id, "item_count": view.item_count, "total": total, "currency": "INR",
        "delivery": {"id": view.slot.id, "label_hi": view.slot.label_hi, "label_en": view.slot.label_en},
        "readback_hi": hi, "readback_en": en,
        "instruction": "Say readback_hi exactly as written, then wait for a clear yes before "
                       "calling confirm_checkout.",
    }


async def confirm_checkout(rt: Runtime, args: dict[str, Any]) -> Deferred:
    if not rt.session.checkout_ready or args["checkout_id"] != rt.session.checkout_id:
        raise ToolError("Call start_checkout and read the total back first.")
    if rt.payment_future is not None and not rt.payment_future.done():
        raise ToolError("The payment step is already open; wait for the shopper to approve it.",
                        retryable=False)
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    rt.payment_future = future
    view = rt.cart
    assert view is not None and view.slot is not None
    await rt.ui.send_json(PaymentRequestMsg(
        type="payment_request", checkout_id=view.id, item_count=view.item_count,
        total=rupees(view.total_minor), currency="INR", delivery=ui_delivery(view.slot),
    ))
    return Deferred(_await_payment(rt, future), scheduling="INTERRUPT")


async def _await_payment(rt: Runtime, future: asyncio.Future) -> dict[str, Any]:
    try:
        outcome = await asyncio.wait_for(future, timeout=rt.settings.payment_timeout_s)
    except TimeoutError:
        await _revert_to_incomplete(rt)
        return {"status": "timed_out", "instruction": "Ask whether they want to try the payment again."}
    finally:
        rt.payment_future = None

    if outcome.get("cart_changed"):
        return {"status": "cart_changed",
                "instruction": "The cart changed. Call start_checkout again and read the new total back."}
    if not outcome.get("approved") or not outcome.get("mandate"):
        await _revert_to_incomplete(rt)
        return {"status": "declined", "instruction": "No order was placed. Ask what they would like to do."}

    try:
        done = await rt.commerce.complete(rt.session.cart_ref, outcome["mandate"])
    except CommerceError as exc:
        await _revert_to_incomplete(rt)
        return {"status": "declined", "reason": exc.code,
                "instruction": "The approval could not be verified; no order was placed."}

    slot = done.slot or (rt.cart.slot if rt.cart else None)
    assert slot is not None
    await rt.ui.send_json(OrderMsg(type="order", order_id=done.order_id or "", delivery=ui_delivery(slot)))
    rt.session.cart_ref = None
    rt.session.checkout_id = None
    rt.session.checkout_ready = False
    rt.cart = None
    rt.line_sources.clear()
    empty = CheckoutView(id="", status="incomplete", lines=(), item_count=0, total_minor=0)
    await rt.ui.send_json(cart_msg(empty, rt.products))
    return {"status": "completed", "order_id": done.order_id,
            "delivery": {"id": slot.id, "label_hi": slot.label_hi, "label_en": slot.label_en},
            "instruction": "Thank the shopper and say the order confirmation and delivery time."}
