"""CommercePort over UCP 2026-08-25 REST (T030). Wire format: mvp/contracts/store-api.md."""

import uuid
from typing import Any

import httpx

from session_server.config import Settings
from session_server.models.domain import FamilyContact, Product, Shopper
from session_server.ports.commerce import (
    Address,
    CartLineView,
    CheckoutView,
    CommerceError,
    SearchResult,
    Slot,
    UsualOrder,
)


def _product(raw: dict[str, Any]) -> Product:
    return Product.model_validate(raw["metadata"]["talktobuy"])


def _address(raw: dict[str, Any]) -> Address:
    return Address(id=raw["id"], label=raw.get("label", ""), name=raw.get("name", ""),
                   line1=raw.get("line1", ""), area=raw.get("area", ""), city=raw.get("city", ""),
                   pincode=raw.get("pincode", ""), phone=raw.get("phone", ""))


def _checkout(raw: dict[str, Any]) -> CheckoutView:
    lines = tuple(
        CartLineView(
            product_id=li["item"]["id"],
            qty=int(li["quantity"]),
            line_total_minor=next((t["amount"] for t in li.get("totals", []) if t["type"] == "total"), 0),
        )
        for li in raw.get("line_items", [])
    )
    totals = {t["type"]: t["amount"] for t in raw.get("totals", [])}
    meta = (raw.get("metadata") or {}).get("talktobuy") or {}
    slot = None
    for method in (raw.get("fulfillment") or {}).get("methods", []):
        for group in method.get("groups", []):
            selected = group.get("selected_option_id")
            for opt in group.get("options", []):
                if opt["id"] == selected:
                    m = opt.get("metadata") or {}
                    slot = Slot(id=opt["id"], label_hi=m.get("label_hi", opt.get("title", "")),
                                label_en=m.get("label_en", opt.get("title", "")))
    address = None
    for method in (raw.get("fulfillment") or {}).get("methods", []):
        for dest in method.get("destinations", []):
            if dest["id"] == method.get("selected_destination_id"):
                address = _address({"id": dest["id"], "name": dest.get("name", ""), **dest.get("address", {})})
    order = raw.get("order") or {}
    return CheckoutView(
        id=raw["id"],
        status=raw["status"],
        lines=lines,
        item_count=int(meta.get("item_count", len(lines))),
        total_minor=int(totals.get("total", 0)),
        slot=slot,
        order_id=order.get("id"),
        out_of_stock=tuple(meta.get("out_of_stock", [])),
        address=address,
    )


