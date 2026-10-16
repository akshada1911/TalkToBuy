"""plan_dish: a named dish becomes a list of ingredients in proper amounts and packs, and is added after a yes."""

import asyncio
import itertools

from session_server.core import confirm
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.ports.live import ToolCall
from session_server.ports.planner import DishPlan, PlannedItem
from session_server.testing.fakes import DEMO_PRODUCTS, FakeCommerce, FakePlanner, make_runtime, product

EXTRA = [
    product("p-1001", "Basmati Rice 1 kg", "बासमती चावल", "1 kg", 1000, "g", 12000, "staples", ["rice", "chawal", "basmati"]),
    product("p-1002", "Basmati Rice 5 kg", "बासमती चावल", "5 kg", 5000, "g", 55000, "staples", ["rice", "chawal", "basmati"]),
    product("p-1003", "Green Peas 500 g", "हरी मटर", "500 g", 500, "g", 6000, "produce", ["peas", "matar", "green peas"]),
    product("p-1004", "Iodised Salt 1 kg", "नमक", "1 kg", 1000, "g", 2500, "staples", ["salt", "namak"]),
    product("p-1005", "Eggs 6", "अंडे", "6 pcs", 6, "piece", 7800, "dairy", ["egg", "eggs"]),
    product("p-1006", "Garlic Pickle 200 g", "लहसुन का अचार", "200 g", 200, "g", 9000, "staples", ["garlic", "achar"], brand="Double Horse"),
    product("p-1007", "Garlic 100 g", "लहसुन", "100 g", 100, "g", 3000, "produce", ["garlic", "lahsun"]),
    product("p-1008", "Ginger Snap Cookies 70 g", "जिंजर कुकीज़", "70 g", 70, "g", 4000, "biscuits", ["ginger snap"]),
    product("p-1009", "Tomatoes Value Pack 1 kg", "टमाटर", "1 kg", 1000, "g", 6000, "produce", ["tomato", "tamatar"]),
    product("p-1011", "Chilli Powder 100 g", "मिर्च पाउडर", "100 g", 100, "g", 3500, "spices", ["chilli powder"], brand="Eastern"),
    product("p-1012", "Dahi Curd 400 g", "दही", "400 g", 400, "g", 4000, "dairy", ["curd", "dahi"]),
    product("p-1013", "Peanut Butter 340 g", "पीनट बटर", "340 g", 340, "g", 25000, "staples", ["peanut"], brand="Goody"),
    product("p-1010", "Green Chillies 100 g", "हरी मिर्च", "100 g", 100, "g", 1500, "produce", ["green chilli", "mirch"]),
]

MATAR_PANEER = [
    PlannedItem("paneer", 400, "g"),
    PlannedItem("green peas", 500, "g"),
    PlannedItem("tomato", 500, "g"),
    PlannedItem("salt", 30, "g", staple=True),
    PlannedItem("saffron", 1, "g"),  # not sold here
]


def _rt(plans):
    rt = make_runtime(FakeCommerce(DEMO_PRODUCTS + EXTRA))
    rt.planner = FakePlanner(plans)
    return rt, ToolRouter(rt, HANDLERS)


_ids = itertools.count(1)


async def _plan(rt, router, heard=True, **args):
    if heard:
        rt.shopper_history = [f"{args['people']} people"]  # the shopper said the number
    cid = f"p{next(_ids)}"
    await router.handle(ToolCall(cid, "plan_dish", args))
    resp = rt.live.response_for(cid)
    assert resp["status"] == "ok", resp
    return resp["result"]


async def test_a_dish_becomes_proper_packs_and_a_list_on_screen() -> None:
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    out = await _plan(rt, router, dish="Matar Paneer", people=5)
    by = {i["need"]: i for i in out["items"]}
    assert (by["paneer"]["product_id"], by["paneer"]["qty"]) == ("p-0998", 2)  # 400 g = 2 x 200 g, in stock only
    assert (by["green peas"]["product_id"], by["green peas"]["qty"]) == ("p-1003", 1)
    assert (by["tomato"]["product_id"], by["tomato"]["qty"]) == ("p-0007", 2)  # 500 g = 2 x 250 g
    assert by["paneer"]["amount"] == "400 g" and by["paneer"]["total"] == "400 g"
    assert out["not_in_catalogue"] == ["saffron"]
    assert out["ask_if_at_home"] == ["salt"]
    assert out["dish"] == "Matar Paneer" and out["people"] == 5
    assert rt.ui.of("goal_list")[-1]["goal_text"] == "Matar Paneer for 5 people"
    assert out["estimated_total_rupees"] > 0


