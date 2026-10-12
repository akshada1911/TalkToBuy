"""Cart helpers. The cart IS the store's checkout session; an edit never cancels it (F3)."""

from typing import Any

from session_server.core.runtime import Runtime
from session_server.core.ui import cards_msg, cart_msg, model_cart
from session_server.ports.commerce import CheckoutView


def current_lines(rt: Runtime) -> dict[str, int]:
    return {line.product_id: line.qty for line in rt.cart.lines} if rt.cart else {}


async def invalidate_checkout(rt: Runtime) -> None:
    """Any cart edit voids a read-back: a pending payment resolves as cart_changed."""
    rt.session.checkout_ready = False
    if rt.payment_future is not None and not rt.payment_future.done():
        rt.payment_future.set_result({"cart_changed": True})


async def apply_lines(rt: Runtime, lines: dict[str, int], added: list[str]) -> CheckoutView:
    """Replace the cart's lines (clearing any slot), then push cart + added cards to the UI."""
    items = [(pid, qty) for pid, qty in lines.items() if qty > 0]
    if rt.session.cart_ref is None:
        view = await rt.commerce.create_cart(items)
        rt.session.cart_ref = view.id
        rt.session.checkout_id = view.id
    else:
        view = await rt.commerce.put_cart(rt.session.cart_ref, items, None)
    await invalidate_checkout(rt)
    rt.cart = view
    await rt.ensure_products([line.product_id for line in view.lines] + added)
    await rt.ui.send_json(cart_msg(view, rt.products))
    if added:
        await rt.ui.send_json(cards_msg([rt.products[p] for p in added if p in rt.products], "added"))
    return view


def request_key(args: dict[str, Any]) -> tuple:
    """Identity of an add_to_cart request, for de-duplication within one shopper request."""
    if "goal_id" in args:
        return ("goal", args["goal_id"])
    if args.get("usual"):
        return ("usual",)
    return ("item", args.get("product_id"), args.get("qty"), args.get("source", "named"))


def duplicate_add(rt: Runtime, args: dict[str, Any]) -> dict[str, Any] | None:
    """If this exact add already ran for the current shopper request, the result to return
    instead of adding again (the model sometimes repeats tool calls); else None."""
    if request_key(args) in rt.turn_adds and rt.cart is not None:
        return {**model_cart(rt.cart, rt.products),
                "note": "Already added for this request — not added twice. Do not call add_to_cart "
                        "again for it; continue with the next item."}
    return None
