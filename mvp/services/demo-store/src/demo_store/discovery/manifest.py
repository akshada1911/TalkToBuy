"""`GET /.well-known/ucp` business profile (T021)."""

from fastapi import APIRouter

from demo_store.ap2.keys import jwks
from demo_store.config import get_settings
from demo_store.ucp.errors import UCP_VERSION

router = APIRouter(tags=["discovery"])

SPEC = "https://ucp.dev/specification"
CAPABILITIES = [
    ("dev.ucp.shopping.checkout", None),
    ("dev.ucp.shopping.catalog.search", None),
    ("dev.ucp.shopping.catalog.lookup", None),
    ("dev.ucp.shopping.fulfillment", "dev.ucp.shopping.checkout"),
    ("dev.ucp.common.payment.ap2_mandate", "dev.ucp.shopping.checkout"),
]


def manifest() -> dict:
    base = get_settings().store_base_url.rstrip("/")
    capabilities = {
        name: [{"version": UCP_VERSION, "spec": f"{SPEC}/{name}", **({"extends": ext} if ext else {})}]
        for name, ext in CAPABILITIES
    }
    return {
        "ucp": {
            "version": UCP_VERSION,
            "services": {"dev.ucp.shopping": [{"version": UCP_VERSION, "transport": "rest",
                                               "endpoint": f"{base}/ucp/v1"}]},
            "capabilities": capabilities,
            "payment_handlers": {
                "com.example.card": [{"id": "com.example.card", "version": UCP_VERSION,
                                      "config": {"test_mode": True}}]
            },
        },
        **jwks(),
    }


@router.get("/.well-known/ucp")
def well_known() -> dict:
    return manifest()
