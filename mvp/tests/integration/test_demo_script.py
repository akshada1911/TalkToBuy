"""The whole demo script (quickstart rows 1–7) across real services, in process.

Drives the session server's tool handlers exactly as the Live model would, through the real UCP
client, against the real demo store. Checks the demo pass criteria in spec.md and quickstart.md:
exact quantities, the cake list, the ₹1,016 read-back, one-approval checkout, and the safety stop.
"""

import asyncio

import httpx
import pytest
from support import SoftAuthenticator

from demo_store.main import app as store_app
from demo_store.state import STATE
from session_server.adapters.ucp.client import UcpCommerce
from session_server.config import Settings
from session_server.core import confirm
from session_server.core.safety import detector, hold
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime

SHOP = "http://localhost:5173"


@pytest.fixture
async def env():
    async with store_app.router.lifespan_context(store_app):
        STATE.reset()
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=store_app), base_url="http://store.test")
        settings = Settings(_env_file=None, payment_timeout_s=5)
        rt = make_runtime(settings=settings)
        rt.commerce = UcpCommerce(settings, client=http)
        rt.shopper = await rt.commerce.shopper("u-ghanshyam")
        router = ToolRouter(rt, HANDLERS)
        calls = iter(range(1, 10_000))

        async def tool(name, args):
            cid = f"c{next(calls)}"
            await router.handle(ToolCall(cid, name, args))
            return rt.live.response_for(cid)

        yield rt, tool, http
        await http.aclose()


def ok(resp):
    assert resp is not None and resp["status"] == "ok", resp
    return resp["result"]


async def test_full_demo_script(env) -> None:
    rt, tool, http = env
    assert rt.shopper.address_form == "respectful_male"
    await ok_pace(tool)

    # Row 1: "दो लीटर दूध, पाव किलो टमाटर, और मेरा हमेशा वाला आटा"
    milk = ok(await tool("search_catalog", {"query": "दूध", "amount_phrase": "दो लीटर"}))
    plan = next(p for p in milk["pack_plans"] if p["recommended"])
    assert (plan["product_id"], plan["qty"]) == ("p-0001", 2)
    ok(await tool("add_to_cart", {"product_id": plan["product_id"], "qty": plan["qty"]}))

    tomato = ok(await tool("search_catalog", {"query": "टमाटर", "amount_phrase": "पाव किलो"}))
    plan = next(p for p in tomato["pack_plans"] if p["recommended"])
    assert (plan["product_id"], plan["qty"]) == ("p-0002", 1)  # 250 g for "paav kilo"
    ok(await tool("add_to_cart", {"product_id": plan["product_id"], "qty": plan["qty"]}))

    usual = ok(await tool("get_usual_order", {}))
    atta = next(line["product"]["id"] for line in usual["lines"] if line["product"]["category"] == "flours")
    assert atta == "p-0003"
    assert (await tool("add_to_cart", {"product_id": atta, "qty": 1, "source": "usual"}))["status"] == "refused"
    confirm.on_shopper_input(rt, "हाँ, वही डाल दो")
    ok(await tool("add_to_cart", {"product_id": atta, "qty": 1, "source": "usual"}))

    # Row 3: the empty biscuit packet on camera
    rt.camera_active = True
    biscuit = ok(await tool("search_catalog", {"query": "Parle-G biscuit"}))
    assert biscuit["products"][0]["id"] == "p-0004"
    assert (await tool("add_to_cart", {"product_id": "p-0004", "qty": 1, "source": "named"}))["status"] == "refused"
    confirm.on_shopper_input(rt, "haan")
    ok(await tool("add_to_cart", {"product_id": "p-0004", "qty": 1, "source": "camera"}))
    rt.camera_active = False

    # Row 4: small eggless chocolate cake; has sugar and baking soda; milk already in the cart
    needs = {"maida": "maida", "cocoa powder": "cocoa powder", "butter": "Amul butter",
             "condensed milk": "Milkmaid condensed milk", "baking powder": "baking powder",
             "cake tin": "7 inch cake tin"}
    items = [{"need": "sugar", "product_id": "p-0011", "qty": 1, "struck": True, "struck_reason": "on_hand"},
             {"need": "baking soda", "product_id": "p-0012", "qty": 1, "struck": True, "struck_reason": "on_hand"},
             {"need": "milk", "product_id": "p-0001", "qty": 1, "struck": False}]
    for need, query in needs.items():
        found = ok(await tool("search_catalog", {"query": query}))
        items.append({"need": need, "product_id": found["products"][0]["id"], "qty": 1, "struck": False})
    goal = ok(await tool("show_products", {"goal_list": {"goal_text": "small eggless chocolate cake",
                                                          "items": items}}))
    left_out = {i["need"]: i["struck_reason"] for i in goal["items"] if i["struck"]}
    assert left_out == {"sugar": "on_hand", "baking soda": "on_hand", "milk": "in_cart"}
    added = [i["product_id"] for i in goal["items"] if not i["struck"]]
    assert sorted(added) == ["p-0005", "p-0006", "p-0007", "p-0008", "p-0009", "p-0010"]
    confirm.on_shopper_input(rt, "हाँ")
    cart = ok(await tool("add_to_cart", {"goal_id": goal["goal_id"]}))
    assert cart["item_count"] == 10

    # Row 5: read-back is exactly 10 items, ₹1,016, 6–7 pm
    rb = ok(await tool("start_checkout", {"delivery_slot": "earliest"}))
    assert (rb["item_count"], rb["total"]) == (10, 1016)
    assert "₹1016" in rb["readback_hi"] and "कुल 10 सामान" in rb["readback_hi"]

    # Row 6: one fingerprint approval in the shop's payment step completes the order
    await tool("confirm_checkout", {"checkout_id": rb["checkout_id"]})
    request = rt.ui.of("payment_request")[-1]
    assert request["total"] == 1016
    mandate = await approve_with_fingerprint(http, rb["checkout_id"])
    rt.payment_future.set_result({"approved": True, "mandate": mandate})
    for _ in range(100):
        await asyncio.sleep(0.01)
        final = [r for _, n, r, _ in rt.live.tool_responses if n == "confirm_checkout"]
        if final:
            break
    result = final[-1]["result"]
    assert result["status"] == "completed" and result["order_id"]
    assert rt.ui.of("order")[-1]["order_id"] == result["order_id"]


