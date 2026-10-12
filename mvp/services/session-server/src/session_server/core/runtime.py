"""Per-connection runtime state shared by the orchestrator, tool router and tools.

`session` is the persisted domain Session (mvp/contracts/domain.schema.json); everything else
here is in-memory only and dropped when the connection ends (FR-040).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from session_server.config import Settings
from session_server.models.domain import GoalList, Product, Session, Shopper
from session_server.ports.commerce import CheckoutView, CommercePort, UsualOrder
from session_server.ports.live import LivePort


class UiSink(Protocol):
    async def send_json(self, message: BaseModel | dict[str, Any]) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...


@dataclass
class Runtime:
    session: Session
    shopper: Shopper
    commerce: CommercePort
    live: LivePort
    ui: UiSink
    settings: Settings
    clock: Callable[[], float] = time.time

    products: dict[str, Product] = field(default_factory=dict)
    cart: CheckoutView | None = None
    line_sources: dict[str, str] = field(default_factory=dict)
    goals: dict[str, GoalList] = field(default_factory=dict)
    usual: UsualOrder | None = None
    goal_problems: dict[str, list[str]] = field(default_factory=dict)
    # add_to_cart calls already applied for the current shopper request (cleared on each new one);
    # stops the model double-adding when it repeats a tool call (seen in live rehearsal).
    turn_adds: set[tuple] = field(default_factory=set)
    camera_active: bool = False
    doctor_suggested: bool = False
    payment_future: asyncio.Future | None = None
    shopper_turn_text: str = ""
    background: set[asyncio.Task] = field(default_factory=set)

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self.background.add(task)
        task.add_done_callback(self.background.discard)
        return task

    def remember(self, products: list[Product]) -> None:
        for p in products:
            self.products[p.id] = p

    async def ensure_products(self, ids: list[str]) -> None:
        missing = [i for i in ids if i not in self.products]
        if missing:
            self.remember(await self.commerce.lookup(missing))
