"""In-memory fakes for LivePort, CommercePort and UiSink, plus a runtime factory."""

import asyncio
import itertools
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from session_server.config import Settings
from session_server.core.runtime import Runtime
from session_server.models.domain import FamilyContact, Listing, Product, Session, Shopper, Usage
from session_server.ports import live as L
from session_server.ports.commerce import (
    Address,
    CartLineView,
    CheckoutView,
    CommerceError,
    SearchResult,
    Slot,
    UsualOrder,
)


def product(pid: str, name: str, local: str, size: str, qty: float, unit: str, paise: int,
            category: str, synonyms: list[str] | None = None, in_stock: bool = True,
            brand: str | None = None) -> Product:
    return Product(
        id=pid, name=name, local_name=local, brand=brand, size=size, unit_qty=qty, unit=unit,
        price_minor=paise, currency="INR", image=f"/static/products/{pid}.svg",
        image_credit="test", category=category, source_categories=[],
        listing=Listing(description=f"{name}.", usage=None), synonyms=synonyms or [],
        in_stock=in_stock,
    )


DEMO_PRODUCTS = [
    product("p-0112", "Toned Milk 1 L", "टोंड दूध", "1 L", 1000, "ml", 5400, "dairy", ["doodh", "dudh", "milk", "दूध"]),
    product("p-0113", "Toned Milk 500 ml", "टोंड दूध", "500 ml", 500, "ml", 2800, "dairy", ["doodh", "milk", "दूध"]),
    product("p-0007", "Tomatoes 250 g", "टमाटर", "250 g", 250, "g", 1000, "produce", ["tamatar", "tomato", "टमाटर"]),
    product("p-0201", "Chakki Atta 5 kg", "चक्की आटा", "5 kg", 5000, "g", 26500, "flours", ["aata", "atta", "आटा"], brand="Aashirvaad"),
    product("p-0300", "Glucose Biscuits", "ग्लूकोज़ बिस्कुट", "80 g", 1, "piece", 1000, "biscuits", ["parle-g", "biscuit", "बिस्कुट"], brand="Parle"),
    product("p-0401", "Maida 500 g", "मैदा", "500 g", 500, "g", 3500, "flours", ["maida", "मैदा"]),
    product("p-2051", "Cocoa Powder 50 g", "कोको पाउडर", "50 g", 50, "g", 6500, "baking", ["cocoa", "कोको"]),
    product("p-0501", "Butter 100 g", "मक्खन", "100 g", 100, "g", 6000, "dairy", ["butter", "makkhan", "मक्खन"], brand="Amul"),
    product("p-0601", "Condensed Milk 380 g", "कंडेंस्ड मिल्क", "380 g", 380, "g", 15000, "dairy", ["milkmaid", "condensed"], brand="Milkmaid"),
    product("p-0701", "Baking Powder 100 g", "बेकिंग पाउडर", "100 g", 100, "g", 4000, "baking", ["baking powder"]),
    product("p-0801", "Cake Tin 7 inch", "केक टिन", "7 inch", 1, "piece", 27200, "home", ["cake tin", "केक टिन"]),
    product("p-0999", "Paneer 200 g", "पनीर", "200 g", 200, "g", 9000, "dairy", ["paneer", "पनीर"], in_stock=False),
    product("p-0998", "Fresh Paneer 200 g", "ताज़ा पनीर", "200 g", 200, "g", 9500, "dairy", ["paneer", "पनीर"]),
]

ADDRESSES = [
    Address("addr-home", "Home", "Ghanshyam Sharma", "Flat 12, Shanti Apartments", "Kothrud", "Pune", "411038", "9876543210"),
    Address("addr-rohit", "Rohit's place", "Rohit Sharma", "B-204, Green Park", "Baner", "Pune", "411045", "9876501234"),
]

SLOT = Slot(id="slot-1800", label_hi="शाम 6 से 7 बजे", label_en="6–7 pm")