async def ok_pace(tool) -> None:
    ok(await tool("set_pace", {"mode": "guided", "reason": "opening_question"}))


async def approve_with_fingerprint(http: httpx.AsyncClient, checkout_id: str) -> dict:
    """What apps/shop PaymentStep.tsx does: register once, assert with the checkout challenge, approve."""
    auth = SoftAuthenticator(rp_id="localhost", origin=SHOP)
    body = {"shopper_id": "u-ghanshyam"}
    reg = (await http.post("/payment/webauthn/register/options", json=body)).json()
    assert (await http.post("/payment/webauthn/register/verify",
                            json={**body, "credential": auth.register(reg)})).status_code == 200
    opts = await http.post("/payment/webauthn/assert/options", json={**body, "checkout_id": checkout_id})
    assert opts.status_code == 200, opts.text
    approve = await http.post("/payment/approve", json={**body, "checkout_id": checkout_id,
                                                         "credential": auth.assert_(opts.json())})
    assert approve.status_code == 200, approve.text
    data = approve.json()
    return {"checkout_mandate": data["checkout_mandate"], "payment_mandate": data["payment_mandate"]}


async def test_forged_mandate_is_rejected_by_store(env) -> None:
    rt, tool, _ = env
    ok(await tool("add_to_cart", {"product_id": "p-0001", "qty": 1}))
    rb = ok(await tool("start_checkout", {"delivery_slot": "earliest"}))
    await tool("confirm_checkout", {"checkout_id": rb["checkout_id"]})
    rt.payment_future.set_result({"approved": True, "mandate": {"checkout_mandate": "forged", "payment_mandate": "x"}})
    for _ in range(100):
        await asyncio.sleep(0.01)
        final = [r for _, n, r, _ in rt.live.tool_responses if n == "confirm_checkout"]
        if final:
            break
    assert final[-1]["result"]["status"] == "declined"
    assert not rt.ui.of("order")


async def test_safety_stop_shows_nothing_and_family_told_only_after_yes(env) -> None:
    rt, tool, http = env
    text = "मैं कल गिर गया और मेरा पैर सुन्न है, कोई दवाई मिलेगी?"
    await hold.apply(rt, await detector.evaluate(text, None))
    for name, args in [("search_catalog", {"query": "pain spray"}), ("show_products", {"ids": ["p-0001"]}),
                       ("add_to_cart", {"product_id": "p-0001", "qty": 1})]:
        assert (await tool(name, args))["status"] == "refused"
    assert not rt.ui.of("cards")
    msg = {"message": "Ghanshyam ji ne bataya ki woh gir gaye aur pair sunn hai.", "shopper_consented": True}
    assert (await tool("notify_family", msg))["status"] == "refused"
    confirm.on_shopper_input(rt, "हाँ, बता दो")
    result = ok(await tool("notify_family", msg))
    assert result["contact_name"].startswith("Rohit")
    feed = (await http.get("/demo/family/notifications", params={"shopper_id": "u-ghanshyam"})).json()
    assert feed and feed[-1]["message"] == msg["message"]
