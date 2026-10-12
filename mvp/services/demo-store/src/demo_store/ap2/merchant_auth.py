"""`ap2.merchant_authorization`: an ES256 detached JWS over the RFC 8785 canonical checkout.

The signed bytes are `JCS(checkout without "ap2")`. The token is a compact JWS with the payload
part removed (`header..signature`, RFC 7515 Appendix F). `checkout_hash` is the base64url SHA-256
of the same canonical bytes; the WebAuthn challenge is the raw SHA-256.
"""

import base64
import hashlib
import json

import rfc8785
from jwcrypto import jwk, jws
from jwcrypto.common import JWException

from demo_store.ap2.keys import store_key


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def canonical_checkout(checkout: dict) -> bytes:
    """RFC 8785 JCS bytes of the checkout with the `ap2` field excluded."""
    return rfc8785.dumps({k: v for k, v in checkout.items() if k != "ap2"})


def checkout_digest(checkout: dict) -> bytes:
    return hashlib.sha256(canonical_checkout(checkout)).digest()


def checkout_hash(checkout: dict) -> str:
    return b64url(checkout_digest(checkout))


def sign_detached(payload: bytes, key: jwk.JWK) -> str:
    token = jws.JWS(payload)
    token.add_signature(key, alg="ES256", protected=json.dumps({"alg": "ES256", "kid": key["kid"]}))
    header, _payload, signature = token.serialize(compact=True).split(".")
    return f"{header}..{signature}"


def verify_detached(detached: str, payload: bytes, key: jwk.JWK) -> bool:
    parts = detached.split(".") if isinstance(detached, str) else []
    if len(parts) != 3 or parts[1]:
        return False
    token = jws.JWS()
    try:
        token.deserialize(f"{parts[0]}.{b64url(payload)}.{parts[2]}")
        token.verify(key, alg="ES256")
    except (JWException, ValueError, TypeError):
        return False
    return True


def sign_checkout(checkout: dict) -> str:
    return sign_detached(canonical_checkout(checkout), store_key())


def verify_checkout(checkout: dict, merchant_authorization: str) -> bool:
    return verify_detached(merchant_authorization, canonical_checkout(checkout), store_key())


def attach(checkout: dict) -> dict:
    """Return the checkout with a fresh `ap2.merchant_authorization`."""
    return {**checkout, "ap2": {"merchant_authorization": sign_checkout(checkout)}}
