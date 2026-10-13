"""The committed catalogue snapshot (T015-T019, T059) and the scripted-cart arithmetic."""

import json
import re
from pathlib import Path

from demo_store.models.domain import Product

DATA = Path(__file__).resolve().parents[1] / "data"
CATALOG = json.loads((DATA / "catalog.json").read_text("utf-8"))["products"]
SEED = json.loads((DATA / "seed_barcodes.json").read_text("utf-8"))
DEMO_IDS = {e["id"] for e in SEED["stage1"] if e.get("demo")} | {
    pid for pid, demo in SEED["hand_added"].items() if demo
}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
DENY_TAGS = {"en:dietary-supplements", "en:food-supplements", "en:vitamins", "en:protein-powders",
             "en:baby-milks", "en:infant-formulas", "en:non-food-products"}
HEALTH_CLAIMS = re.compile(r"health|immun|vitamin|nutri|boost|strong bones|energy|cure|heal", re.I)


def test_every_product_validates_with_unique_ids():
    products = [Product.model_validate(p) for p in CATALOG]
    ids = [p.id for p in products]
    assert len(ids) == len(set(ids))
    assert 300 <= len(products) <= 600  # spec: 300–500 core items, plus the hand-added menu


def test_demo_items_complete():
    by_id = {p["id"]: p for p in CATALOG}
    assert len(DEMO_IDS) == 12
    for pid in DEMO_IDS:
        p = by_id[pid]
        assert DEVANAGARI.search(p["local_name"]), pid
        assert p["listing"]["description"] and p["listing"]["usage"] and p["image"] and p["image_credit"]
        assert p["synonyms"]
        assert not HEALTH_CLAIMS.search(p["listing"]["description"] + p["listing"]["usage"]), pid
    assert by_id["p-0008"]["barcode"] == "8901058903959"  # Milkmaid's single India record


def test_every_item_has_hindi_name_and_credit():
    for p in CATALOG:
        assert DEVANAGARI.search(p["local_name"]), p["id"]
        assert p["image_credit"], p["id"]


def test_hand_added_items():
    by_id = {p["id"]: p for p in CATALOG}
    tomatoes, tin = by_id["p-0002"], by_id["p-0010"]
    assert (tomatoes["category"], tomatoes["unit_qty"], tomatoes["unit"]) == ("produce", 250, "g")
    assert (tin["category"], tin["unit"]) == ("home", "piece")
    for p in (tomatoes, tin):
        assert p["image"] == f"/static/products/{p['id']}.svg"
        assert (DATA.parent / "static" / "products" / f"{p['id']}.svg").exists()


def test_exactly_one_non_demo_item_out_of_stock():
    oos = [p["id"] for p in CATALOG if not p["in_stock"]]
    assert len(oos) == 1 and oos[0] not in DEMO_IDS


def test_include_list_and_denylist():
    include = {"dairy", "flours", "biscuits", "baking", "beverages", "spices", "staples", "snacks",
               "produce", "home"}
    for p in CATALOG:
        assert p["category"] in include
        assert not DENY_TAGS.intersection(p["source_categories"]), p["id"]


def test_scripted_cart_totals_1016_rupees():
    by_id = {p["id"]: p for p in CATALOG}
    from support import SCRIPTED_CART

    assert len(SCRIPTED_CART) == 10
    assert sum(by_id[pid]["price_minor"] * qty for pid, qty in SCRIPTED_CART) == 101600
