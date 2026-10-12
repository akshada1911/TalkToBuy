"""T073: goal lists strike on-hand and in-cart items, and are added in one batch after a yes."""

from session_server.core import confirm
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.core.tools.cart import add_to_cart
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime

CAKE = {
    "goal_text": "small eggless chocolate cake",
    "items": [
        {"need": "sugar", "product_id": None, "struck": True, "struck_reason": "on_hand"},
        {"need": "baking soda", "product_id": None, "struck": True, "struck_reason": "on_hand"},
        {"need": "milk", "product_id": "p-0112", "qty": 1, "struck": False},
        {"need": "maida", "product_id": "p-0401", "qty": 1, "struck": False},
        {"need": "cocoa powder", "product_id": "p-2051", "qty": 1, "struck": False},
        {"need": "butter", "product_id": "p-0501", "qty": 1, "struck": False},
        {"need": "condensed milk", "product_id": "p-0601", "qty": 1, "struck": False},
        {"need": "baking powder", "product_id": "p-0701", "qty": 1, "struck": False},
        {"need": "cake tin", "product_id": "p-0801", "qty": 1, "struck": False},
    ],
}


async def test_cake_list_strikes_on_hand_and_cart_items_and_adds_six_at_once() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    await add_to_cart(rt, {"product_id": "p-0112", "qty": 2})  # milk already in the cart

    await router.handle(ToolCall("g", "show_products", {"goal_list": CAKE}))
    shown = rt.live.response_for("g")["result"]
    struck = {i["need"]: i["struck_reason"] for i in shown["items"] if i["struck"]}
    assert struck == {"sugar": "on_hand", "baking soda": "on_hand", "milk": "in_cart"}
    assert set(rt.session.on_hand) == {"sugar", "baking soda"}
    ui = rt.ui.of("goal_list")[-1]
    assert [i["struck"] for i in ui["items"]].count(True) == 3

    # Nothing is added before the yes.
    await router.handle(ToolCall("a1", "add_to_cart", {"goal_id": shown["goal_id"]}))
    assert rt.live.response_for("a1")["status"] == "refused"
    puts_before = len([c for c in rt.commerce.calls if c[0] == "put_cart"])

    confirm.on_shopper_input(rt, "हाँ, सब डाल दो")
    await router.handle(ToolCall("a2", "add_to_cart", {"goal_id": shown["goal_id"]}))
    cart = rt.live.response_for("a2")["result"]
    assert cart["item_count"] == 7  # milk + 6 goal items
    assert len([c for c in rt.commerce.calls if c[0] == "put_cart"]) == puts_before + 1  # one batch
    assert len(rt.ui.of("cards")[-1]["products"]) == 6
    assert rt.goals[shown["goal_id"]].status == "confirmed"


async def test_server_strikes_cart_items_even_if_model_forgets() -> None:
    rt = make_runtime()
    await add_to_cart(rt, {"product_id": "p-0401", "qty": 1})
    router = ToolRouter(rt, HANDLERS)
    goal = {"goal_text": "roti", "items": [{"need": "maida", "product_id": "p-0401", "qty": 1, "struck": False}]}
    await router.handle(ToolCall("g", "show_products", {"goal_list": goal}))
    item = rt.live.response_for("g")["result"]["items"][0]
    assert item["struck"] and item["struck_reason"] == "in_cart"


async def test_goal_items_known_on_hand_are_struck_in_later_goals() -> None:
    rt = make_runtime()
    rt.session.on_hand.append("sugar")
    router = ToolRouter(rt, HANDLERS)
    goal = {"goal_text": "kheer", "items": [{"need": "Sugar", "product_id": None, "struck": False}]}
    await router.handle(ToolCall("g", "show_products", {"goal_list": goal}))
    assert rt.live.response_for("g")["result"]["items"][0]["struck_reason"] == "on_hand"