async def test_a_big_headcount_uses_big_packs_and_says_the_weight_not_packets() -> None:
    rt, router = _rt({"veg biryani": [PlannedItem("basmati rice", 5000, "g")]})
    out = await _plan(rt, router, dish="veg biryani", people=50)
    rice = out["items"][0]
    assert (rice["product_id"], rice["qty"]) == ("p-1002", 1)  # 1 x 5 kg, not 5 x 1 kg and never 50 packets
    assert rice["amount"] == "5 kg" and rice["total"] == "5 kg"


async def test_pack_count_is_capped() -> None:
    rt, router = _rt({"tomato curry": [PlannedItem("tomato", 100000, "g")]})
    out = await _plan(rt, router, dish="tomato curry", people=500)
    assert out["items"][0]["qty"] == 20 and out["items"][0]["capped"] is True


async def test_items_the_shopper_has_are_struck_and_the_plan_is_reused() -> None:
    planner = FakePlanner({"matar paneer": MATAR_PANEER})
    rt, router = _rt({})
    rt.planner = planner
    await _plan(rt, router, dish="matar paneer", people=5)
    out = await _plan(rt, router, dish="Matar Paneer", people=5, on_hand=["salt", "tomatoes"])
    home = {i["need"] for i in out["items"] if i["on_hand"]}
    assert home == {"salt", "tomato"}
    assert len(planner.calls) == 1  # the second call did not ask the planner again
    struck = {i["need"]: i["struck_reason"] for i in rt.ui.of("goal_list")[-1]["items"] if i["struck"]}
    assert struck == {"salt": "on_hand", "tomato": "on_hand"}


async def test_yes_adds_exactly_the_planned_packs() -> None:
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    out = await _plan(rt, router, dish="matar paneer", people=5, on_hand=["salt"])
    await router.handle(ToolCall("a0", "add_to_cart", {"goal_id": out["goal_id"]}))
    assert rt.live.response_for("a0")["status"] == "refused"  # nothing is added before a yes
    confirm.on_shopper_input(rt, "हाँ चलेगा")
    await router.handle(ToolCall("a1", "add_to_cart", {"goal_id": out["goal_id"]}))
    assert rt.live.response_for("a1")["status"] == "ok"
    lines = {line["product_id"]: line["qty"] for line in rt.live.response_for("a1")["result"]["lines"]}
    assert lines == {"p-0998": 2, "p-1003": 1, "p-0007": 2}


async def test_a_planner_that_did_not_answer_tells_the_model_to_try_again() -> None:
    rt, router = _rt({})
    rt.shopper_history = ["for 2 people"]
    await router.handle(ToolCall("p", "plan_dish", {"dish": "anything", "people": 2}))
    resp = rt.live.response_for("p")
    assert resp["status"] == "error" and "call plan_dish again" in resp["message"] and resp["retryable"]


async def test_the_right_product_is_chosen_or_none_at_all() -> None:
    plan_ = [PlannedItem("garlic", 20, "g"), PlannedItem("ginger", 30, "g"), PlannedItem("fresh green chilli", 15, "g"),
             PlannedItem("tomato", 350, "g")]
    rt, router = _rt({"curry": plan_})
    out = await _plan(rt, router, dish="curry", people=4)
    by = {i["need"]: i for i in out["items"]}
    assert by["garlic"]["product_id"] == "p-1007"  # the fresh garlic, not the pickle
    assert by["ginger"]["product_id"] is None  # ginger snap cookies are not ginger
    assert by["fresh green chilli"]["product_id"] == "p-1010"  # "chillies" and "chilli" are the same word
    assert (by["tomato"]["product_id"], by["tomato"]["qty"]) == ("p-0007", 2)  # 2 x 250 g, not a 1 kg value pack
    assert out["not_in_catalogue"] == ["ginger"]


async def test_other_names_and_a_dropped_colour_find_the_product() -> None:
    plan_ = [PlannedItem("yogurt", 400, "g", alt=("curd",)), PlannedItem("red chili powder", 10, "g"),
             PlannedItem("tomato", 1500, "g")]
    rt, router = _rt({"raita": plan_})
    out = await _plan(rt, router, dish="raita", people=6)
    by = {i["need"]: i for i in out["items"]}
    assert by["yogurt"]["product_id"] == "p-1012"  # not found as "yogurt", found as "curd"
    assert by["red chili powder"]["product_id"] == "p-1011"  # "red" dropped: the shop sells plain chilli powder
    assert (by["tomato"]["product_id"], by["tomato"]["qty"]) == ("p-1009", 2)  # 2 x 1 kg beats 6 x 250 g


