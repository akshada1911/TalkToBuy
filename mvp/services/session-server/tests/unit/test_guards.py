"""T058: inferred items need a server-observed yes (FR-015). Arming, confirming, negatives, expiry."""

import pytest

from session_server.core import confirm
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime


class Clock:
    def __init__(self) -> None:
        self.t = 1_000.0

    def __call__(self) -> float:
        return self.t


async def _call(router, name, args, cid="c"):
    await router.handle(ToolCall(cid, name, args))
    return router.rt.live.response_for(cid)


@pytest.mark.parametrize("text", ["हाँ", "हां जी", "haan daal do", "ठीक है", "yes please", "ok"])
def test_affirmatives(text) -> None:
    assert confirm.is_affirmative(text)


@pytest.mark.parametrize("text", ["नहीं", "nahi chahiye", "no", "rehne do", "मत डालो", "haan nahi"])
def test_negatives_are_not_affirmative(text) -> None:
    assert not confirm.is_affirmative(text)


async def test_usual_item_refused_until_yes_then_allowed_once() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    await _call(router, "get_usual_order", {}, "u")
    add = {"product_id": "p-0201", "qty": 1, "source": "usual"}
    assert (await _call(router, "add_to_cart", add, "a1"))["status"] == "refused"
    confirm.on_shopper_input(rt, "हाँ, वही डाल दो")
    assert (await _call(router, "add_to_cart", add, "a2"))["status"] == "ok"
    # consumed: a second add of an inferred item needs a fresh yes
    assert (await _call(router, "add_to_cart", add, "a3"))["status"] == "refused"


async def test_named_source_cannot_bypass_pending_camera_item() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    rt.camera_active = True
    await _call(router, "search_catalog", {"query": "biscuit"}, "s")
    res = await _call(router, "add_to_cart", {"product_id": "p-0300", "qty": 1, "source": "named"}, "a")
    assert res["status"] == "refused"
    confirm.on_shopper_input(rt, "haan")
    res = await _call(router, "add_to_cart", {"product_id": "p-0300", "qty": 1, "source": "camera"}, "b")
    assert res["status"] == "ok"


async def test_negative_clears_confirmation() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    await _call(router, "get_usual_order", {}, "u")
    confirm.on_shopper_input(rt, "nahi, rehne do")
    assert rt.session.pending_confirmation is None
    res = await _call(router, "add_to_cart", {"usual": True}, "a")
    assert res["status"] == "refused"


async def test_confirmation_expires_after_60_seconds() -> None:
    clock = Clock()
    rt = make_runtime(clock=clock)
    router = ToolRouter(rt, HANDLERS)
    await _call(router, "get_usual_order", {}, "u")
    confirm.on_shopper_input(rt, "हाँ")
    clock.t += 61
    res = await _call(router, "add_to_cart", {"usual": True}, "a")
    assert res["status"] == "refused"


async def test_named_items_are_added_without_asking() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    res = await _call(router, "add_to_cart", {"product_id": "p-0112", "qty": 2, "source": "named"}, "a")
    assert res["status"] == "ok" and res["result"]["item_count"] == 1
    # card pushed to the UI before the model got the result
    assert rt.ui.of("cards")[-1]["products"][0]["id"] == "p-0112"


async def test_add_form_must_be_exactly_one() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    res = await _call(router, "add_to_cart", {"product_id": "p-0112", "qty": 1, "usual": True}, "a")
    assert res["status"] == "refused" and "exactly one form" in res["message"]


async def test_family_needs_consent() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    confirm.arm(rt, "family", [])
    args = {"message": "Ghanshyam ji fell.", "shopper_consented": True}
    assert (await _call(router, "notify_family", args, "f1"))["status"] == "refused"
    confirm.on_shopper_input(rt, "haan bata do")
    assert (await _call(router, "notify_family", args, "f2"))["status"] == "ok"
    assert rt.commerce.notifications == ["Ghanshyam ji fell."]


async def test_problem_suggestions_capped_at_three() -> None:
    rt = make_runtime()
    router = ToolRouter(rt, HANDLERS)
    res = await _call(router, "show_products",
                      {"ids": ["p-0112", "p-0007", "p-0201", "p-0300"], "purpose": "problem"}, "p")
    assert res["status"] == "refused"
    res = await _call(router, "show_products", {"ids": ["p-0112", "p-0007"], "purpose": "problem"}, "q")
    assert res["status"] == "ok"
