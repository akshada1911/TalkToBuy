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


async def test_bad_goal_items_are_flagged_and_never_sent_to_the_store() -> None:
    """Live rehearsal regression: one bad line made the store reject the whole batch."""
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    goal = {"goal_text": "cake", "items": [
        {"need": "maida", "product_id": "p-0401", "qty": 1, "struck": False},
        {"need": "vanilla", "product_id": "p-9999", "qty": 1, "struck": False},   # hallucinated id
        {"need": "paneer", "product_id": "p-0999", "qty": 1, "struck": False},    # out of stock
    ]}
    await router.handle(ToolCall("g", "show_products", {"goal_list": goal}))
    shown = rt.live.response_for("g")["result"]
    assert len(shown["problems"]) == 2 and "fix_first" in shown
    confirm.on_shopper_input(rt, "हाँ")
    await router.handle(ToolCall("a", "add_to_cart", {"goal_id": shown["goal_id"]}))
    cart = rt.live.response_for("a")["result"]
    assert [line["product_id"] for line in cart["lines"]] == ["p-0401"]


async def test_goal_response_reports_cart_items_missing_from_the_list() -> None:
    rt = make_runtime()
    await add_to_cart(rt, {"product_id": "p-0112", "qty": 2})
    router = ToolRouter(rt, HANDLERS)
    no_milk = {**CAKE, "items": [i for i in CAKE["items"] if i["need"] != "milk"]}
    await router.handle(ToolCall("g", "show_products", {"goal_list": no_milk}))
    result = rt.live.response_for("g")["result"]
    assert result["already_in_cart"] == [{"product_id": "p-0112", "name": "Toned Milk 1 L"}]
    assert "in_cart" in result["check"]


async def test_reshowing_the_list_after_yes_keeps_the_yes() -> None:
    """Live rehearsal regression: the model re-called show_products right after 'हाँ'."""
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    await router.handle(ToolCall("g1", "show_products", {"goal_list": CAKE}))
    confirm.on_shopper_input(rt, "हाँ, सब डाल दो")
    await router.handle(ToolCall("g2", "show_products", {"goal_list": CAKE}))
    goal_id = rt.live.response_for("g2")["result"]["goal_id"]
    await router.handle(ToolCall("a", "add_to_cart", {"goal_id": goal_id}))
    assert rt.live.response_for("a")["status"] == "ok"


async def test_proposing_new_items_after_yes_needs_a_new_yes() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    small = {"goal_text": "x", "items": [{"need": "maida", "product_id": "p-0401", "qty": 1, "struck": False}]}
    await router.handle(ToolCall("g1", "show_products", {"goal_list": small}))
    confirm.on_shopper_input(rt, "haan")
    await router.handle(ToolCall("g2", "show_products", {"goal_list": CAKE}))  # more items than agreed
    goal_id = rt.live.response_for("g2")["result"]["goal_id"]
    await router.handle(ToolCall("a", "add_to_cart", {"goal_id": goal_id}))
    assert rt.live.response_for("a")["status"] == "refused"


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
