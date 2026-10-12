"""T062: checkout can only complete with a payment-step mandate; edits never lose the cart."""

import asyncio

import pytest

from session_server.core.tool_router import ToolError, ToolRouter
from session_server.core.tools import HANDLERS
from session_server.core.tools.cart import add_to_cart, update_cart
from session_server.core.tools.checkout import confirm_checkout, start_checkout
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime

MANDATE = {"checkout_mandate": "valid-test-mandate", "payment_mandate": "pm"}


async def _cart(rt):
    await add_to_cart(rt, {"product_id": "p-0112", "qty": 2})
    await add_to_cart(rt, {"product_id": "p-0007", "qty": 1})


async def test_start_checkout_refuses_empty_cart() -> None:
    rt = make_runtime()
    with pytest.raises(ToolError, match="empty"):
        await start_checkout(rt, {"delivery_slot": "earliest"})


async def test_readback_uses_store_numbers_exactly() -> None:
    rt = make_runtime()
    await _cart(rt)
    result = await start_checkout(rt, {"delivery_slot": "earliest"})
    # 2 × ₹54 + ₹10 = ₹118, 2 distinct products, slot from the store
    assert result["item_count"] == 2 and result["total"] == 118
    assert "कुल 2 सामान" in result["readback_hi"] and "₹118" in result["readback_hi"]
    assert "शाम 6 से 7 बजे" in result["readback_hi"]
    readback = rt.ui.of("readback")[-1]
    assert readback["total"] == 118 and readback["text_hi"] == result["readback_hi"]


async def test_confirm_requires_start_checkout_first() -> None:
    rt = make_runtime()
    await _cart(rt)
    with pytest.raises(ToolError, match="start_checkout"):
        await confirm_checkout(rt, {"checkout_id": rt.session.cart_ref})


async def test_spoken_yes_alone_never_completes() -> None:
    rt = make_runtime()
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    deferred = await confirm_checkout(rt, {"checkout_id": rb["checkout_id"]})
    assert rt.ui.of("payment_request")
    # The shopper says "haan, pay karo" but never approves in the payment step: times out.
    result = await deferred.awaitable
    assert result["status"] == "timed_out"
    assert not [c for c in rt.commerce.calls if c[0] == "complete"]
    assert rt.commerce.carts[rt.session.cart_ref]["status"] == "incomplete"


async def test_completes_only_with_approved_mandate() -> None:
    rt = make_runtime()
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    deferred = await confirm_checkout(rt, {"checkout_id": rb["checkout_id"]})
    rt.payment_future.set_result({"approved": True, "mandate": MANDATE})
    result = await deferred.awaitable
    assert result["status"] == "completed" and result["order_id"]
    assert rt.ui.of("order")[-1]["order_id"] == result["order_id"]
    assert rt.session.cart_ref is None


async def test_declined_payment_keeps_cart() -> None:
    rt = make_runtime()
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    cart_id = rb["checkout_id"]
    deferred = await confirm_checkout(rt, {"checkout_id": cart_id})
    rt.payment_future.set_result({"approved": False, "mandate": None})
    assert (await deferred.awaitable)["status"] == "declined"
    cart = rt.commerce.carts[cart_id]
    assert cart["status"] == "incomplete" and cart["lines"] == {"p-0112": 2, "p-0007": 1}


async def test_cart_edit_during_payment_returns_cart_changed_and_keeps_lines() -> None:
    rt = make_runtime()
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    deferred = await confirm_checkout(rt, {"checkout_id": rb["checkout_id"]})
    await update_cart(rt, {"product_id": "p-0007", "qty": 2})
    assert (await deferred.awaitable)["status"] == "cart_changed"
    cart = rt.commerce.carts[rb["checkout_id"]]
    assert cart["status"] == "incomplete"  # never canceled
    assert cart["lines"] == {"p-0112": 2, "p-0007": 2}
    assert rt.session.checkout_ready is False


async def test_no_to_readback_leaves_cart_intact() -> None:
    rt = make_runtime()
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    # Shopper says "nahi, ek aur cheez" → model edits the cart instead of confirming.
    await add_to_cart(rt, {"product_id": "p-0201", "qty": 1})
    cart = rt.commerce.carts[rb["checkout_id"]]
    assert cart["status"] == "incomplete" and len(cart["lines"]) == 3


async def test_speech_during_payment_does_not_duplicate_confirm() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    await _cart(rt)
    rb = await start_checkout(rt, {"delivery_slot": "earliest"})
    await router.handle(ToolCall("c1", "confirm_checkout", {"checkout_id": rb["checkout_id"]}))
    assert rt.live.response_for("c1") is None  # still open (non-blocking)
    await router.handle(ToolCall("c2", "confirm_checkout", {"checkout_id": rb["checkout_id"]}))
    second = rt.live.response_for("c2")
    assert second["status"] == "error" and "already open" in second["message"]
    rt.payment_future.set_result({"approved": True, "mandate": MANDATE})
    for _ in range(20):
        await asyncio.sleep(0)
        if rt.live.response_for("c1"):
            break
    first = rt.live.response_for("c1")
    assert first["result"]["status"] == "completed"
    assert [s for cid, _, _, s in rt.live.tool_responses if cid == "c1"] == ["INTERRUPT"]
    assert len([c for c in rt.commerce.calls if c[0] == "complete"]) == 1


async def test_out_of_stock_at_checkout_is_reported() -> None:
    rt = make_runtime()
    await _cart(rt)
    rt.commerce.products["p-0007"] = rt.commerce.products["p-0007"].model_copy(update={"in_stock": False})
    with pytest.raises(ToolError, match="out of stock"):
        await start_checkout(rt, {"delivery_slot": "earliest"})