async def test_the_number_of_people_is_never_guessed() -> None:
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    await router.handle(ToolCall("g1", "plan_dish", {"dish": "matar paneer", "people": 4}))
    refused = rt.live.response_for("g1")
    assert refused["status"] == "refused" and "number of people" in refused["message"]
    for said in ("for 4 people", "चार लोगों के लिए", "four of us", "४"):
        rt.shopper_history = [said]
        rt.dish_plans.clear()
        await router.handle(ToolCall(f"g-{said}", "plan_dish", {"dish": "matar paneer", "people": 4}))
        assert rt.live.response_for(f"g-{said}")["status"] == "ok", said
    rt.shopper_history = ["just me"]
    rt.dish_plans.clear()
    await router.handle(ToolCall("g-solo", "plan_dish", {"dish": "matar paneer", "people": 1}))
    assert rt.live.response_for("g-solo")["status"] == "ok"
    rt.shopper_history = ["I have salt and oil"]  # a repeat of a heard plan needs no new number
    await router.handle(ToolCall("g-again", "plan_dish", {"dish": "matar paneer", "people": 1, "on_hand": ["salt"]}))
    assert rt.live.response_for("g-again")["status"] == "ok"


async def test_the_assumed_version_is_passed_on_and_an_unknown_dish_is_not_guessed() -> None:
    rt, router = _rt({
        "biryani": DishPlan([PlannedItem("basmati rice", 500, "g")], assumption="A vegetarian biryani."),
        "blorptang": DishPlan([], recognised=False),
    })
    out = await _plan(rt, router, dish="biryani", people=5)
    assert out["assumption"] == "A vegetarian biryani." and "assumption" in out["instruction"]
    await router.handle(ToolCall("u1", "plan_dish", {"dish": "blorptang", "people": 5}))
    resp = rt.live.response_for("u1")
    assert resp["status"] == "error" and "not recognised" in resp["message"] and "Do not guess" in resp["message"]


async def test_a_processed_form_is_not_the_raw_ingredient() -> None:
    rt, router = _rt({"satay": [PlannedItem("peanut", 100, "g"), PlannedItem("butter", 100, "g"),
                                PlannedItem("chili powder", 10, "g")]})
    out = await _plan(rt, router, dish="satay", people=4)
    by = {i["need"]: i for i in out["items"]}
    assert by["peanut"]["product_id"] is None  # peanut butter is not peanuts
    assert by["butter"]["product_id"] == "p-0501"  # but 'butter' still finds butter
    assert by["chili powder"]["product_id"] == "p-1011"


async def test_the_planner_retries_on_the_lighter_model_and_reports_the_error() -> None:
    import json
    from types import SimpleNamespace

    from session_server.adapters.gemini_flash.planner import FlashPlanner

    asked = []

    async def generate_content(model, contents, config):
        asked.append(model)
        if model == "primary":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return SimpleNamespace(text=json.dumps({"recognised": True, "assumption": "Plain.", "items": [
            {"need": "rice", "per_person": 100, "fixed": 0, "unit": "g", "staple": False}]}))

    planner = FlashPlanner.__new__(FlashPlanner)
    planner.models = ["primary", "backup"]
    planner.client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    plan = await planner.plan("pulao", None)
    assert asked == ["primary", "backup"] and plan.items[0].need == "rice" and plan.assumption == "Plain."
    assert plan.items[0].total(4) == 400  # 100 g per person x 4

    async def always_bad(model, contents, config):
        return SimpleNamespace(text="not json")

    planner.client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=always_bad)))
    assert await planner.plan("pulao", None) is None


async def test_the_list_is_prepared_when_the_dish_is_named_and_scales_instantly() -> None:
    planner = FakePlanner({"veg biryani": [PlannedItem("basmati rice", 0, "g", per_person=100),
                                           PlannedItem("salt", 5, "g", staple=True, per_person=2)]})
    rt, router = _rt({})
    rt.planner = planner
    # 1. the dish is named: prepare in the background and answer at once, with no list yet
    await router.handle(ToolCall("d1", "plan_dish", {"dish": "veg biryani"}))
    first = rt.live.response_for("d1")["result"]
    assert first["status"] == "preparing" and "how many people" in first["instruction"]
    assert not rt.ui.of("goal_list")
    for _ in range(20):  # the background work finishes while the shopper answers
        await asyncio.sleep(0)
    searches_before = len([c for c in rt.commerce.calls if c[0] == "search"])
    assert planner.calls == [("veg biryani", None)] and searches_before >= 2
    # 2. the number arrives: the same plan scales, and nothing is planned or searched again
    out = await _plan(rt, router, dish="veg biryani", people=50)
    rice = next(i for i in out["items"] if i["need"] == "basmati rice")
    salt = next(i for i in out["items"] if i["need"] == "salt")
    assert (rice["product_id"], rice["qty"]) == ("p-1002", 1) and rice["amount"] == "5 kg"  # 100 g x 50
    assert salt["amount"] == "105 g"  # 5 g flat + 2 g x 50
    assert planner.calls == [("veg biryani", None)]
    assert len([c for c in rt.commerce.calls if c[0] == "search"]) == searches_before
    # the same list for another headcount: instant, and the amounts follow
    again = await _plan(rt, router, dish="veg biryani", people=5)
    assert next(i for i in again["items"] if i["need"] == "basmati rice")["amount"] == "500 g"
    assert planner.calls == [("veg biryani", None)] and "SHORT" in out["instruction"]


