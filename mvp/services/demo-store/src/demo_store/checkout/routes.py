"""Checkout-session routes: the cart is a UCP checkout session (T049, T063)."""

import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from demo_store.catalog.store import get_catalog
from demo_store.checkout import fulfillment, totals
from demo_store.checkout.complete import CompleteRequest, cancel_checkout, complete_checkout
from demo_store.state import STATE
from demo_store.ucp.errors import (
    TERMINAL_STATUSES,
    CheckoutNotModifiableError,
    CheckoutStatus,
    InvalidRequestError,
    OutOfStockError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/ucp/v1/checkout-sessions", tags=["checkout"])

MAX_QUANTITY = 100


class ItemRef(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str


class LineItemIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    item: ItemRef
    quantity: int = Field(ge=0, le=MAX_QUANTITY)


class FulfillmentIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    selected_option_id: str | None = None


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    currency: str = "INR"
    line_items: list[LineItemIn] = Field(default_factory=list)
    fulfillment: FulfillmentIn | None = None


def _merge_lines(items: list[LineItemIn]) -> list[tuple[str, int]]:
    """(product_id, quantity) in first-seen order; duplicates summed, zero quantities dropped."""
    catalog = get_catalog()
    merged: dict[str, int] = {}
    for li in items:
        if catalog.get(li.item.id) is None:
            raise InvalidRequestError(f"unknown product {li.item.id}")
        merged[li.item.id] = merged.get(li.item.id, 0) + li.quantity
    if any(q > MAX_QUANTITY for q in merged.values()):
        raise InvalidRequestError(f"quantity above {MAX_QUANTITY}")
    return [(pid, q) for pid, q in merged.items() if q > 0]


def _apply(record: totals.Record, body: CheckoutIn) -> None:
    """Full replacement of lines and fulfillment selection (store-api.md PUT rules)."""
    if body.currency != "INR":
        raise InvalidRequestError("only INR is supported", code="INVALID_CURRENCY")
    lines = _merge_lines(body.line_items)
    old = [(li["product_id"], li["quantity"]) for li in record["lines"]]
    lines_changed = lines != old

    by_product = {li["product_id"]: li["id"] for li in record["lines"]}
    new_lines = []
    for pid, qty in lines:
        line_id = by_product.get(pid)
        if line_id is None:
            record["line_seq"] += 1
            line_id = f"li_{record['line_seq']}"
        new_lines.append({"id": line_id, "product_id": pid, "quantity": qty})

    options = fulfillment.slot_options()
    requested = body.fulfillment.selected_option_id if body.fulfillment else None
    selected = None
    if requested and not lines_changed:
        try:
            selected = fulfillment.resolve(requested, options)
        except KeyError:
            raise InvalidRequestError(f"unknown fulfillment option {requested}") from None
        catalog = get_catalog()
        missing = [catalog.get(pid) for pid, _ in lines if not catalog.get(pid).in_stock]
        if missing and new_lines:
            names = ", ".join(f"{p.name} ({p.id})" for p in missing)
            raise OutOfStockError(f"out of stock: {names}")

    record["lines"] = new_lines
    record["options"] = options
    # Changing line_items always clears the selection, returning the session to incomplete.
    record["selected_option_id"] = selected["id"] if selected else None
    record["status"] = totals.status_for(record)


def get_record(checkout_id: str) -> totals.Record:
    record = STATE.checkouts.get(checkout_id)
    if record is None:
        raise ResourceNotFoundError(f"checkout {checkout_id} not found")
    return record


@router.post("", status_code=201)
def create_checkout(body: CheckoutIn) -> dict[str, Any]:
    record: totals.Record = {
        "id": f"chk_{uuid.uuid4().hex[:20]}",
        "status": CheckoutStatus.INCOMPLETE,
        "currency": "INR",
        "lines": [],
        "line_seq": 0,
        "options": [],
        "selected_option_id": None,
        "order": None,
    }
    with STATE.lock:
        _apply(record, body)
        STATE.checkouts[record["id"]] = record
        return totals.render(record)


@router.get("/{checkout_id}")
def read_checkout(checkout_id: str) -> dict[str, Any]:
    with STATE.lock:
        return totals.render(get_record(checkout_id))


@router.put("/{checkout_id}")
def update_checkout(checkout_id: str, body: CheckoutIn) -> dict[str, Any]:
    with STATE.lock:
        record = get_record(checkout_id)
        if record["status"] in TERMINAL_STATUSES:
            raise CheckoutNotModifiableError(f"checkout is {record['status']}")
        draft = {**record, "lines": list(record["lines"])}
        _apply(draft, body)  # validate fully before mutating the stored record
        record.update(draft)
        return totals.render(record)


@router.post("/{checkout_id}/complete")
def complete(checkout_id: str, body: CompleteRequest) -> JSONResponse:
    with STATE.lock:
        record = get_record(checkout_id)
        return JSONResponse(complete_checkout(record, body))


@router.post("/{checkout_id}/cancel")
def cancel(checkout_id: str) -> dict[str, Any]:
    with STATE.lock:
        return cancel_checkout(get_record(checkout_id))
