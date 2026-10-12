"""Complete and cancel (T066).

`complete` reads `ap2.checkout_mandate` and `payment.instruments[0].credential.token`, then checks,
in order: both present (`mandate_required`), both signatures (`mandate_invalid_signature`), expiry
(`mandate_expired`), that checkout id, hash, amount, currency and instrument match the current
session (`mandate_scope_mismatch`), and that the `merchant_authorization` the shopper approved is
the store's own signature over the current checkout (`merchant_authorization_invalid`). Only then
does it move `ready_for_complete → complete_in_progress → completed` and record a test-mode order.
"""

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from demo_store.ap2 import mandates, merchant_auth
from demo_store.checkout import totals
from demo_store.checkout.totals import Record
from demo_store.state import STATE
from demo_store.ucp.errors import (
    TERMINAL_STATUSES,
    CheckoutNotModifiableError,
    CheckoutStatus,
    MandateError,
    UcpError,
)


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    ap2: dict[str, Any] | None = None
    payment: dict[str, Any] | None = None


def _payment_instrument(body: CompleteRequest) -> tuple[str | None, str | None]:
    instruments = (body.payment or {}).get("instruments") or []
    if not instruments or not isinstance(instruments[0], dict):
        return None, None
    first = instruments[0]
    token = (first.get("credential") or {}).get("token") if isinstance(first.get("credential"), dict) else None
    return first.get("handler_id"), token


def verify_mandates(record: Record, body: CompleteRequest, now: float | None = None) -> dict:
    """Raise MandateError with the AP2 code on any failure; return the checkout mandate claims."""
    checkout_token = (body.ap2 or {}).get("checkout_mandate")
    handler_id, payment_token = _payment_instrument(body)
    if not checkout_token or not payment_token:
        raise MandateError("mandate_required", "a checkout mandate and a payment mandate are required")

    try:
        checkout_claims = mandates.verify(checkout_token)
        payment_claims = mandates.verify(payment_token)
    except mandates.InvalidSignature as exc:
        raise MandateError("mandate_invalid_signature", f"mandate signature invalid: {exc}") from None

    now = time.time() if now is None else now
    for claims in (checkout_claims, payment_claims):
        exp = claims.get("exp")
        if not isinstance(exp, int | float) or exp < now:
            raise MandateError("mandate_expired", "mandate has expired")

    current = totals.unsigned(record)
    current_hash = merchant_auth.checkout_hash(current)
    total = next(t["amount"] for t in current["totals"] if t["type"] == "total")
    amount = payment_claims.get("payment_amount") or {}
    scope_ok = (
        checkout_claims.get("checkout_id") == record["id"]
        and checkout_claims.get("checkout_hash") == current_hash
        and checkout_claims.get("amount") == total
        and checkout_claims.get("currency") == record["currency"]
        and payment_claims.get("checkout_hash") == current_hash
        and amount.get("amount") == total
        and amount.get("currency") == record["currency"]
        and payment_claims.get("payment_instrument") == mandates.PAYMENT_HANDLER
        and handler_id == mandates.PAYMENT_HANDLER
    )
    if not scope_ok:
        raise MandateError("mandate_scope_mismatch", "mandate does not match the current checkout")

    merchant_authorization = checkout_claims.get("merchant_authorization")
    if not isinstance(merchant_authorization, str) or not merchant_auth.verify_checkout(
        current, merchant_authorization
    ):
        raise MandateError("merchant_authorization_invalid", "merchant authorization is not ours")
    return checkout_claims


def complete_checkout(record: Record, body: CompleteRequest) -> dict:
    if record["status"] != CheckoutStatus.READY_FOR_COMPLETE:
        raise UcpError(f"checkout is {record['status']}, not ready_for_complete",
                       code="CHECKOUT_NOT_READY", status_code=409)
    claims = verify_mandates(record, body)

    record["status"] = CheckoutStatus.COMPLETE_IN_PROGRESS
    slot = totals.selected_slot(record)
    placed_at = datetime.now(UTC).isoformat(timespec="seconds")
    order_id = f"ord_{uuid.uuid4().hex[:16]}"
    record["order"] = {"id": order_id, "delivery": slot, "address": record.get("address"), "mode": "test",
                       "placed_at": placed_at}
    STATE.orders.append({
        "order_id": order_id,
        "shopper_id": claims.get("shopper_id") or "u-ghanshyam",
        "checkout_id": record["id"],
        "lines": [{"product_id": li["product_id"], "qty": li["quantity"]} for li in record["lines"]],
        "total_minor": totals.subtotal(record),
        "delivery_slot": slot,
        "address": record.get("address"),
        "placed_at": placed_at,
        "mode": "test",
    })
    record["status"] = CheckoutStatus.COMPLETED
    return totals.render(record)


def cancel_checkout(record: Record) -> dict:
    if record["status"] in TERMINAL_STATUSES:
        raise CheckoutNotModifiableError(f"checkout is {record['status']}")
    record["status"] = CheckoutStatus.CANCELED
    return totals.render(record)
