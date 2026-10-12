"""Hermetic tests: never read mvp/.env and never configure a real Google Cloud project."""

import os

os.environ["TTB_NO_DOTENV"] = "1"
os.environ["GCP_PROJECT"] = ""
for var in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_APPLICATION_CREDENTIALS", "CLOUDSDK_CORE_PROJECT"):
    os.environ.pop(var, None)

import pytest  # noqa: E402

from session_server.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
