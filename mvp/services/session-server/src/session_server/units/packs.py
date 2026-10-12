"""Pack selection: fewest packs ≥ amount; smallest pack when below every pack (FR-025)."""

import math
from dataclasses import dataclass

from session_server.units.parser import Amount


@dataclass(frozen=True)
class PackOption:
    product_id: str
    unit_qty: float
    unit: str  # "g" | "ml" | "piece"


def packs_needed(amount: Amount, option: PackOption) -> int | None:
    """Packs of this option needed to cover the amount, or None if units don't match."""
    if amount.unit == "pack":
        return max(1, amount.value)
    if amount.unit != option.unit or option.unit_qty <= 0:
        return None
    return max(1, math.ceil(amount.value / option.unit_qty))


def plan(amount: Amount, options: list[PackOption]) -> list[tuple[str, int]]:
    """Return (product_id, qty) for every compatible option, best first.

    Best = fewest packs, then least overshoot, then original (relevance) order.
    """
    scored = []
    for rank, option in enumerate(options):
        packs = packs_needed(amount, option)
        if packs is None:
            continue
        overshoot = 0.0 if amount.unit == "pack" else packs * option.unit_qty - amount.value
        scored.append(((packs, overshoot, rank), (option.product_id, packs)))
    scored.sort(key=lambda item: item[0])
    return [choice for _, choice in scored]
