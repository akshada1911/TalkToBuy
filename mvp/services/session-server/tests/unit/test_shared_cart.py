"""One cart: filled by tapping in the shop or by voice. The assistant picks the shop's cart up, never
overwrites a tap, and learns when the cart is finished elsewhere. Without a shop cart, nothing changes."""

import asyncio

from session_server.core.cart import adopt_cart, sync_cart
from session_server.core.prompts import build_system_instruction, cart_note
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.core.tools.cart import add_to_cart
from session_server.core.tools.cancel import cancel_order
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime

MILK, TOMATO, BISCUIT = "p-0112", "p-0007", "p-0300"


async def _shop_cart(rt, lines):
    """A cart created in the shop (not by the assistant)."""
    view = await rt.commerce.create_cart(list(lines.items()))
    return view.id


def _tap(rt, cart_id, lines):
    """The shop changes the cart in the store behind the assistant's back."""
    rt.commerce.carts[cart_id]["lines"] = dict(lines)


async def test_the_assistant_picks_up_a_cart_filled_in_the_shop() -> None:
    rt = make_runtime()
    cart_id = await _shop_cart(rt, {MILK: 2, TOMATO: 1})
    assert await adopt_cart(rt, cart_id) is True
    assert rt.session.cart_ref == cart_id and rt.session.checkout_id == cart_id
    assert {l.product_id: l.qty for l in rt.cart.lines} == {MILK: 2, TOMATO: 1}
    assert MILK in rt.products and TOMATO in rt.products  # names known for the cards


async def test_an_unknown_or_finished_cart_is_not_picked_up() -> None:
    rt = make_runtime()
    assert await adopt_cart(rt, "chk_nope") is False
    done = await _shop_cart(rt, {MILK: 1})
    rt.commerce.carts[done]["status"] = "completed"
    assert await adopt_cart(rt, done) is False
    assert rt.session.cart_ref is None and rt.cart is None


async def test_voice_adds_go_into_the_shop_cart_without_losing_the_taps() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    cart_id = await _shop_cart(rt, {MILK: 1})
    await adopt_cart(rt, cart_id)
    # The shopper taps tomatoes in the shop while the assistant is running.
    _tap(rt, cart_id, {MILK: 1, TOMATO: 2})
    await router.handle(ToolCall("a", "add_to_cart", {"product_id": BISCUIT, "qty": 1, "source": "named"}))
    assert rt.live.response_for("a")["status"] == "ok"
    assert rt.commerce.carts[cart_id]["lines"] == {MILK: 1, TOMATO: 2, BISCUIT: 1}
    assert rt.session.cart_ref == cart_id  # still the one cart


async def test_a_tap_changes_the_cart_the_widget_sees_and_voids_a_read_back() -> None:
    rt = make_runtime()
    cart_id = await _shop_cart(rt, {MILK: 1})
    await adopt_cart(rt, cart_id)
    rt.session.checkout_ready = True
    waiting = asyncio.get_running_loop().create_future()
    rt.payment_future = waiting
    _tap(rt, cart_id, {MILK: 3})
    await sync_cart(rt)
    msg = rt.ui.of("cart")[-1]
    assert msg["cart_id"] == cart_id and msg["cart"]["lines"][0]["qty"] == 3
    assert rt.session.checkout_ready is False
    assert waiting.result() == {"cart_changed": True}


async def test_an_unchanged_cart_is_left_alone() -> None:
    rt = make_runtime()
    cart_id = await _shop_cart(rt, {MILK: 1})
    await adopt_cart(rt, cart_id)
    rt.session.checkout_ready = True
    await sync_cart(rt)
    assert rt.ui.of("cart") == [] and rt.session.checkout_ready is True
    await sync_cart(rt, push=True)  # the shop asked for a refresh: the widget gets it
    assert len(rt.ui.of("cart")) == 1


