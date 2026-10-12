"""Catalogue search (T043) plus lookup, filters, seeded mode and normalisation."""

import re

import pytest
from ucp_sdk.models.schemas.shopping.types.product import Product as UcpProduct

from demo_store.catalog import normalize
from demo_store.catalog.store import get_catalog
from demo_store.models.domain import Product

INCLUDE = {"dairy", "flours", "biscuits", "baking", "beverages", "spices", "staples", "snacks",
           "produce", "home"}
HEALTH = re.compile(r"vitamin|supplement|protein|medicine|balm|tablet|capsule|syrup|infant", re.I)


def domain(product: dict) -> Product:
    return Product.model_validate(product["metadata"]["talktobuy"])


def first(result: dict) -> Product:
    assert result["products"], "no results"
    return domain(result["products"][0])


@pytest.mark.parametrize("query", ["पाव किलो टमाटर", "tamatar", "टमाटर", "tomatoes"])
def test_tomatoes_250g_first(client, query):
    top = first(client.search(query))
    assert (top.id, top.category, top.unit_qty, top.unit) == ("p-0002", "produce", 250, "g")


def test_paav_kilo_is_not_ambiguous(client):
    assert client.search("पाव किलो टमाटर")["metadata"]["talktobuy"]["ambiguous"] is False


@pytest.mark.parametrize("query", ["Parle-G", "parle g", "पारले जी", "glucose biscuit"])
def test_parle_g_returns_glucose_biscuit(client, query):
    top = first(client.search(query))
    assert top.id == "p-0004" and top.category == "biscuits"


@pytest.mark.parametrize("query", ["doodh", "दूध", "dudh", "toned milk"])
def test_doodh_returns_toned_milk(client, query):
    top = first(client.search(query))
    assert top.id == "p-0001" and top.unit_qty == 1000 and top.unit == "ml"


@pytest.mark.parametrize("query", ["pain balm", "vitamin", "protein powder", "दवाई", "medicine"])
def test_medicine_queries_return_no_medicine_or_supplement(client, query):
    for product in client.search(query)["products"]:
        p = domain(product)
        assert p.category in INCLUDE
        assert not HEALTH.search(f"{p.name} {p.brand or ''} {' '.join(p.source_categories)}"), p.name


@pytest.mark.parametrize(("query", "expected"), [
    ("maida", "p-0005"), ("मैदा", "p-0005"), ("cocoa powder", "p-0006"), ("कोको पाउडर", "p-0006"),
    ("butter", "p-0007"), ("मक्खन", "p-0007"), ("condensed milk", "p-0008"), ("milkmaid", "p-0008"),
    ("baking powder", "p-0032"), ("बेकिंग पाउडर", "p-0032"), ("7 inch cake tin", "p-0010"),
    ("केक टिन", "p-0010"), ("चीनी", "p-0011"), ("cheeni", "p-0011"), ("baking soda", "p-0012"),
    ("बेकिंग सोडा", "p-0012"), ("आटा", "p-0003"), ("मेरा हमेशा वाला आटा", "p-0003"),
])
def test_demo_items_rank_first(client, query, expected):
    assert first(client.search(query)).id == expected


def test_at_most_ten_results(client):
    result = client.search("biscuit", pagination={"limit": 50})
    assert 0 < len(result["products"]) <= 10
    assert result["pagination"] == {"has_next_page": False}


def test_out_of_stock_returned_flagged_and_after_in_stock(client):
    products = client.search("pillsbury atta")["products"]
    flags = [domain(p).in_stock for p in products]
    oos = [p for p in products if p["id"] == "p-0018"]
    assert oos, "the out-of-stock best match must still be returned"
    assert oos[0]["metadata"]["talktobuy"]["in_stock"] is False
    assert oos[0]["variants"][0]["availability"]["available"] is False
    assert flags == sorted(flags, reverse=True)  # in-stock first


def test_scores_and_ambiguity_metadata(client):
    meta = client.search("doodh")["metadata"]["talktobuy"]
    scores = list(meta["scores"].values())
    assert meta["ambiguous"] is (len(scores) >= 2 and sorted(scores)[-1] - sorted(scores)[-2] < 0.05)


def test_products_conform_to_ucp_and_domain(client):
    for product in client.search("atta")["products"]:
        UcpProduct.model_validate(product)
        p = domain(product)
        assert product["price_range"]["min"] == {"amount": p.price_minor, "currency": "INR"}
        assert product["media"][0]["url"].startswith(("https://", "http://store.test/static/"))


def test_category_and_price_filters(client):
    result = client.search("doodh", filters={"categories": ["dairy"], "price": {"min": 0, "max": 3000}})
    assert result["products"]
    for product in result["products"]:
        p = domain(product)
        assert p.category == "dairy" and p.price_minor <= 3000


def test_quantity_only_query_returns_nothing(client):
    assert client.search("paav kilo")["products"] == []


def test_lookup_keeps_request_order_and_omits_unknown(client):
    resp = client.post("/ucp/v1/catalog/lookup", {"ids": ["p-0007", "p-9999", "p-0001"]})
    assert resp.status_code == 200
    assert [p["id"] for p in resp.json()["products"]] == ["p-0007", "p-0001"]


def test_ucp_headers_required(client):
    resp = client.raw.post("/ucp/v1/catalog/search", json={"query": "doodh"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["ucp"]["status"] == "error" and body["messages"][0]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize(("query", "expected"), [
    ("यह ख़त्म हो गया", "p-0004"), ("दो लीटर दूध", "p-0001"), ("पाव किलो टमाटर", "p-0002"),
    ("मेरा हमेशा वाला आटा", "p-0003"), ("maida", "p-0005"), ("7 inch cake tin", "p-0010"),
    ("cocoa powder", "p-0006"), ("condensed milk", "p-0008"), ("baking soda", "p-0012"),
])
def test_seeded_mode(client, search_mode, query, expected):
    search_mode("seeded")
    result = client.search(query)
    assert result["products"][0]["id"] == expected
    assert result["metadata"]["talktobuy"]["ambiguous"] is False


def test_seeded_medicine_is_empty(client, search_mode):
    search_mode("seeded")
    assert client.search("pain balm")["products"] == []


def test_seeded_ids_exist():
    from demo_store.catalog.seeded import PHRASES

    catalog = get_catalog()
    for ids in PHRASES.values():
        assert all(catalog.get(i) for i in ids)


@pytest.mark.parametrize(("a", "b"), [
    ("दूध", "doodh"), ("चीनी", "cheeni"), ("टमाटर", "tamaatar"), ("आटा", "atta"), ("मैदा", "maida"),
    ("पाव किलो टमाटर", "tamatar"), ("दो लीटर दूध", "dudh"),
])
def test_transliteration_lite(a, b):
    assert normalize.key(a) == normalize.key(b)


def test_size_hint():
    assert normalize.size_hint("पाव किलो टमाटर") == (250, "g")
    assert normalize.size_hint("5 kg atta") == (5000, "g")
    assert normalize.size_hint("tamatar") is None
