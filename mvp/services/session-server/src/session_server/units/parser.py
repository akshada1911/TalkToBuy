"""Deterministic parser for spoken quantities ("paav kilo" → 250 g)."""

import re
from dataclasses import dataclass
from typing import Literal

from session_server.units.lexicon import (
    DEVANAGARI_DIGITS,
    FRACTIONS,
    NUMBERS,
    PAUNE,
    SAVA,
    UNITS,
)

BaseUnit = Literal["g", "ml", "piece", "pack"]

_TOKEN = re.compile(r"[0-9०-९]+(?:\.[0-9]+)?|[^\s0-9०-९.,।!?]+")


@dataclass(frozen=True)
class Amount:
    value: int
    unit: BaseUnit


def parse(phrase: str) -> Amount | None:
    """Parse a quantity phrase. Returns None if no quantity is recognised."""
    tokens = _TOKEN.findall(phrase.lower())
    value: float | None = None
    modifier: str | None = None
    unit: tuple[float, str] | None = None

    for tok in tokens:
        digits = tok.translate(DEVANAGARI_DIGITS)
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", digits):
            number = float(digits)
        elif tok in NUMBERS:
            number = NUMBERS[tok]
        else:
            number = None

        if number is not None:
            if modifier == "sava":
                number += 0.25
            elif modifier == "paune":
                number -= 0.25
            modifier = None
            value = number
        elif tok in FRACTIONS:
            value = FRACTIONS[tok]
        elif tok in SAVA:
            modifier = "sava"
        elif tok in PAUNE:
            modifier = "paune"
        elif tok in UNITS:
            unit = UNITS[tok]

    if value is None and modifier == "sava":
        value = 1.25
    elif value is None and modifier == "paune":
        value = 0.75

    if unit is None:
        if value is None:
            return None
        if value == 0.25:  # a bare "paav" means a quarter kilo
            return Amount(250, "g")
        if value != int(value):
            return None
        return Amount(int(value), "pack")

    multiplier, base = unit
    qty = (1 if value is None else value) * multiplier
    return Amount(round(qty), base)  # type: ignore[arg-type]
