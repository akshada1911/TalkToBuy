"""Checkout sessions, fulfillment and AP2 complete (T049, T061, T063-T066)."""

import base64
import json
import time

import pytest
from jwcrypto import jwk, jws
from support import SCRIPTED_CART, SoftAuthenticator, lines_body

from demo_store.ap2 import mandates, merchant_auth


def totals_of(checkout: dict) -> dict:
    return {t["type"]: t["amount"] for t in checkout["totals"]}


def mint(checkout: dict, now: float | None = None, merchant_authorization: str | None = None):
    """Mandates for a rendered checkout, as the payment surface would issue them."""
    if merchant_authorization:
        checkout = {**checkout, "ap2": {"merchant_authorization": merchant_authorization}}
    return mandates.issue(checkout, merchant_auth.checkout_hash(checkout), "u-ghanshyam", now=now)


def complete_body(checkout_mandate: str | None, payment_mandate: str | None) -> dict:
    body: dict = {}
    if checkout_mandate:
        body["ap2"] = {"checkout_mandate": checkout_mandate}
    if payment_mandate:
        body["payment"] = {"instruments": [{"handler_id": "com.example.card",
                                            "credential": {"token": payment_mandate}}]}
    return body


def complete(client, checkout_id: str, body: dict, key: str | None = None):
    return client.post(f"/ucp/v1/checkout-sessions/{checkout_id}/complete", body, key=key)


def error_code(resp) -> str:
    return resp.json()["messages"][0]["code"]


# --- cart (checkout session) ---


def test_create_empty_cart(client):
    checkout = client.create()
    assert checkout["status"] == "incomplete" and checkout["currency"] == "INR"
    assert checkout["line_items"] == [] and checkout["order"] is None
    assert totals_of(checkout) == {"subtotal": 0, "fulfillment": 0, "total": 0}
    assert checkout["metadata"]["talktobuy"] == {"item_count": 0, "out_of_stock": []}
    assert checkout["ucp"] == {"version": "2026-08-25"}


def test_scripted_cart_totals_101600(client):
    checkout = client.create(SCRIPTED_CART)
    totals = totals_of(checkout)
    assert totals == {"subtotal": 101600, "fulfillment": 0, "total": 101600}
    assert [t["type"] for t in checkout["totals"]].count("subtotal") == 1
    assert [t["type"] for t in checkout["totals"]].count("total") == 1
    assert checkout["metadata"]["talktobuy"]["item_count"] == 10
    milk = checkout["line_items"][0]
    assert milk["item"] == {"id": "p-0001", "title": "Nestlé a+ Toned Milk 1 L", "price": 6800}
    assert milk["quantity"] == 2
    assert milk["totals"] == [{"type": "subtotal", "amount": 13600}, {"type": "total", "amount": 13600}]


def test_every_response_has_valid_merchant_authorization(client):
    checkout = client.create(SCRIPTED_CART)
    fetched = client.get(f"/ucp/v1/checkout-sessions/{checkout['id']}").json()
    for c in (checkout, fetched):
        token = c["ap2"]["merchant_authorization"]
        header, payload, _sig = token.split(".")
        assert payload == ""
        assert merchant_auth.verify_checkout(c, token)
    tampered = {**fetched, "totals": [{"type": "total", "amount": 1}]}
    assert not merchant_auth.verify_checkout(tampered, fetched["ap2"]["merchant_authorization"])


def test_fulfillment_slots_and_selection(client):
    checkout = client.ready_cart()
    group = checkout["fulfillment"]["methods"][0]["groups"][0]
    assert group["selected_option_id"] == "slot-1800"
    slot = next(o for o in group["options"] if o["id"] == "slot-1800")
    assert slot["title"] == "6–7 pm"
    assert slot["metadata"]["label_hi"] == "शाम 6 से 7 बजे"
    assert slot["metadata"]["start"] == "2026-10-17T18:00:00+05:30"
    assert checkout["fulfillment"]["methods"][0]["line_item_ids"] == [li["id"] for li in checkout["line_items"]]
    # DEMO_CLOCK is 14:00 IST: today's 10 am and 12 pm slots are closed; tomorrow follows today.
    ids = [o["id"] for o in group["options"]]
    assert ids[:3] == ["slot-1600", "slot-1800", "slot-2000"] and ids[3] == "slot-d1-1000"


def test_earliest_resolves_to_first_open_slot(client):
    checkout = client.ready_cart(slot="earliest")
    assert checkout["fulfillment"]["methods"][0]["groups"][0]["selected_option_id"] == "slot-1600"


