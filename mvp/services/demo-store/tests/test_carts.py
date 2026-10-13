"""The shop's cart: the same UCP checkout the assistant uses, through a plain JSON door."""

from demo_store.ap2 import mandates, merchant_auth

MILK = "p-0001"
EGGS = "p-0621"


def body(lines, **extra):
    return {"lines": [{"product_id": pid, "qty": qty} for pid, qty in lines], **extra}


def test_create_read_and_replace_a_cart(client):
    created = client.post("/demo/carts", body([(MILK, 2)]))
    assert created.status_code == 201
    cart = created.json()
    assert cart["status"] == "incomplete" and cart["item_count"] == 1
    line = cart["lines"][0]
    assert line["product"]["id"] == MILK and line["qty"] == 2 and line["line_total"] == line["product"]["price"] * 2
    assert cart["total"] == line["line_total"]

    again = client.get(f"/demo/carts/{cart['id']}").json()
    assert again["lines"] == cart["lines"]

    replaced = client.put(f"/demo/carts/{cart['id']}", body([(MILK, 1), (EGGS, 3)])).json()
    assert [(li["product"]["id"], li["qty"]) for li in replaced["lines"]] == [(MILK, 1), (EGGS, 3)]
    assert replaced["total"] == sum(li["line_total"] for li in replaced["lines"])


def test_an_empty_cart_is_allowed_and_zero_quantities_drop_the_line(client):
    cart = client.post("/demo/carts").json()
    assert cart["lines"] == [] and cart["total"] == 0 and cart["status"] == "incomplete"
    filled = client.put(f"/demo/carts/{cart['id']}", body([(MILK, 1)])).json()
    assert filled["item_count"] == 1
    cleared = client.put(f"/demo/carts/{cart['id']}", body([(MILK, 0)])).json()
    assert cleared["lines"] == [] and cleared["total"] == 0


def test_unknown_products_and_missing_carts_are_rejected(client):
    assert client.post("/demo/carts", body([("p-9999", 1)])).status_code == 400
    assert client.get("/demo/carts/chk_nope").status_code == 404
    assert client.put("/demo/carts/chk_nope", body([])).status_code == 404


def test_the_same_cart_is_visible_to_the_assistant_over_ucp(client):
    cart = client.post("/demo/carts", body([(MILK, 2)])).json()
    ucp = client.get(f"/ucp/v1/checkout-sessions/{cart['id']}").json()
    assert [(li["item"]["id"], li["quantity"]) for li in ucp["line_items"]] == [(MILK, 2)]


def test_slots_and_choosing_a_slot_and_address_makes_it_ready(client):
    slots = client.get("/demo/slots").json()
    assert slots and {"id", "label_hi", "label_en", "start", "end"} <= set(slots[0])
    cart = client.post("/demo/carts", body([(MILK, 1)])).json()
    ready = client.put(f"/demo/carts/{cart['id']}", body([(MILK, 1)], slot_id=slots[0]["id"], address_id="addr-home")).json()
    assert ready["status"] == "ready_for_complete"
    assert ready["slot"]["id"] == slots[0]["id"] and ready["address"]["label"] == "Home"
    # Any change of lines goes back to incomplete (a read-back covers exactly what is in the cart).
    assert client.put(f"/demo/carts/{cart['id']}", body([(MILK, 2)])).json()["status"] == "incomplete"


def test_an_unknown_address_is_rejected(client):
    cart = client.post("/demo/carts", body([(MILK, 1)])).json()
    resp = client.put(f"/demo/carts/{cart['id']}", body([(MILK, 1)], slot_id="earliest", address_id="addr-nope"))
    assert resp.status_code == 400


def test_complete_places_the_order_with_the_approved_mandates_only(client):
    cart = client.post("/demo/carts", body([(MILK, 1)])).json()
    client.put(f"/demo/carts/{cart['id']}", body([(MILK, 1)], slot_id="earliest", address_id="addr-rohit"))
    ucp = client.get(f"/ucp/v1/checkout-sessions/{cart['id']}").json()
    issued = mandates.issue(ucp, merchant_auth.checkout_hash(ucp), "u-ghanshyam")

    bad = client.post(f"/demo/carts/{cart['id']}/complete", {"mandate": {"checkout_mandate": "x.y.z", "payment_mandate": "x.y.z"}})
    assert bad.status_code == 402

    done = client.post(f"/demo/carts/{cart['id']}/complete", {"mandate": {"checkout_mandate": issued.checkout_mandate, "payment_mandate": issued.payment_mandate}})
    assert done.status_code == 200
    placed = done.json()
    assert placed["status"] == "completed"
    assert placed["order"]["id"].startswith("ord_") and placed["order"]["address"]["label"] == "Rohit's place"
    # A finished cart cannot be changed any more.
    assert client.put(f"/demo/carts/{cart['id']}", body([(MILK, 3)])).status_code == 409


def test_a_cart_that_is_not_ready_cannot_complete(client):
    cart = client.post("/demo/carts", body([(MILK, 1)])).json()
    resp = client.post(f"/demo/carts/{cart['id']}/complete", {"mandate": {"checkout_mandate": "a", "payment_mandate": "b"}})
    assert resp.status_code == 409
