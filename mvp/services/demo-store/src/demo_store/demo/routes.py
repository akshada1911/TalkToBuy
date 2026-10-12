"""Demo-only (non-UCP) endpoints (T023, T090): shopper profile, usual order, family alerts, reset."""

import hmac
import json
import uuid
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from demo_store.catalog.store import get_catalog, to_ucp
from demo_store.demo import addresses
from demo_store.config import get_settings
from demo_store.models.domain import FamilyContact, Order, Shopper
from demo_store.state import STATE
from demo_store.ucp.errors import ResourceNotFoundError, UcpError

router = APIRouter(prefix="/demo", tags=["demo"])

MAX_MESSAGE = 280


@lru_cache
def seed() -> dict:
    raw = json.loads((get_settings().data_dir / "orders_seed.json").read_text("utf-8"))
    return {
        "shoppers": {s["id"]: Shopper.model_validate(s) for s in raw["shoppers"]},
        "family": {k: FamilyContact.model_validate(v) for k, v in raw["family"].items()},
        "orders": [Order.model_validate(o) for o in raw["orders"]],
        "addresses": raw.get("addresses", {}),
    }


def _shopper(shopper_id: str) -> Shopper:
    shopper = seed()["shoppers"].get(shopper_id)
    if shopper is None:
        raise ResourceNotFoundError(f"shopper {shopper_id} not found")
    return shopper


@router.get("/shoppers/{shopper_id}")
def get_shopper(shopper_id: str) -> dict:
    return _shopper(shopper_id).model_dump(mode="json")


@router.get("/shoppers/{shopper_id}/last-order")
def last_order(shopper_id: str) -> dict:
    _shopper(shopper_id)
    with STATE.lock:
        real = [o for o in STATE.orders if o["shopper_id"] == shopper_id]
    if real:
        order_id, lines = real[-1]["order_id"], real[-1]["lines"]
    else:
        seeded = [o for o in seed()["orders"] if o.shopper_id == shopper_id]
        if not seeded:
            raise ResourceNotFoundError(f"shopper {shopper_id} has no orders")
        order_id = seeded[-1].order_id
        lines = [line.model_dump() for line in seeded[-1].lines]
    catalog = get_catalog()
    return {
        "order_id": order_id,
        "lines": [
            {"product": to_ucp(catalog.get(line["product_id"])), "qty": line["qty"]}
            for line in lines
            if catalog.get(line["product_id"]) is not None
        ],
    }


def _family(shopper_id: str) -> FamilyContact:
    _shopper(shopper_id)
    contact = seed()["family"].get(shopper_id)
    if contact is None:
        raise ResourceNotFoundError(f"shopper {shopper_id} has no linked family contact")
    return contact


@router.get("/shoppers/{shopper_id}/family")
def family(shopper_id: str) -> dict:
    return _family(shopper_id).model_dump(mode="json")


def seeded_addresses(shopper_id: str) -> list[dict]:
    return list(seed()["addresses"].get(shopper_id, []))


def get_address(shopper_id: str, address_id: str) -> dict:
    """One saved address of this shopper (seeded or added); 404 if unknown."""
    _shopper(shopper_id)
    return addresses.find(shopper_id, address_id, seeded_addresses(shopper_id))


@router.get("/shoppers/{shopper_id}/addresses")
def list_addresses(shopper_id: str) -> list[dict]:
    _shopper(shopper_id)
    return addresses.saved(shopper_id, seeded_addresses(shopper_id))


@router.post("/shoppers/{shopper_id}/addresses", status_code=201)
def add_address(shopper_id: str, body: addresses.AddressIn) -> dict:
    _shopper(shopper_id)
    return addresses.add(shopper_id, body, seeded_addresses(shopper_id))


class NotificationIn(BaseModel):
    shopper_id: str
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)


@router.post("/family/notifications")
def notify_family(body: NotificationIn) -> dict:
    contact = _family(body.shopper_id)
    with STATE.lock:
        STATE.notifications.append({
            "id": f"n_{uuid.uuid4().hex[:12]}",
            "shopper_id": body.shopper_id,
            "contact_id": contact.id,
            "message": body.message,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        })
    return {"delivered": True, "contact_name": contact.name}


@router.get("/family/notifications")
def list_notifications(shopper_id: str = Query(...)) -> list[dict]:
    with STATE.lock:
        return [
            {"id": n["id"], "message": n["message"], "created_at": n["created_at"]}
            for n in STATE.notifications
            if n["shopper_id"] == shopper_id
        ]


@router.post("/reset")
def reset(x_demo_admin_key: str | None = Header(default=None)) -> dict:
    expected = get_settings().demo_admin_key
    if not expected or not x_demo_admin_key or not hmac.compare_digest(expected, x_demo_admin_key):
        raise UcpError("invalid or missing X-Demo-Admin-Key", code="UNAUTHORIZED", status_code=401)
    STATE.reset()
    return {"ok": True}