def test_put_changing_lines_returns_ready_session_to_incomplete(client):
    checkout = client.ready_cart()
    new_lines = [*SCRIPTED_CART, ("p-0011", 1)]
    resp = client.replace(checkout["id"], new_lines, slot="slot-1800")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "incomplete"
    assert body["fulfillment"]["methods"][0]["groups"][0]["selected_option_id"] is None
    assert len(body["line_items"]) == 11
    # line ids are stable across replacements
    assert [li["id"] for li in body["line_items"][:10]] == [li["id"] for li in checkout["line_items"]]


def test_put_without_slot_clears_selection(client):
    checkout = client.ready_cart()
    body = client.replace(checkout["id"], SCRIPTED_CART).json()
    assert body["status"] == "incomplete"


def test_selecting_slot_with_empty_cart_stays_incomplete(client):
    checkout = client.create()
    assert client.replace(checkout["id"], [], slot="slot-1800").json()["status"] == "incomplete"


def test_unknown_product_is_invalid_request(client):
    checkout = client.create()
    resp = client.replace(checkout["id"], [("p-9999", 1)])
    assert resp.status_code == 400 and error_code(resp) == "INVALID_REQUEST"


def test_unknown_slot_is_invalid_request(client):
    checkout = client.create(SCRIPTED_CART)
    resp = client.replace(checkout["id"], SCRIPTED_CART, slot="slot-0300")
    assert resp.status_code == 400 and error_code(resp) == "INVALID_REQUEST"


def test_out_of_stock_line_blocks_slot_selection(client):
    lines = [("p-0018", 1)]
    checkout = client.create(lines)
    assert checkout["metadata"]["talktobuy"]["out_of_stock"] == ["p-0018"]
    resp = client.replace(checkout["id"], lines, slot="slot-1800")
    assert resp.status_code == 400 and error_code(resp) == "OUT_OF_STOCK"
    assert "p-0018" in resp.json()["messages"][0]["content"]


def test_unknown_checkout_is_404(client):
    resp = client.get("/ucp/v1/checkout-sessions/chk_missing")
    assert resp.status_code == 404 and error_code(resp) == "RESOURCE_NOT_FOUND"


# --- complete (T061) ---


def test_complete_without_mandate(client):
    checkout = client.ready_cart()
    resp = complete(client, checkout["id"], {})
    assert resp.status_code == 402 and error_code(resp) == "mandate_required"
    issued = mint(checkout)
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, None))
    assert resp.status_code == 402 and error_code(resp) == "mandate_required"


def test_complete_scope_mismatch_when_lines_differ(client):
    checkout = client.ready_cart()
    issued = mint(checkout)
    changed = [*SCRIPTED_CART[:-1], ("p-0033", 1)]  # 8-inch tin instead of 7-inch
    client.replace(checkout["id"], changed)
    client.replace(checkout["id"], changed, slot="slot-1800")
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 402 and error_code(resp) == "mandate_scope_mismatch"