class FakeCommerce:
    def __init__(self, products: list[Product] | None = None):
        self.products = {p.id: p for p in (products or DEMO_PRODUCTS)}
        self.carts: dict[str, dict[str, Any]] = {}
        self.ids = itertools.count(1)
        self.calls: list[tuple[str, Any]] = []
        self.notifications: list[str] = []
        self.family_contact: FamilyContact | None = FamilyContact(id="f-1", name="Rohit (son)", channel="in_app")
        self.usual = UsualOrder("ord-seed", [(self.products["p-0201"], 1)])
        self.saved_addresses: list[Address] = list(ADDRESSES)

    def _view(self, cid: str) -> CheckoutView:
        cart = self.carts[cid]
        lines = tuple(CartLineView(pid, qty, self.products[pid].price_minor * qty) for pid, qty in cart["lines"].items())
        return CheckoutView(id=cid, status=cart["status"], lines=lines, item_count=len(lines),
                            total_minor=sum(line.line_total_minor for line in lines),
                            slot=SLOT if cart["slot"] else None, order_id=cart.get("order_id"),
                            address=cart.get("address"))

    async def search(self, query: str, *, categories=None, max_price_minor=None, limit=10) -> SearchResult:
        self.calls.append(("search", query))
        q = query.lower()
        hits = [p for p in self.products.values()
                if any(tok in " ".join([p.name.lower(), p.local_name, *p.synonyms]) for tok in q.split())]
        hits.sort(key=lambda p: not p.in_stock)
        return SearchResult(hits[:limit], ambiguous=False)

    async def lookup(self, ids: list[str]) -> list[Product]:
        return [self.products[i] for i in ids if i in self.products]

    async def create_cart(self, lines):
        cid = f"chk_{next(self.ids)}"
        self.carts[cid] = {"lines": dict(lines), "slot": None, "status": "incomplete"}
        self.calls.append(("create_cart", dict(lines)))
        return self._view(cid)

    async def get_cart(self, cart_id):
        return self._view(cart_id)

    async def put_cart(self, cart_id, lines, slot_id=None, address_id=None, shopper_id=None):
        cart = self.carts[cart_id]
        if cart["status"] in ("completed", "canceled"):
            raise CommerceError("CHECKOUT_NOT_MODIFIABLE", "terminal", 409)
        new_lines = dict(lines)
        if new_lines != cart["lines"]:
            cart["slot"] = None
        cart["lines"] = new_lines
        if address_id:
            cart["address"] = next(a for a in self.saved_addresses if a.id == address_id)
        if slot_id:
            oos = [self.products[p].name for p in new_lines if not self.products[p].in_stock]
            if oos:
                raise CommerceError("OUT_OF_STOCK", f"{oos[0]} is out of stock.")
            cart["slot"] = SLOT.id
        elif slot_id is None:
            cart["slot"] = None
        cart["status"] = "ready_for_complete" if cart["slot"] and new_lines else "incomplete"
        self.calls.append(("put_cart", (new_lines, slot_id)))
        return self._view(cart_id)

    async def complete(self, cart_id, mandate):
        cart = self.carts[cart_id]
        self.calls.append(("complete", mandate))
        if cart["status"] != "ready_for_complete":
            raise CommerceError("CHECKOUT_NOT_MODIFIABLE", "not ready", 409)
        if mandate.get("checkout_mandate") != "valid-test-mandate":
            raise CommerceError("mandate_invalid_signature", "bad mandate", 402)
        cart["status"] = "completed"
        cart["order_id"] = f"ord_{cart_id}"
        return self._view(cart_id)

    async def cancel(self, cart_id):
        self.carts[cart_id]["status"] = "canceled"
        return self._view(cart_id)

    async def shopper(self, shopper_id):
        return Shopper(id=shopper_id, display_name="Ghanshyam ji", language="hi", address_form="respectful_male")

    async def addresses(self, shopper_id):
        return list(self.saved_addresses)

    async def add_address(self, shopper_id, fields):
        if not str(fields.get("pincode", "")).isdigit() or len(str(fields["pincode"])) != 6:
            raise CommerceError("INVALID_REQUEST", "pincode must be 6 digits")
        a = Address(f"addr-new{len(self.saved_addresses)}", fields.get("label") or "New address",
                    fields["name"], fields["line1"], fields["area"], fields["city"], fields["pincode"],
                    fields["phone"])
        self.saved_addresses.append(a)
        return a

    async def last_order(self, shopper_id):
        return self.usual

    async def family(self, shopper_id):
        return self.family_contact

    async def notify_family(self, shopper_id, message):
        self.notifications.append(message)
        return self.family_contact.name if self.family_contact else ""


class FakeLive:
    """Scriptable LivePort: push events with `emit`, inspect what the server sent."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[L.LiveEvent | None] = asyncio.Queue()
        self.config: L.LiveConfig | None = None
        self.audio: list[bytes] = []
        self.video: list[bytes] = []
        self.audio_ends = 0
        self.texts: list[tuple[str, str]] = []
        self.tool_responses: list[tuple[str, str, dict[str, Any], str]] = []
        self.reconnects: list[str] = []
        self.closed = False

    async def connect(self, config):
        self.config = config

    async def reconnect(self, media_mode):
        self.reconnects.append(media_mode)

    async def events(self) -> AsyncIterator[L.LiveEvent]:
        while True:
            ev = await self.queue.get()
            if ev is None:
                return
            yield ev

    def emit(self, *events: L.LiveEvent | None) -> None:
        for ev in events:
            self.queue.put_nowait(ev)

    async def send_audio(self, pcm):
        self.audio.append(pcm)

    async def send_video(self, jpeg):
        self.video.append(jpeg)

    async def send_audio_end(self):
        self.audio_ends += 1

    async def send_text(self, text, *, role="user"):
        self.texts.append((role, text))

    async def send_tool_response(self, call_id, name, response, scheduling):
        self.tool_responses.append((call_id, name, response, scheduling))

    async def close(self):
        self.closed = True

    def response_for(self, call_id: str) -> dict[str, Any] | None:
        return next((r for cid, _, r, _ in self.tool_responses if cid == call_id), None)


class FakeUi:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.frames: list[bytes] = []

    async def send_json(self, message):
        self.messages.append(message.model_dump(mode="json") if isinstance(message, BaseModel) else message)

    async def send_bytes(self, data):
        self.frames.append(data)

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [m for m in self.messages if m.get("type") == kind]


def make_runtime(commerce: FakeCommerce | None = None, *, pace: str = "guided",
                 clock=None, settings: Settings | None = None) -> Runtime:
    import time

    s = Session(session_id="s-test", shopper_id="u-ghanshyam", started_at=time.time(), pace=pace,
                usage=Usage(audio_in_s=0, audio_out_s=0, video_in_s=0, tokens_in=0, tokens_out=0, est_cost_usd=0))
    rt = Runtime(
        session=s,
        shopper=Shopper(id="u-ghanshyam", display_name="Ghanshyam ji", language="hi", address_form="respectful_male"),
        commerce=commerce or FakeCommerce(), live=FakeLive(), ui=FakeUi(),
        settings=settings or Settings(_env_file=None, payment_timeout_s=2),
    )
    if clock is not None:
        rt.clock = clock
    return rt
