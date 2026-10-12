"""Delivery addresses: seeded, added, chosen on a checkout and covered by the signed checkout."""

from support import SCRIPTED_CART, lines_body

SHOPPER = "u-ghanshyam"
NEW = {"label": "Office", "name": "Ghanshyam Sharma", "line1": "Shop 4, FC Road", "area": "Deccan",
       "city": "Pune", "pincode": "411004", "phone": "98765 43210"}


def destination(address_id: str) -> dict:
    return {"shopper_id": SHOPPER, "address_id": address_id}


def test_seeded_addresses_are_listed(client):
    resp = client.get(f"/demo/shoppers/{SHOPPER}/addresses")
    assert resp.status_code == 200
    assert [a["id"] for a in resp.json()] == ["addr-home", "addr-rohit"]


def test_new_address_is_saved_and_listed(client):
    resp = client.post(f"/demo/shoppers/{SHOPPER}/addresses", NEW)
    assert resp.status_code == 201
    saved = resp.json()
    assert saved["label"] == "Office" and saved["phone"] == "9876543210"
    listed = client.get(f"/demo/shoppers/{SHOPPER}/addresses").json()
    assert [a["id"] for a in listed][-1] == saved["id"]


def test_invalid_address_is_rejected(client):
    for bad in ({**NEW, "pincode": "41"}, {**NEW, "phone": "12345"}, {**NEW, "city": ""}):
        assert client.post(f"/demo/shoppers/{SHOPPER}/addresses", bad).status_code == 400


def test_checkout_carries_the_chosen_address(client):
    checkout = client.create(SCRIPTED_CART)
    body = {**lines_body(SCRIPTED_CART, "slot-1800"), "destination": destination("addr-rohit")}
    resp = client.put(f"/ucp/v1/checkout-sessions/{checkout['id']}", body)
    assert resp.status_code == 200, resp.text
    method = resp.json()["fulfillment"]["methods"][0]
    assert method["selected_destination_id"] == "addr-rohit"
    assert method["destinations"][0]["address"]["area"] == "Baner"


def test_address_is_kept_when_destination_is_omitted_and_part_of_the_signature(client):
    checkout = client.create(SCRIPTED_CART)
    url = f"/ucp/v1/checkout-sessions/{checkout['id']}"
    home = client.put(url, {**lines_body(SCRIPTED_CART, "slot-1800"), "destination": destination("addr-home")}).json()
    kept = client.put(url, lines_body(SCRIPTED_CART, "slot-1800")).json()
    assert kept["fulfillment"]["methods"][0]["selected_destination_id"] == "addr-home"
    other = client.put(url, {**lines_body(SCRIPTED_CART, "slot-1800"), "destination": destination("addr-rohit")}).json()
    # A different address is a different checkout, so the merchant signature differs.
    assert home["ap2"]["merchant_authorization"] != other["ap2"]["merchant_authorization"]


def test_unknown_address_is_rejected(client):
    checkout = client.create(SCRIPTED_CART)
    body = {**lines_body(SCRIPTED_CART, "slot-1800"), "destination": destination("addr-nope")}
    resp = client.put(f"/ucp/v1/checkout-sessions/{checkout['id']}", body)
    assert resp.status_code == 400 and resp.json()["messages"][0]["code"] == "INVALID_ADDRESS"