class UcpCommerce:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.profile = f'profile="{settings.session_server_url}/agent-profile.json"'
        self.http = client or httpx.AsyncClient(base_url=settings.store_base_url, timeout=10.0)

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"UCP-Agent": self.profile, "Request-Id": str(uuid.uuid4())}
        if method in ("POST", "PUT"):
            # The store requires Idempotency-Key on every POST/PUT (store-api.md); a fresh key
            # per call is correct because the session server never retries a mutation blindly.
            headers["Idempotency-Key"] = str(uuid.uuid4())
        resp = await self.http.request(method, path, json=body, headers=headers)
        if resp.status_code >= 400:
            try:
                msg = resp.json()["messages"][0]
                raise CommerceError(msg.get("code", "ERROR"), msg.get("content", resp.text), resp.status_code)
            except (ValueError, KeyError, IndexError):
                raise CommerceError("HTTP_ERROR", resp.text, resp.status_code) from None
        return resp.json()

    @staticmethod
    def _lines(lines: list[tuple[str, int]]) -> list[dict[str, Any]]:
        return [{"item": {"id": pid}, "quantity": qty} for pid, qty in lines]

    async def search(self, query: str, *, categories: list[str] | None = None,
                     max_price_minor: int | None = None, limit: int = 10) -> SearchResult:
        filters: dict[str, Any] = {}
        if categories:
            filters["categories"] = categories
        if max_price_minor:
            filters["price"] = {"min": 0, "max": max_price_minor}
        body = {"query": query, "filters": filters, "pagination": {"limit": limit}}
        raw = await self._call("POST", "/ucp/v1/catalog/search", body)
        meta = (raw.get("metadata") or {}).get("talktobuy") or {}
        return SearchResult([_product(p) for p in raw.get("products", [])], bool(meta.get("ambiguous")))

    async def lookup(self, ids: list[str]) -> list[Product]:
        raw = await self._call("POST", "/ucp/v1/catalog/lookup", {"ids": ids})
        return [_product(p) for p in raw.get("products", [])]

    async def create_cart(self, lines: list[tuple[str, int]]) -> CheckoutView:
        raw = await self._call("POST", "/ucp/v1/checkout-sessions",
                               {"currency": "INR", "line_items": self._lines(lines)})
        return _checkout(raw)

    async def get_cart(self, cart_id: str) -> CheckoutView:
        return _checkout(await self._call("GET", f"/ucp/v1/checkout-sessions/{cart_id}"))

    async def put_cart(self, cart_id: str, lines: list[tuple[str, int]], slot_id: str | None = None,
                       address_id: str | None = None, shopper_id: str | None = None) -> CheckoutView:
        body: dict[str, Any] = {"currency": "INR", "line_items": self._lines(lines),
                                "fulfillment": {"selected_option_id": slot_id} if slot_id else None}
        if address_id:  # omitted otherwise, so the store keeps the address already chosen
            body["destination"] = {"shopper_id": shopper_id, "address_id": address_id}
        return _checkout(await self._call("PUT", f"/ucp/v1/checkout-sessions/{cart_id}", body))

    async def complete(self, cart_id: str, mandate: dict[str, Any]) -> CheckoutView:
        body = {
            "ap2": {"checkout_mandate": mandate.get("checkout_mandate")},
            "payment": {"instruments": [{"handler_id": "com.example.card",
                                         "credential": {"token": mandate.get("payment_mandate")}}]},
        }
        return _checkout(await self._call("POST", f"/ucp/v1/checkout-sessions/{cart_id}/complete", body))

    async def cancel(self, cart_id: str) -> CheckoutView:
        return _checkout(await self._call("POST", f"/ucp/v1/checkout-sessions/{cart_id}/cancel", {}))

    async def shopper(self, shopper_id: str) -> Shopper:
        return Shopper.model_validate(await self._call("GET", f"/demo/shoppers/{shopper_id}"))

    async def addresses(self, shopper_id: str) -> list[Address]:
        raw = await self._call("GET", f"/demo/shoppers/{shopper_id}/addresses")
        return [_address(a) for a in raw]

    async def add_address(self, shopper_id: str, fields: dict[str, Any]) -> Address:
        return _address(await self._call("POST", f"/demo/shoppers/{shopper_id}/addresses", fields))

    async def last_order(self, shopper_id: str) -> UsualOrder | None:
        try:
            raw = await self._call("GET", f"/demo/shoppers/{shopper_id}/last-order")
        except CommerceError as exc:
            if exc.status == 404:
                return None
            raise
        return UsualOrder(raw["order_id"], [(Product.model_validate(_unwrap(li["product"])), int(li["qty"]))
                                           for li in raw.get("lines", [])])

    async def family(self, shopper_id: str) -> FamilyContact | None:
        try:
            return FamilyContact.model_validate(await self._call("GET", f"/demo/shoppers/{shopper_id}/family"))
        except CommerceError as exc:
            if exc.status == 404:
                return None
            raise

    async def notify_family(self, shopper_id: str, message: str) -> str:
        raw = await self._call("POST", "/demo/family/notifications",
                               {"shopper_id": shopper_id, "message": message})
        return raw["contact_name"]


def _unwrap(product: dict[str, Any]) -> dict[str, Any]:
    """Accept either a domain Product or a UCP product carrying metadata.talktobuy."""
    return product.get("metadata", {}).get("talktobuy", product) if "metadata" in product else product
