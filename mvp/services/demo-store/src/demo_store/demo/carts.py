"""The shopper's cart for the shop app (tap to add, check out without the assistant).

It is the same thing the assistant's cart is: a UCP checkout session. These endpoints are a plain
JSON door onto it for the browser (no UCP headers), so a cart filled by tapping and a cart filled
by voice are one cart. The assistant picks it up by its id.

  POST /demo/carts                  create (optionally with lines)
  GET  /demo/carts/{id}             read
  PUT  /demo/carts/{id}             replace the lines; optionally choose the delivery slot and address
  POST /demo/carts/{id}/complete    complete with the mandates from /payment/approve
  GET  /demo/slots                  today's and tomorrow's open delivery slots
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from demo_store.catalog.store import get_catalog, image_url
from demo_store.checkout import fulfillment, totals
from demo_store.checkout.complete import CompleteRequest, complete_checkout
from demo_store.checkout.routes import (
    CheckoutIn,
    DestinationIn,
    FulfillmentIn,
    ItemRef,
    LineItemIn,
    create_checkout,
    get_record,
    update_checkout,
)
from demo_store.state import STATE

router = APIRouter(prefix="/demo", tags=["demo"])

SHOPPER_ID = "u-ghanshyam"


class CartLineIn(BaseModel):
    product_id: str
    qty: int = Field(ge=0, le=100)


class CartIn(BaseModel):
    lines: list[CartLineIn] = Field(default_factory=list)
    slot_id: str | None = None
    address_id: str | None = None
    shopper_id: str = SHOPPER_ID


class MandateIn(BaseModel):
    checkout_mandate: str
    payment_mandate: str


class CompleteIn(BaseModel):
    mandate: MandateIn


def _slot(slot: dict | None) -> dict | None:
    return {"id": slot["id"], "label_hi": slot["label_hi"], "label_en": slot["label_en"]} if slot else None


def _address(a: dict | None) -> dict | None:
    if not a:
        return None
    return {"id": a["id"], "label": a["label"], "text": f"{a['line1']}, {a['area']}, {a['city']} {a['pincode']}"}


def view(record: dict[str, Any]) -> dict[str, Any]:
    """The cart in the shop's terms (whole rupees), shaped like the assistant's `cart` message."""
    catalog = get_catalog()
    lines = []
    for li in record["lines"]:
        p = catalog.get(li["product_id"])
        assert p is not None, li["product_id"]
        lines.append({
            "product": {
                "id": p.id, "name": p.name, "local_name": p.local_name, "size": p.size,
                "price": round(p.price_minor / 100), "image": image_url(p),
                "image_credit": p.image_credit, "in_stock": p.in_stock,
            },
            "qty": li["quantity"],
            "line_total": round(p.price_minor * li["quantity"] / 100),
        })
    order = record.get("order")
    return {
        "id": record["id"],
        "status": str(record["status"]),
        "lines": lines,
        "item_count": len(lines),
        "total": round(totals.subtotal(record) / 100),
        "slot": _slot(totals.selected_slot(record)),
        "address": _address(record.get("address")),
        "order": (
            {"id": order["id"], "delivery": _slot(order.get("delivery")), "address": _address(order.get("address"))}
            if order else None
        ),
    }


def _checkout_in(body: CartIn) -> CheckoutIn:
    return CheckoutIn(
        currency="INR",
        line_items=[LineItemIn(item=ItemRef(id=li.product_id), quantity=li.qty) for li in body.lines],
        fulfillment=FulfillmentIn(selected_option_id=body.slot_id) if body.slot_id else None,
        **({"destination": DestinationIn(shopper_id=body.shopper_id, address_id=body.address_id)} if body.address_id else {}),
    )


@router.post("/carts", status_code=201)
def create_cart(body: CartIn | None = None) -> dict:
    created = create_checkout(_checkout_in(body or CartIn()))
    with STATE.lock:
        return view(get_record(created["id"]))


@router.get("/carts/{cart_id}")
def read_cart(cart_id: str) -> dict:
    with STATE.lock:
        return view(get_record(cart_id))


@router.put("/carts/{cart_id}")
def replace_cart(cart_id: str, body: CartIn) -> dict:
    update_checkout(cart_id, _checkout_in(body))
    with STATE.lock:
        return view(get_record(cart_id))


@router.post("/carts/{cart_id}/complete")
def complete_cart(cart_id: str, body: CompleteIn) -> dict:
    with STATE.lock:
        record = get_record(cart_id)
        complete_checkout(record, CompleteRequest(
            ap2={"checkout_mandate": body.mandate.checkout_mandate},
            payment={"instruments": [{"handler_id": "com.example.card",
                                      "credential": {"token": body.mandate.payment_mandate}}]},
        ))
        return view(record)


@router.get("/slots")
def slots() -> list[dict]:
    return [
        {"id": o["id"], "label_hi": o["label_hi"], "label_en": o["label_en"], "start": o["start"], "end": o["end"]}
        for o in fulfillment.slot_options()
    ]
