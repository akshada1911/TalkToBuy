"""Mapping from domain objects (paise) to UI and model-facing views (whole rupees)."""

from typing import Any

from session_server.models.domain import Product
from session_server.models.messages import (
    CardsMsg,
    CartMsg,
    StateMsg,
    UiCart,
    UiCartLine,
    AddressesMsg,
    UiAddress,
    UiDelivery,
    UiProduct,
)
from session_server.ports.commerce import Address, CheckoutView, Slot


def rupees(minor: int) -> int:
    return round(minor / 100)


def ui_product(p: Product) -> UiProduct:
    return UiProduct(
        id=p.id, name=p.name, local_name=p.local_name, size=p.size, price=rupees(p.price_minor),
        image=p.image, image_credit=p.image_credit, in_stock=p.in_stock,
    )


def ui_delivery(slot: Slot) -> UiDelivery:
    return UiDelivery(id=slot.id, label_hi=slot.label_hi, label_en=slot.label_en)


def ui_address(a: Address) -> UiAddress:
    return UiAddress(id=a.id, label=a.label, text=a.text)


def addresses_msg(addresses: list[Address]) -> AddressesMsg:
    return AddressesMsg(type="addresses", addresses=[ui_address(a) for a in addresses])


def ui_cart(view: CheckoutView, products: dict[str, Product]) -> UiCart:
    lines = [
        UiCartLine(product=ui_product(products[line.product_id]), qty=line.qty,
                   line_total=rupees(line.line_total_minor))
        for line in view.lines
        if line.product_id in products
    ]
    return UiCart(lines=lines, item_count=view.item_count, total=rupees(view.total_minor))


def cart_msg(view: CheckoutView, products: dict[str, Product]) -> CartMsg:
    return CartMsg(type="cart", cart=ui_cart(view, products))


def cards_msg(products: list[Product], mode: str) -> CardsMsg:
    return CardsMsg(type="cards", mode=mode, products=[ui_product(p) for p in products])


def state_msg(rt: Any) -> StateMsg:
    elapsed = rt.clock() - rt.session.started_at
    remaining = max(0, int(rt.settings.session_cap_s - elapsed))
    return StateMsg(
        type="state", pace=rt.session.pace, media_mode=rt.session.media_mode,
        safety_hold=rt.session.safety_hold, remaining_s=remaining,
    )


def model_product(p: Product) -> dict[str, Any]:
    """What the model sees about a product: the minimum it needs to speak and act, prices in
    whole rupees, and the listing as the only basis for explanations (FR-030). Kept small on
    purpose: every tool result is re-billed on each later turn of the Live session."""
    listing = {"description": p.listing.description}
    if p.listing.usage:
        listing["usage"] = p.listing.usage
    return {
        "id": p.id,
        "name": p.name,
        "local_name": p.local_name,
        "size": p.size,
        "price": rupees(p.price_minor),
        "in_stock": p.in_stock,
        "listing": listing,
    }


def model_cart(view: CheckoutView, products: dict[str, Product]) -> dict[str, Any]:
    return {
        "lines": [
            {
                "product_id": line.product_id,
                "name": products[line.product_id].name if line.product_id in products else None,
                "qty": line.qty,
            }
            for line in view.lines
        ],
        "item_count": view.item_count,
        "total": rupees(view.total_minor),
    }