async def test_nothing_happens_without_a_cart() -> None:
    rt = make_runtime()
    await sync_cart(rt, push=True)
    assert rt.ui.of("cart") == [] and rt.session.cart_ref is None


async def test_a_cart_finished_in_the_shop_is_forgotten() -> None:
    rt = make_runtime()
    cart_id = await _shop_cart(rt, {MILK: 1})
    await adopt_cart(rt, cart_id)
    rt.commerce.carts[cart_id]["status"] = "completed"  # the shop placed the order itself
    await sync_cart(rt)
    assert rt.session.cart_ref is None and rt.cart is None
    last = rt.ui.of("cart")[-1]
    assert last["cart"]["item_count"] == 0 and last["cart_id"] is None


async def test_voice_cancel_empties_the_shop_cart_and_tells_the_shop() -> None:
    rt = make_runtime()
    cart_id = await _shop_cart(rt, {MILK: 1, TOMATO: 1})
    await adopt_cart(rt, cart_id)
    result = await cancel_order(rt, {})
    assert result["status"] == "cancelled" and result["removed_items"] == 2
    assert rt.commerce.carts[cart_id]["status"] == "canceled"
    last = rt.ui.of("cart")[-1]
    assert last["cart"]["item_count"] == 0 and last["cart_id"] is None


async def test_the_shop_can_ask_for_a_refresh_over_the_socket() -> None:
    from session_server.testing.fakes import FakeLive  # noqa: F401  (the runtime already has one)
    from tests.unit.test_session_flow import _setup  # type: ignore[import-not-found]

    rt, _, convo = _setup()
    cart_id = await _shop_cart(rt, {MILK: 1})
    await adopt_cart(rt, cart_id)
    _tap(rt, cart_id, {MILK: 2})
    await convo.on_client_json({"type": "cart_sync"})
    assert rt.ui.of("cart")[-1]["cart"]["lines"][0]["qty"] == 2


def test_the_model_is_told_about_items_already_in_the_cart() -> None:
    note = cart_note([("p-0112", "Toned Milk 1 L", 2)], 108)
    assert "2 × Toned Milk 1 L (p-0112)" in note and "₹108" in note and "do not add them again" in note
    from session_server.models.domain import Shopper

    shopper = Shopper(id="u", display_name="Ghanshyam ji", language="hi", address_form="respectful_male")
    with_cart = build_system_instruction(shopper, "guided", cart=note)
    without = build_system_instruction(shopper, "guided")
    assert with_cart.startswith(without) and note in with_cart
    assert "p-0112" not in without  # no shop cart: the instruction is exactly as before


async def test_a_cart_the_shop_starts_after_the_chat_began_is_adopted_and_can_be_cleared() -> None:
    """Open the assistant first, then tap items in the shop: 'clear the cart' must clear THOSE items."""
    from session_server.adapters.memory.state import MemoryState
    from session_server.core.session import ConversationSession
    from session_server.core.tool_router import ToolRouter
    from session_server.core.tools import HANDLERS
    from session_server.ports.live import ToolCall

    rt = make_runtime()
    convo = ConversationSession(rt, ToolRouter(rt, HANDLERS), MemoryState())
    assert rt.session.cart_ref is None  # the chat began with no cart
    shop_cart = await rt.commerce.create_cart({"p-0112": 2})  # the shop created this one by tapping
    await convo.on_client_json({"type": "cart_sync", "cart_id": shop_cart.id})
    assert rt.session.cart_ref == shop_cart.id and rt.cart is not None and rt.cart.item_count == 1
    assert rt.ui.of("cart")[-1]["cart_id"] == shop_cart.id

    await ToolRouter(rt, HANDLERS).handle(ToolCall("c1", "cancel_order", {}))
    assert rt.live.response_for("c1")["result"]["status"] == "cancelled"
    assert rt.commerce.carts[shop_cart.id]["status"] == "canceled"
    assert rt.ui.of("cart")[-1]["cart"]["item_count"] == 0
