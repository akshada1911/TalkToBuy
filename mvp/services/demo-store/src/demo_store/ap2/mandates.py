"""Test-mode AP2 mandates (research R4 fallback).

The payment trusted surface issues two compact ES256 JWS tokens signed with the demo mandate key:

- checkout mandate: `{checkout_id, checkout_hash, amount, currency, approved_at, exp}` plus
  `shopper_id` and the `merchant_authorization` the shopper approved;
- payment mandate: `{transaction_id, payee, payment_amount:{amount, currency},
  payment_instrument:"com.example.card", checkout_hash, exp}`.

Upgrade path: the official AP2 format is an SD-JWT with key binding (`vct: mandate.checkout.1`,
`mandate.payment.1`) issued via the AP2 Python SDK from GitHub (never the unrelated PyPI `ap2`).
Only this module and `checkout/complete.py` would change.
"""

import json
import time
import uuid
from dataclasses import dataclass

from jwcrypto import jws
from jwcrypto.common import JWException

from demo_store.ap2.keys import mandate_key
from demo_store.config import get_settings

PAYMENT_HANDLER = "com.example.card"
PAYEE = "TalkToBuy Demo Store"


@dataclass
class IssuedMandates:
    checkout_mandate: str
    payment_mandate: str
    expires_at: int


def sign_claims(claims: dict, typ: str) -> str:
    key = mandate_key()
    token = jws.JWS(json.dumps(claims, separators=(",", ":")).encode())
    header = {"alg": "ES256", "kid": key["kid"], "typ": typ}
    token.add_signature(key, alg="ES256", protected=json.dumps(header))
    return token.serialize(compact=True)


def issue(checkout: dict, checkout_hash: str, shopper_id: str, now: float | None = None) -> IssuedMandates:
    """Issue both mandates for a merchant-authorised checkout."""
    now = int(now if now is not None else time.time())
    exp = now + get_settings().mandate_ttl_s
    total = next(t["amount"] for t in checkout["totals"] if t["type"] == "total")
    checkout_claims = {
        "checkout_id": checkout["id"],
        "checkout_hash": checkout_hash,
        "amount": total,
        "currency": checkout["currency"],
        "approved_at": now,
        "exp": exp,
        "shopper_id": shopper_id,
        "merchant_authorization": checkout["ap2"]["merchant_authorization"],
        "mode": "test",
    }
    payment_claims = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:16]}",
        "payee": PAYEE,
        "payment_amount": {"amount": total, "currency": checkout["currency"]},
        "payment_instrument": PAYMENT_HANDLER,
        "checkout_hash": checkout_hash,
        "iat": now,
        "exp": exp,
        "mode": "test",
    }
    return IssuedMandates(
        checkout_mandate=sign_claims(checkout_claims, "mandate.checkout+jws"),
        payment_mandate=sign_claims(payment_claims, "mandate.payment+jws"),
        expires_at=exp,
    )


class InvalidSignature(Exception):
    """The token is malformed or not signed by the demo mandate key."""


def verify(token: str) -> dict:
    """Verify a mandate signature and return its claims (expiry is checked by the caller)."""
    if not isinstance(token, str) or token.count(".") != 2:
        raise InvalidSignature("not a compact JWS")
    parsed = jws.JWS()
    try:
        parsed.deserialize(token)
        parsed.verify(mandate_key(), alg="ES256")
        claims = json.loads(parsed.payload)
    except (JWException, ValueError, TypeError) as exc:
        raise InvalidSignature(str(exc)) from exc
    if not isinstance(claims, dict):
        raise InvalidSignature("claims are not an object")
    return claims
