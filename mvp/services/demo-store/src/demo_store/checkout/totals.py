"""Checkout records and their UCP rendering (T049).

A record is the store's internal view of a checkout session. `render()` produces the wire
Checkout of `mvp/contracts/store-api.md`, signed with `ap2.merchant_authorization`.
"""

from typing import Any

from demo_store.ap2 import merchant_auth
from demo_store.catalog.store import get_catalog
from demo_store.checkout import fulfillment
from demo_store.ucp.errors import UCP_VERSION, CheckoutStatus

Record = dict[str, Any]


def line_amount(product_id: str, quantity: int) -> int:
    product = get_catalog().get(product_id)
    assert product is not None, product_id
    return product.price_minor * quantity


def subtotal(record: Record) -> int:
    return sum(line_amount(li["product_id"], li["quantity"]) for li in record["lines"])


def status_for(record: Record) -> CheckoutStatus:
    if record["lines"] and record["selected_option_id"]:
        return CheckoutStatus.READY_FOR_COMPLETE
    return CheckoutStatus.INCOMPLETE


def selected_slot(record: Record) -> dict | None:
    return next((o for o in record["options"] if o["id"] == record["selected_option_id"]), None)


def out_of_stock(record: Record) -> list[str]:
    catalog = get_catalog()
    return [li["product_id"] for li in record["lines"] if not catalog.get(li["product_id"]).in_stock]


def unsigned(record: Record) -> dict:
    """The wire Checkout without `ap2` (exactly the bytes that get signed and hashed)."""
    catalog = get_catalog()
    line_items = []
    for li in record["lines"]:
        product = catalog.get(li["product_id"])
        amount = product.price_minor * li["quantity"]
        line_items.append({
            "id": li["id"],
            "item": {"id": product.id, "title": product.name, "price": product.price_minor},
            "quantity": li["quantity"],
            "totals": [{"type": "subtotal", "amount": amount}, {"type": "total", "amount": amount}],
        })
    sub = sum(li["totals"][0]["amount"] for li in line_items)
    return {
        "ucp": {"version": UCP_VERSION},
        "id": record["id"],
        "status": str(record["status"]),
        "currency": record["currency"],
        "line_items": line_items,
        "totals": [
            {"type": "subtotal", "amount": sub},
            {"type": "fulfillment", "amount": 0},
            {"type": "total", "amount": sub},
        ],
        "fulfillment": fulfillment.to_ucp(
            record["options"], record["selected_option_id"], [li["id"] for li in line_items]
        ),
        "links": [],
        "order": record.get("order"),
        "metadata": {
            "talktobuy": {"item_count": len(line_items), "out_of_stock": out_of_stock(record)}
        },
    }


def render(record: Record) -> dict:
    return merchant_auth.attach(unsigned(record))
