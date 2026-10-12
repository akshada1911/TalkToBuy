"""Hermetic in-process environment for cross-service tests: real demo store (ASGI) + real session
server tools and UCP client. No network, no Google Cloud."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

MVP = Path(__file__).resolve().parents[2]
STORE = MVP / "services" / "demo-store"
_TMP = Path(tempfile.mkdtemp(prefix="ttb-int-"))
for name in ("catalog.json", "orders_seed.json"):
    shutil.copy(STORE / "data" / name, _TMP / name)

os.environ.update({
    "TTB_NO_DOTENV": "1",
    "GCP_PROJECT": "",
    "DATA_DIR": str(_TMP),
    "SEARCH_MODE": "live",
    "DEMO_ADMIN_KEY": "test-admin-key",
    "DEMO_CLOCK": "2026-10-17T14:00:00+05:30",
    "STORE_BASE_URL": "http://store.test",
    "SHOP_ORIGIN": "http://localhost:5173",
    "WEBAUTHN_RP_ID": "localhost",
    "STORE_SIGNING_KEY_PEM": "",
    "MANDATE_SIGNING_KEY_PEM": "",
})
sys.path.insert(0, str(STORE / "tests"))  # SoftAuthenticator from the store's test support
