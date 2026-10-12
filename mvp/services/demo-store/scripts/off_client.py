"""Throttled Open Food Facts HTTP client shared by discover_off.py and import_off.py.

Politeness rules (research R5): User-Agent `TalkToBuy/0.1 (<OFF_CONTACT_EMAIL>)`, at most one
product read every 5 s, at least 7 s between search calls, exponential backoff on HTTP 503 or an
HTML body (OFF's overload page).
"""

import os
import time
from pathlib import Path

import httpx

MVP_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
PRODUCT_FIELDS = "code,product_name,brands,quantity,categories_tags,image_front_url,countries_tags"
SEARCH_URL = "https://search.openfoodfacts.org/search"


def contact_email() -> str:
    """Read OFF_CONTACT_EMAIL from the environment or mvp/.env."""
    email = os.environ.get("OFF_CONTACT_EMAIL", "")
    env_file = MVP_DIR / ".env"
    if not email and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("OFF_CONTACT_EMAIL="):
                email = line.split("=", 1)[1].strip().strip('"')
    if "@" not in email or email.startswith("REPLACE_"):
        raise SystemExit("OFF_CONTACT_EMAIL is not set (mvp/.env); OFF requires a contact.")
    return email


class OffClient:
    """Minimal throttled client. Raises nothing on failure; returns None instead."""

    def __init__(self, product_interval: float = 5.0, search_interval: float = 7.0,
                 budget_s: float = 25 * 60) -> None:
        self.http = httpx.Client(
            headers={"User-Agent": f"TalkToBuy/0.1 ({contact_email()})"}, timeout=30.0
        )
        self.product_interval = product_interval
        self.search_interval = search_interval
        self.started = time.monotonic()
        self.budget_s = budget_s
        self._last: dict[str, float] = {}
        self.failures = 0

    def over_budget(self) -> bool:
        return time.monotonic() - self.started > self.budget_s

    def _wait(self, kind: str, interval: float) -> None:
        elapsed = time.monotonic() - self._last.get(kind, 0.0)
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last[kind] = time.monotonic()

    def _get(self, kind: str, interval: float, url: str, params: dict) -> dict | None:
        delay = interval
        for _attempt in range(4):
            if self.over_budget():
                return None
            self._wait(kind, interval)
            try:
                resp = self.http.get(url, params=params)
            except httpx.HTTPError as exc:
                print(f"  ! {exc!r}")
                resp = None
            html = resp is not None and "html" in resp.headers.get("content-type", "")
            if resp is not None and resp.status_code == 200 and not html:
                return resp.json()
            if resp is not None and resp.status_code == 404:
                return None
            status = resp.status_code if resp is not None else "network"
            print(f"  ! OFF {status}{' (html)' if html else ''}; backing off {delay * 2:.0f}s")
            self.failures += 1
            time.sleep(delay * 2)
            delay *= 2
        return None

    def product(self, code: str) -> dict | None:
        data = self._get("product", self.product_interval, PRODUCT_URL.format(code=code),
                         {"fields": PRODUCT_FIELDS})
        if not data or data.get("status") != 1:
            return None
        return data.get("product")

    def search(self, term: str, page_size: int = 50) -> list[dict]:
        params = {
            "q": f'{term} countries_tags:"en:india"',
            "page_size": page_size,
            "fields": PRODUCT_FIELDS,
            "langs": "en",
        }
        data = self._get("search", self.search_interval, SEARCH_URL, params)
        return (data or {}).get("hits", [])
