"""Discovery manifest, UCP middleware and the demo endpoints (T021-T023, T090)."""

from jwcrypto import jwk
from support import SCRIPTED_CART, lines_body

from demo_store.ap2 import merchant_auth
from demo_store.models.domain import FamilyContact, Shopper

ADMIN = {"X-Demo-Admin-Key": "test-admin-key"}


def test_manifest(client):
    body = client.raw.get("/.well-known/ucp").json()
    ucp = body["ucp"]
    assert ucp["version"] == "2026-08-25"
    assert set(ucp["capabilities"]) == {
        "dev.ucp.shopping.checkout", "dev.ucp.shopping.catalog.search",
        "dev.ucp.shopping.catalog.lookup", "dev.ucp.shopping.fulfillment",
        "dev.ucp.common.payment.ap2_mandate",
    }
    service = ucp["services"]["dev.ucp.shopping"][0]
    assert service["transport"] == "rest" and service["endpoint"] == "http://store.test/ucp/v1"
    assert "com.example.card" in ucp["payment_handlers"]
    keys = body["keys"]
    assert keys and all(k["kty"] == "EC" and k["crv"] == "P-256" and k["alg"] == "ES256" for k in keys)
    assert all("d" not in k for k in keys)  # public keys only


def test_merchant_authorization_verifies_with_published_key(client):
    checkout = client.create(SCRIPTED_CART)
    published = jwk.JWK(**client.raw.get("/.well-known/ucp").json()["keys"][0])
    assert merchant_auth.verify_detached(
        checkout["ap2"]["merchant_authorization"], merchant_auth.canonical_checkout(checkout), published)


def test_idempotency_replay_and_conflict(client):
    body = lines_body(SCRIPTED_CART)
    first = client.post("/ucp/v1/checkout-sessions", body, key="idem-create-1")
    replay = client.post("/ucp/v1/checkout-sessions", body, key="idem-create-1")
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    conflict = client.post("/ucp/v1/checkout-sessions", lines_body(SCRIPTED_CART[:2]), key="idem-create-1")
    assert conflict.status_code == 409
    assert conflict.json()["messages"][0]["code"] == "IDEMPOTENCY_CONFLICT"


def test_idempotency_key_required_on_post(client):
    resp = client.raw.post("/ucp/v1/checkout-sessions", json=lines_body([]),
                           headers={"UCP-Agent": 'profile="x"', "Request-Id": "r"})
    assert resp.status_code == 400
    assert "Idempotency-Key" in resp.json()["messages"][0]["content"]


def test_shopper_profile(client):
    body = client.raw.get("/demo/shoppers/u-ghanshyam").json()
    assert body == {"id": "u-ghanshyam", "display_name": "Ghanshyam ji", "language": "hi",
                    "address_form": "respectful_male"}
    Shopper.model_validate(body)
    assert client.raw.get("/demo/shoppers/u-nobody").status_code == 404


def test_seeded_last_order_contains_usual_atta(client):
    body = client.raw.get("/demo/shoppers/u-ghanshyam/last-order").json()
    assert body["order_id"] == "ord_seed_ghanshyam_0001"
    ids = [line["product"]["id"] for line in body["lines"]]
    assert "p-0003" in ids
    atta = body["lines"][ids.index("p-0003")]
    assert atta["qty"] == 1 and atta["product"]["metadata"]["talktobuy"]["unit_qty"] == 5000


def test_family_contact_and_notifications(client):
    contact = client.raw.get("/demo/shoppers/u-ghanshyam/family").json()
    assert contact == {"id": "f-rohit", "name": "Rohit (son)", "channel": "in_app"}
    FamilyContact.model_validate(contact)

    resp = client.raw.post("/demo/family/notifications",
                           json={"shopper_id": "u-ghanshyam", "message": "पापा गिर गए हैं, कृपया फ़ोन करें।"})
    assert resp.json() == {"delivered": True, "contact_name": "Rohit (son)"}
    listed = client.raw.get("/demo/family/notifications", params={"shopper_id": "u-ghanshyam"}).json()
    assert len(listed) == 1 and set(listed[0]) == {"id", "message", "created_at"}

    too_long = client.raw.post("/demo/family/notifications",
                               json={"shopper_id": "u-ghanshyam", "message": "x" * 281})
    assert too_long.status_code == 400


def test_reset_requires_admin_key_and_clears_state(client):
    checkout = client.create(SCRIPTED_CART)
    client.raw.post("/demo/family/notifications", json={"shopper_id": "u-ghanshyam", "message": "hi"})
    assert client.raw.post("/demo/reset").status_code == 401
    assert client.raw.post("/demo/reset", headers={"X-Demo-Admin-Key": "wrong"}).status_code == 401
    assert client.raw.post("/demo/reset", headers=ADMIN).json() == {"ok": True}
    assert client.get(f"/ucp/v1/checkout-sessions/{checkout['id']}").status_code == 404
    assert client.raw.get("/demo/family/notifications", params={"shopper_id": "u-ghanshyam"}).json() == []
    last = client.raw.get("/demo/shoppers/u-ghanshyam/last-order").json()
    assert last["order_id"] == "ord_seed_ghanshyam_0001"


def test_static_placeholder_image(client):
    resp = client.raw.get("/static/products/p-0002.svg")
    assert resp.status_code == 200 and "svg" in resp.headers["content-type"]