async def test_a_yes_whose_transcript_arrives_late_still_adds_the_list() -> None:
    """The model hears 'yes' and calls add_to_cart before the transcript of it reaches the server (the cloud is a
    little slower). The call waits a moment for the transcript instead of refusing and making the shopper repeat."""
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    out = await _plan(rt, router, dish="matar paneer", people=5)
    rt.last_shopper_signal = rt.clock()  # the shopper is speaking right now

    async def transcript_arrives_late():
        await asyncio.sleep(0.5)
        confirm.on_shopper_input(rt, "yes please")

    late = asyncio.ensure_future(transcript_arrives_late())
    await router.handle(ToolCall("late", "add_to_cart", {"goal_id": out["goal_id"]}))
    await late
    assert rt.live.response_for("late")["status"] == "ok"


async def test_nothing_is_added_when_the_shopper_said_nothing() -> None:
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    out = await _plan(rt, router, dish="matar paneer", people=5)
    rt.last_shopper_signal = rt.clock() - 60  # quiet for a minute: no waiting, no adding
    t0 = asyncio.get_event_loop().time()
    await router.handle(ToolCall("quiet", "add_to_cart", {"goal_id": out["goal_id"]}))
    assert rt.live.response_for("quiet")["status"] == "refused"
    assert asyncio.get_event_loop().time() - t0 < 1.0


async def test_an_older_list_of_the_same_dish_is_replaced_by_the_latest_one() -> None:
    """After 'I have salt at home' the list is planned again; adding by the old list id must add the latest list."""
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    first = await _plan(rt, router, dish="matar paneer", people=5)
    second = await _plan(rt, router, dish="matar paneer", people=5, on_hand=["salt", "tomato"])
    assert first["goal_id"] != second["goal_id"]
    confirm.on_shopper_input(rt, "yes add it")
    await router.handle(ToolCall("stale", "add_to_cart", {"goal_id": first["goal_id"]}))  # the model used the old id
    resp = rt.live.response_for("stale")
    assert resp["status"] == "ok"
    names = {line["name"] for line in resp["result"]["lines"]}
    assert not any("Tomato" in n for n in names)  # the tomatoes the shopper has at home were not added


async def test_a_no_in_the_answer_does_not_kill_the_pending_list() -> None:
    """After 'do you have any at home, or shall I add everything?' people say 'No, add everything' or just 'No'."""
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    out = await _plan(rt, router, dish="matar paneer", people=5)
    gid = out["goal_id"]

    # "No, I do not have any of these. Please add everything." is a yes to adding.
    confirm.on_shopper_input(rt, "No, I do not have any of these at home. Please add everything.")
    assert rt.session.pending_confirmation.confirmed is True

    # A bare "No" (I have none) withdraws nothing it cannot recover: the list stays pending...
    rt.session.pending_confirmation.confirmed = False
    confirm.on_shopper_input(rt, "No.")
    assert rt.session.pending_confirmation is not None and rt.session.pending_confirmation.confirmed is False
    await router.handle(ToolCall("n1", "add_to_cart", {"goal_id": gid}))
    assert rt.live.response_for("n1")["status"] == "refused"  # not added on a "no"

    # ...so the "yes" that follows still adds it.
    confirm.on_shopper_input(rt, "Yes, add it.")
    await router.handle(ToolCall("n2", "add_to_cart", {"goal_id": gid}))
    assert rt.live.response_for("n2")["status"] == "ok"


async def test_an_explicit_refusal_still_drops_the_list() -> None:
    rt, router = _rt({"matar paneer": MATAR_PANEER})
    await _plan(rt, router, dish="matar paneer", people=5)
    for said in ("don't add anything", "cancel that", "nahi chahiye", "रहने दो"):
        rt.session.pending_confirmation = rt.session.pending_confirmation or None
        await _plan(rt, router, dish="matar paneer", people=5)  # re-arm
        confirm.on_shopper_input(rt, said)
        assert rt.session.pending_confirmation is None, said
