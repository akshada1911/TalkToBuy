"""Delivery addresses: the shopper's saved ones (seed) plus any added during the demo."""

import re
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from demo_store.state import STATE
from demo_store.ucp.errors import ResourceNotFoundError

_PINCODE = re.compile(r"^[1-9][0-9]{5}$")


class AddressIn(BaseModel):
    """A new address. Pincode is 6 digits; phone is a 10-digit Indian mobile number."""

    label: str = Field(default="", max_length=40)
    name: str = Field(min_length=1, max_length=80)
    line1: str = Field(min_length=1, max_length=160)
    area: str = Field(min_length=1, max_length=80)
    city: str = Field(min_length=1, max_length=80)
    pincode: str
    phone: str

    @field_validator("name", "line1", "area", "city", "label")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("pincode")
    @classmethod
    def _pincode(cls, v: str) -> str:
        v = v.strip()
        if not _PINCODE.match(v):
            raise ValueError("pincode must be 6 digits")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = re.sub(r"[\s\-]", "", v)
        digits = re.sub(r"^(\+91|0)", "", digits)
        if not re.fullmatch(r"[6-9][0-9]{9}", digits):
            raise ValueError("phone must be a 10-digit mobile number")
        return digits


def saved(shopper_id: str, seeded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with STATE.lock:
        return [*seeded, *STATE.addresses.get(shopper_id, [])]


def add(shopper_id: str, body: AddressIn, seeded: list[dict[str, Any]]) -> dict[str, Any]:
    with STATE.lock:
        existing = saved(shopper_id, seeded)
        record = {"id": f"addr-{uuid.uuid4().hex[:8]}", **body.model_dump()}
        record["label"] = record["label"] or f"Address {len(existing) + 1}"
        STATE.addresses.setdefault(shopper_id, []).append(record)
        return record


def find(shopper_id: str, address_id: str, seeded: list[dict[str, Any]]) -> dict[str, Any]:
    for a in saved(shopper_id, seeded):
        if a["id"] == address_id:
            return a
    raise ResourceNotFoundError(f"address {address_id} not found")
