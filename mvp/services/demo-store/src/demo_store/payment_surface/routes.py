"""Payment trusted surface (T065), called by the shop app in the browser.

One-time WebAuthn platform-authenticator registration per shopper, then a per-checkout assertion
whose challenge is the SHA-256 of the merchant-authorised canonical checkout
(`JCS(checkout without ap2)`, the bytes `ap2.merchant_authorization` signs). A verified assertion
yields test-mode mandates (see `ap2/mandates.py`, research R4 fallback).
"""

import base64
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from demo_store.ap2 import mandates, merchant_auth
from demo_store.checkout import totals
from demo_store.checkout.routes import get_record
from demo_store.config import get_settings
from demo_store.state import STATE
from demo_store.ucp.errors import CheckoutStatus, InvalidRequestError, UcpError

router = APIRouter(prefix="/payment", tags=["payment"])


class ShopperIn(BaseModel):
    shopper_id: str


class RegisterVerifyIn(ShopperIn):
    credential: dict[str, Any]


class AssertOptionsIn(ShopperIn):
    checkout_id: str


class ApproveIn(AssertOptionsIn):
    credential: dict[str, Any]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _origins() -> list[str]:
    return [o.strip() for o in get_settings().shop_origin.split(",") if o.strip()]


def _ready_checkout(checkout_id: str) -> dict:
    record = get_record(checkout_id)
    if record["status"] != CheckoutStatus.READY_FOR_COMPLETE:
        raise UcpError(f"checkout is {record['status']}, not ready_for_complete",
                       code="CHECKOUT_NOT_READY", status_code=409)
    return record


@router.post("/webauthn/register/options")
def register_options(body: ShopperIn) -> dict:
    settings = get_settings()
    existing = STATE.get_credentials(body.shopper_id)
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_name=body.shopper_id,
        user_id=body.shopper_id.encode(),
        user_display_name=body.shopper_id,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=_unb64url(c["id"])) for c in existing],
    )
    with STATE.lock:
        STATE.webauthn_challenges[f"reg:{body.shopper_id}"] = options.challenge
    return json.loads(options_to_json(options))


@router.post("/webauthn/register/verify")
def register_verify(body: RegisterVerifyIn) -> dict:
    with STATE.lock:
        challenge = STATE.webauthn_challenges.pop(f"reg:{body.shopper_id}", None)
    if challenge is None:
        raise InvalidRequestError("no registration in progress for this shopper")
    settings = get_settings()
    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=_origins(),
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, KeyError, TypeError) as exc:
        raise InvalidRequestError(f"registration failed: {exc}", code="WEBAUTHN_FAILED") from None
    STATE.save_credential(body.shopper_id, {
        "id": _b64url(verified.credential_id),
        "public_key": _b64url(verified.credential_public_key),
        "sign_count": verified.sign_count,
    })
    return {"ok": True}


@router.post("/webauthn/assert/options")
def assert_options(body: AssertOptionsIn) -> dict:
    with STATE.lock:
        record = _ready_checkout(body.checkout_id)
        challenge = merchant_auth.checkout_digest(totals.unsigned(record))
    credentials = STATE.get_credentials(body.shopper_id)
    if not credentials:
        raise InvalidRequestError("shopper has no registered authenticator", code="NOT_REGISTERED")
    options = generate_authentication_options(
        rp_id=get_settings().webauthn_rp_id,
        challenge=challenge,
        allow_credentials=[PublicKeyCredentialDescriptor(id=_unb64url(c["id"])) for c in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(options))


@router.post("/approve")
def approve(body: ApproveIn) -> dict:
    with STATE.lock:
        record = _ready_checkout(body.checkout_id)
        checkout = totals.render(record)
    credential_id = body.credential.get("id") or body.credential.get("rawId")
    stored = next((c for c in STATE.get_credentials(body.shopper_id) if c["id"] == credential_id), None)
    if stored is None:
        raise InvalidRequestError("unknown credential for this shopper", code="WEBAUTHN_FAILED")
    settings = get_settings()
    try:
        verified = verify_authentication_response(
            credential=body.credential,
            expected_challenge=merchant_auth.checkout_digest(checkout),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=_origins(),
            credential_public_key=_unb64url(stored["public_key"]),
            credential_current_sign_count=stored["sign_count"],
            require_user_verification=True,
        )
    except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError) as exc:
        raise InvalidRequestError(f"approval failed: {exc}", code="WEBAUTHN_FAILED") from None
    STATE.save_credential(body.shopper_id, {**stored, "sign_count": verified.new_sign_count})

    issued = mandates.issue(checkout, merchant_auth.checkout_hash(checkout), body.shopper_id)
    return {
        "checkout_mandate": issued.checkout_mandate,
        "payment_mandate": issued.payment_mandate,
        "expires_at": datetime.fromtimestamp(issued.expires_at, UTC).isoformat(),
        "mode": "test",
    }
