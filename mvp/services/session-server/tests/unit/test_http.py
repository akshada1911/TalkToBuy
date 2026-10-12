"""Tickets and app wiring (T034, S1): keyless demo ticket is origin-, rate- and cost-limited."""

import pytest
from fastapi.testclient import TestClient

from session_server.config import Settings, get_settings
from session_server.http import tickets
from session_server.main import app

SHOP = "http://localhost:5173"


@pytest.fixture
def client():
    settings = Settings(_env_file=None, shop_origin=SHOP, ticket_signing_secret="s3cret",
                        demo_admin_key="admin", max_concurrent_sessions=1, daily_session_quota=2)
    app.dependency_overrides[get_settings] = lambda: settings
    tickets._hits.clear()
    tickets.registry.active.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_ticket_round_trip_and_expiry() -> None:
    t = tickets.sign_ticket("u-ghanshyam", "k", ttl_s=10, now=1000)
    assert tickets.verify_ticket(t, "k", now=1005) == "u-ghanshyam"
    assert tickets.verify_ticket(t, "k", now=1011) is None
    assert tickets.verify_ticket(t, "other", now=1005) is None
    assert tickets.verify_ticket("garbage", "k") is None


def test_demo_ticket_requires_shop_origin(client) -> None:
    assert client.post("/v1/demo-ticket").status_code == 403
    assert client.post("/v1/demo-ticket", headers={"Origin": "https://evil.example"}).status_code == 403
    r = client.post("/v1/demo-ticket", headers={"Origin": SHOP})
    assert r.status_code == 200 and tickets.verify_ticket(r.json()["ticket"], "s3cret") == "u-ghanshyam"


def test_daily_quota_and_concurrency_caps(client) -> None:
    ok = {"Origin": SHOP}
    assert client.post("/v1/demo-ticket", headers=ok).status_code == 200
    assert client.post("/v1/demo-ticket", headers=ok).status_code == 200
    assert client.post("/v1/demo-ticket", headers=ok).status_code == 429  # quota of 2
    tickets.registry.active.add("busy")
    assert client.post("/v1/demo-ticket", headers=ok).status_code == 429


def test_kill_switch(client) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, shop_origin=SHOP,
                                                              demo_tickets_enabled=False)
    assert client.post("/v1/demo-ticket", headers={"Origin": SHOP}).status_code == 503


def test_admin_ticket_needs_key(client) -> None:
    assert client.post("/v1/tickets", json={"shopper_id": "u-x"}).status_code == 401
    r = client.post("/v1/tickets", json={"shopper_id": "u-x"}, headers={"X-Demo-Admin-Key": "admin"})
    assert r.status_code == 200


def test_session_refuses_without_gcp_project(client) -> None:
    good = tickets.sign_ticket("u-ghanshyam", get_settings().ticket_signing_secret)
    with client.websocket_connect(f"/v1/session?ticket={good}") as ws:
        msg = ws.receive_json()
    assert msg["code"] in {"not_configured", "bad_ticket"}


def test_forbidden_and_placeholder_projects_are_never_ready() -> None:
    assert not Settings(_env_file=None, gcp_project="zeroqueue-503710").gcp_ready
    assert not Settings(_env_file=None, gcp_project="REPLACE_WITH_TALKTOBUY_PROJECT_ID").gcp_ready
    assert not Settings(_env_file=None, gcp_project="").gcp_ready
    assert Settings(_env_file=None, gcp_project="talktobuy-demo").gcp_ready
