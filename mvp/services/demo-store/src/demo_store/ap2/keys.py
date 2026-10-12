"""ES256 signing keys: the store's merchant key and the demo mandate key.

Each key is loaded from a PEM in the environment (`STORE_SIGNING_KEY_PEM`,
`MANDATE_SIGNING_KEY_PEM`; Secret Manager in the cloud) or, in dev, generated once into a
git-ignored `data/*.pem` file.
"""

from functools import lru_cache
from pathlib import Path

from jwcrypto import jwk

from demo_store.config import get_settings


def _load_or_create(pem: str, path: Path) -> jwk.JWK:
    if pem.strip():
        key = jwk.JWK.from_pem(pem.replace("\\n", "\n").encode())
    elif path.exists():
        key = jwk.JWK.from_pem(path.read_bytes())
    else:
        key = jwk.JWK.generate(kty="EC", crv="P-256")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(key.export_to_pem(private_key=True, password=None))
    if key.get("crv") != "P-256":
        raise ValueError(f"{path.name}: ES256 needs a P-256 key")
    return key


def _with_kid(key: jwk.JWK, prefix: str) -> jwk.JWK:
    data = key.export(as_dict=True)
    data["kid"] = f"{prefix}-{key.thumbprint()[:16]}"
    return jwk.JWK(**data)


@lru_cache
def store_key() -> jwk.JWK:
    """The merchant key used for `ap2.merchant_authorization`."""
    settings = get_settings()
    key = _load_or_create(settings.store_signing_key_pem, settings.data_dir / "store_signing_key.pem")
    return _with_kid(key, "store")


@lru_cache
def mandate_key() -> jwk.JWK:
    """The demo key the payment trusted surface signs test-mode mandates with."""
    settings = get_settings()
    key = _load_or_create(settings.mandate_signing_key_pem, settings.data_dir / "mandate_signing_key.pem")
    return _with_kid(key, "mandate")


def public_jwk(key: jwk.JWK) -> dict:
    data = key.export_public(as_dict=True)
    return {**data, "use": "sig", "alg": "ES256"}


def jwks() -> dict:
    """The store's public JWK Set (merchant key first, then the demo mandate key)."""
    return {"keys": [public_jwk(store_key()), public_jwk(mandate_key())]}