def test_complete_scope_mismatch_for_other_checkout(client):
    first = client.ready_cart()
    second = client.ready_cart()
    issued = mint(first)
    resp = complete(client, second["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 402 and error_code(resp) == "mandate_scope_mismatch"


def test_complete_expired_mandate(client):
    checkout = client.ready_cart()
    issued = mint(checkout, now=time.time() - 3600)
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 402 and error_code(resp) == "mandate_expired"


def test_complete_invalid_signature(client):
    checkout = client.ready_cart()
    issued = mint(checkout)
    # same claims, signed with a key that is not the demo mandate key
    payload = issued.checkout_mandate.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    rogue = jwk.JWK.generate(kty="EC", crv="P-256")
    token = jws.JWS(json.dumps(claims).encode())
    token.add_signature(rogue, alg="ES256", protected=json.dumps({"alg": "ES256"}))
    forged = token.serialize(compact=True)
    resp = complete(client, checkout["id"], complete_body(forged, issued.payment_mandate))
    assert resp.status_code == 402 and error_code(resp) == "mandate_invalid_signature"
    resp = complete(client, checkout["id"], complete_body("not-a-jws", issued.payment_mandate))
    assert error_code(resp) == "mandate_invalid_signature"


def test_complete_tampered_merchant_authorization(client):
    checkout = client.ready_cart()
    header, _, signature = checkout["ap2"]["merchant_authorization"].split(".")
    flipped = signature[:10] + ("A" if signature[10] != "A" else "B") + signature[11:]
    issued = mint(checkout, merchant_authorization=f"{header}..{flipped}")
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 402 and error_code(resp) == "merchant_authorization_invalid"


def test_complete_valid_mandate_places_test_order(client):
    checkout = client.ready_cart()
    issued = mint(checkout)
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 200, resp.text
    done = resp.json()
    assert done["status"] == "completed"
    order = done["order"]
    assert order["id"].startswith("ord_") and order["mode"] == "test"
    assert order["delivery"]["id"] == "slot-1800" and order["delivery"]["label_en"] == "6–7 pm"
    assert merchant_auth.verify_checkout(done, done["ap2"]["merchant_authorization"])

    last = client.raw.get("/demo/shoppers/u-ghanshyam/last-order").json()
    assert last["order_id"] == order["id"]
    assert [(line["product"]["id"], line["qty"]) for line in last["lines"]] == SCRIPTED_CART

    resp = client.replace(checkout["id"], SCRIPTED_CART)
    assert resp.status_code == 409 and error_code(resp) == "CHECKOUT_NOT_MODIFIABLE"


def test_complete_idempotent_replay_returns_same_order(client):
    checkout = client.ready_cart()
    issued = mint(checkout)
    body = complete_body(issued.checkout_mandate, issued.payment_mandate)
    first = complete(client, checkout["id"], body, key="idem-complete-1")
    replay = complete(client, checkout["id"], body, key="idem-complete-1")
    assert first.status_code == replay.status_code == 200
    assert replay.json()["order"]["id"] == first.json()["order"]["id"]
    assert replay.headers.get("Idempotent-Replayed") == "true"
    conflict = complete(client, checkout["id"], {**body, "extra": 1}, key="idem-complete-1")
    assert conflict.status_code == 409 and error_code(conflict) == "IDEMPOTENCY_CONFLICT"
    # a fresh key on a completed session is a 409, never a second order
    again = complete(client, checkout["id"], body)
    assert again.status_code == 409


def test_complete_requires_ready_status(client):
    checkout = client.create(SCRIPTED_CART)
    issued = mint(checkout)
    resp = complete(client, checkout["id"], complete_body(issued.checkout_mandate, issued.payment_mandate))
    assert resp.status_code == 409


def test_cancel(client):
    checkout = client.create(SCRIPTED_CART)
    resp = client.post(f"/ucp/v1/checkout-sessions/{checkout['id']}/cancel")
    assert resp.status_code == 200 and resp.json()["status"] == "canceled"
    again = client.post(f"/ucp/v1/checkout-sessions/{checkout['id']}/cancel")
    assert again.status_code == 409
    put = client.put(f"/ucp/v1/checkout-sessions/{checkout['id']}", lines_body(SCRIPTED_CART))
    assert put.status_code == 409 and error_code(put) == "CHECKOUT_NOT_MODIFIABLE"


# --- payment trusted surface (WebAuthn, end to end) ---


@pytest.fixture
def authenticator(client):
    device = SoftAuthenticator()
    options = client.raw.post("/payment/webauthn/register/options",
                              json={"shopper_id": "u-ghanshyam"}).json()
    resp = client.raw.post("/payment/webauthn/register/verify",
                           json={"shopper_id": "u-ghanshyam", "credential": device.register(options)})
    assert resp.json() == {"ok": True}, resp.text
    return device


def test_webauthn_approval_then_complete(client, authenticator):
    checkout = client.ready_cart()
    options = client.raw.post("/payment/webauthn/assert/options",
                              json={"shopper_id": "u-ghanshyam", "checkout_id": checkout["id"]}).json()
    expected = merchant_auth.b64url(merchant_auth.checkout_digest(checkout))
    assert options["challenge"] == expected

    resp = client.raw.post("/payment/approve", json={
        "shopper_id": "u-ghanshyam", "checkout_id": checkout["id"],
        "credential": authenticator.assert_(options)})
    assert resp.status_code == 200, resp.text
    approval = resp.json()
    assert set(approval) >= {"checkout_mandate", "payment_mandate", "expires_at"}

    resp = complete(client, checkout["id"],
                    complete_body(approval["checkout_mandate"], approval["payment_mandate"]))
    assert resp.status_code == 200 and resp.json()["status"] == "completed"


def test_webauthn_assertion_for_a_changed_cart_is_rejected(client, authenticator):
    checkout = client.ready_cart()
    options = client.raw.post("/payment/webauthn/assert/options",
                              json={"shopper_id": "u-ghanshyam", "checkout_id": checkout["id"]}).json()
    assertion = authenticator.assert_(options)
    changed = SCRIPTED_CART[:-1]
    client.replace(checkout["id"], changed)
    client.replace(checkout["id"], changed, slot="slot-1800")
    resp = client.raw.post("/payment/approve", json={
        "shopper_id": "u-ghanshyam", "checkout_id": checkout["id"], "credential": assertion})
    assert resp.status_code == 400 and error_code(resp) == "WEBAUTHN_FAILED"
