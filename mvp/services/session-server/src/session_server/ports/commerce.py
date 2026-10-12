"""CommercePort: catalogue, cart (checkout session), checkout and demo data."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from session_server.models.domain import FamilyContact, Product, Shopper


class CommerceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CartLineView:
    product_id: str
    qty: int
    line_total_minor: int


@dataclass(frozen=True)
class Slot:
    id: str
    label_hi: str
    label_en: str


@dataclass(frozen=True)
class Address:
    id: str
    label: str
    name: str
    line1: str
    area: str
    city: str
    pincode: str
    phone: str = ""

    @property
    def text(self) -> str:
        return f"{self.line1}, {self.area}, {self.city} {self.pincode}"


@dataclass(frozen=True)
class CheckoutView:
    id: str
    status: str
    lines: tuple[CartLineView, ...]
    item_count: int
    total_minor: int
    slot: Slot | None = None
    order_id: str | None = None
    out_of_stock: tuple[str, ...] = ()
    address: Address | None = None


@dataclass(frozen=True)
class SearchResult:
    products: list[Product]
    ambiguous: bool = False


@dataclass(frozen=True)
class UsualOrder:
    order_id: str
    lines: list[tuple[Product, int]] = field(default_factory=list)


class CommercePort(Protocol):
    async def search(
        self, query: str, *, categories: list[str] | None = None, max_price_minor: int | None = None,
        limit: int = 10,
    ) -> SearchResult: ...

    async def lookup(self, ids: list[str]) -> list[Product]: ...

    async def create_cart(self, lines: list[tuple[str, int]]) -> CheckoutView: ...

    async def get_cart(self, cart_id: str) -> CheckoutView: ...

    async def put_cart(
        self, cart_id: str, lines: list[tuple[str, int]], slot_id: str | None = None,
        address_id: str | None = None, shopper_id: str | None = None,
    ) -> CheckoutView:
        """Full replacement. Changing lines clears the slot (session back to incomplete).

        `address_id` (with `shopper_id`) sets the delivery address; leaving it out keeps the
        address already on the checkout."""
        ...

    async def complete(self, cart_id: str, mandate: dict[str, Any]) -> CheckoutView: ...

    async def cancel(self, cart_id: str) -> CheckoutView: ...

    async def shopper(self, shopper_id: str) -> Shopper: ...

    async def addresses(self, shopper_id: str) -> list[Address]:
        """The shopper's saved delivery addresses."""
        ...

    async def add_address(self, shopper_id: str, fields: dict[str, Any]) -> Address:
        """Save a new address (CommerceError INVALID_REQUEST if a field is invalid)."""
        ...

    async def last_order(self, shopper_id: str) -> UsualOrder | None: ...

    async def family(self, shopper_id: str) -> FamilyContact | None: ...

    async def notify_family(self, shopper_id: str, message: str) -> str:
        """Deliver an in-app family alert; returns the contact name."""
        ...
