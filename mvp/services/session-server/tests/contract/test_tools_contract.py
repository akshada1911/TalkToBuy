"""T042: every tool's args and results match mvp/contracts/tools.schema.json; product and session
records match mvp/contracts/domain.schema.json; the Gemini conversion stays representable."""

import asyncio
import json

import pytest
from google.genai import types
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from session_server.adapters.gemini_live.tools import convert_schema, to_function_declarations
from session_server.config import MVP_ROOT
from session_server.core import confirm
from session_server.core.tool_router import Deferred, load_tool_specs
from session_server.core.tools import HANDLERS
from session_server.testing.fakes import DEMO_PRODUCTS, make_runtime

TOOLS_DOC = json.loads((MVP_ROOT / "contracts" / "tools.schema.json").read_text(encoding="utf-8"))
DOMAIN_DOC = json.loads((MVP_ROOT / "contracts" / "domain.schema.json").read_text(encoding="utf-8"))
SPECS = {s["name"]: s for s in TOOLS_DOC["tools"]}
EXPECTED = {"search_catalog", "show_products", "add_to_cart", "update_cart", "get_usual_order",
            "set_pace", "start_checkout", "confirm_checkout", "notify_family"}


def _returns_validator(name: str) -> Draft202012Validator:
    registry = Registry().with_resource("urn:tools", Resource.from_contents(TOOLS_DOC))
    schema = {**SPECS[name]["returns"], "$defs": TOOLS_DOC["$defs"]}
    return Draft202012Validator(schema, registry=registry)


def _domain_validator(defn: str) -> Draft202012Validator:
    return Draft202012Validator({"$ref": f"#/$defs/{defn}", "$defs": DOMAIN_DOC["$defs"]})


def test_exactly_the_nine_tools() -> None:
    assert set(SPECS) == EXPECTED
    assert set(HANDLERS) == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_parameter_schemas_are_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(SPECS[name]["parameters"])


def test_gemini_declarations_keep_names_required_and_behavior() -> None:
    decls = {d.name: d for d in to_function_declarations(load_tool_specs())}
    assert set(decls) == EXPECTED
    assert decls["start_checkout"].behavior == types.Behavior.BLOCKING
    assert decls["confirm_checkout"].behavior == types.Behavior.NON_BLOCKING
    assert decls["search_catalog"].parameters.required == ["query"]
    assert decls["get_usual_order"].parameters is None


def test_conversion_maps_nulls_and_rejects_union_schemas() -> None:
    goal_item = convert_schema(SPECS["show_products"]["parameters"])["properties"]["goal_list"][
        "properties"]["items"]["items"]["properties"]
    assert goal_item["product_id"] == {"type": "STRING", "nullable": True}
    assert goal_item["struck_reason"]["nullable"] is True and None not in goal_item["struck_reason"]["enum"]
    consent = convert_schema(SPECS["notify_family"]["parameters"])["properties"]["shopper_consented"]
    assert consent["type"] == "BOOLEAN"
    blob = json.dumps(TOOLS_DOC)
    assert '"oneOf"' not in blob and '"anyOf"' not in blob
    with pytest.raises(ValueError):
        convert_schema({"oneOf": [{"type": "string"}]})


async def _call(rt, name, args):
    errors = list(Draft202012Validator(SPECS[name]["parameters"]).iter_errors(args))
    assert not errors, errors
    result = await HANDLERS[name](rt, args)
    if isinstance(result, Deferred):
        rt.payment_future.set_result({"approved": True, "mandate": {"checkout_mandate": "valid-test-mandate",
                                                                     "payment_mandate": "pm"}})
        result = await result.awaitable
    _returns_validator(name).validate(result)
    return result


async def test_all_nine_handler_results_match_their_contracts() -> None:
    rt = make_runtime()
    await _call(rt, "search_catalog", {"query": "doodh", "amount_phrase": "do litre"})
    await _call(rt, "show_products", {"ids": ["p-0112"]})
    await _call(rt, "add_to_cart", {"product_id": "p-0112", "qty": 2, "source": "named"})
    await _call(rt, "update_cart", {"product_id": "p-0112", "qty": 3})
    await _call(rt, "get_usual_order", {})
    await _call(rt, "set_pace", {"mode": "quick", "reason": "opening_question"})
    readback = await _call(rt, "start_checkout", {"delivery_slot": "earliest"})
    await _call(rt, "confirm_checkout", {"checkout_id": readback["checkout_id"]})
    confirm.arm(rt, "family", [])
    confirm.on_shopper_input(rt, "हाँ")
    await _call(rt, "notify_family", {"message": "Ghanshyam ji reported a fall.", "shopper_consented": True})
    await asyncio.sleep(0)


@pytest.mark.parametrize("product", DEMO_PRODUCTS, ids=lambda p: p.id)
def test_store_product_records_match_domain_schema(product) -> None:
    _domain_validator("Product").validate(product.model_dump(mode="json"))


def test_persisted_session_matches_domain_schema() -> None:
    rt = make_runtime()
    confirm.arm(rt, "usual", ["p-0201"])
    _domain_validator("Session").validate(rt.session.model_dump(mode="json"))
