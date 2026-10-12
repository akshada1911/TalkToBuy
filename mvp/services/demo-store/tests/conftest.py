"""Shared fixtures: an isolated data dir, a fixed clock and a UCP-header-aware client."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))  # for `import support`
_TMP = Path(tempfile.mkdtemp(prefix="demo-store-test-"))
for name in ("catalog.json", "orders_seed.json"):
    shutil.copy(SERVICE_DIR / "data" / name, _TMP / name)

# Environment beats mvp/.env. No Google project: search must run lexical-only, never call Gemini.
os.environ.update({
    "DATA_DIR": str(_TMP),
    "GCP_PROJECT": "",
    "SEARCH_MODE": "live",
    "DEMO_ADMIN_KEY": "test-admin-key",
    "DEMO_CLOCK": "2026-10-17T14:00:00+05:30",
    "STORE_BASE_URL": "http://store.test",
    "SHOP_ORIGIN": "http://localhost:5173",
    "WEBAUTHN_RP_ID": "localhost",
    "STORE_SIGNING_KEY_PEM": "",
    "MANDATE_SIGNING_KEY_PEM": "",
})

from fastapi.testclient import TestClient  # noqa: E402
from support import UcpClient  # noqa: E402

from demo_store.main import app  # noqa: E402
from demo_store.state import STATE  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        STATE.reset()
        yield UcpClient(test_client)


@pytest.fixture
def search_mode(monkeypatch):
    """Switch SEARCH_MODE for one test."""
    from demo_store.config import get_settings

    def set_mode(mode: str) -> None:
        monkeypatch.setattr(get_settings(), "search_mode", mode)

    return set_mode
