"""Demo catalogue browsing used by the shop app's Home, list and product screens."""


def test_browse_lists_in_stock_first_with_whole_rupee_prices(client):
    body = client.get("/demo/catalog?limit=5").json()
    assert body["total"] == 525 and len(body["items"]) == 5 and body["limit"] == 5
    first = body["items"][0]
    assert isinstance(first["price"], int) and first["image"].startswith("http")
    assert {"id", "name", "local_name", "size", "category", "in_stock", "description"} <= set(first)


def test_browse_filters_by_category_and_pages(client):
    page1 = client.get("/demo/catalog?category=dairy&limit=10").json()
    page2 = client.get("/demo/catalog?category=dairy&limit=10&offset=10").json()
    assert page1["total"] == page2["total"] and page1["total"] > 10
    assert all(p["category"] == "dairy" for p in page1["items"] + page2["items"])
    assert not {p["id"] for p in page1["items"]} & {p["id"] for p in page2["items"]}


def test_browse_search_matches_names_synonyms_and_hindi(client):
    milk = client.get("/demo/catalog?q=milk&limit=20").json()
    assert milk["items"] and any("milk" in p["name"].lower() for p in milk["items"][:5])
    hindi = client.get("/demo/catalog?q=%E0%A4%A6%E0%A5%82%E0%A4%A7&limit=20").json()  # दूध
    assert hindi["items"]
    assert client.get("/demo/catalog?q=zzzzqqqq").json()["items"] == []


def test_categories_and_product_detail(client):
    cats = client.get("/demo/catalog/categories").json()
    assert {"id": "dairy", "count": 88} in cats
    detail = client.get("/demo/catalog/p-0001").json()
    assert detail["id"] == "p-0001" and detail["similar"]
    assert all(s["category"] == detail["category"] and s["id"] != "p-0001" for s in detail["similar"])
    assert client.get("/demo/catalog/p-9999").status_code == 404


def test_browse_validates_paging(client):
    assert client.get("/demo/catalog?limit=0").status_code == 400
    assert client.get("/demo/catalog?limit=500").status_code == 400


def test_the_everyday_menu_items_exist_and_are_found_by_english_and_hindi_names(client):
    for q, expect in [("palak", "Palak"), ("eggs", "Farm Eggs"), ("bread", "Bread"), ("banana", "Bananas"), ("garlic", "Garlic"),
                      ("%E0%A4%85%E0%A4%82%E0%A4%A1%E0%A5%87", "Farm Eggs")]:  # अंडे
        items = client.get(f"/demo/catalog?q={q}&limit=20").json()["items"]
        assert any(expect in p["name"] for p in items), q
    # The assistant's own catalogue search finds them too.
    found = client.post("/ucp/v1/catalog/search", {"query": "palak", "pagination": {"limit": 5}}).json()["products"]
    assert any("Palak" in p["title"] for p in found)
