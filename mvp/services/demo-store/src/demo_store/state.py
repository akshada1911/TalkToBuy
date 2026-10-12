"""In-memory runtime state: checkouts, orders, notifications and the idempotency cache.

The demo runs as a single Cloud Run instance, so process memory is enough; `/demo/reset` clears
everything except the seeded order. WebAuthn registrations persist to a git-ignored file so a
restart does not force re-registration.
"""

import json
import threading
from dataclasses import dataclass, field
from typing import Any

from demo_store.config import get_settings


@dataclass
class CachedResponse:
    fingerprint: str
    status: int
    body: bytes
    media_type: str


@dataclass
class State:
    lock: threading.RLock = field(default_factory=threading.RLock)
    checkouts: dict[str, dict[str, Any]] = field(default_factory=dict)
    orders: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    idempotency: dict[str, CachedResponse] = field(default_factory=dict)
    webauthn_challenges: dict[str, bytes] = field(default_factory=dict)
    credentials: dict[str, list[dict[str, Any]]] | None = None

    def reset(self) -> None:
        with self.lock:
            self.checkouts.clear()
            self.orders.clear()
            self.notifications.clear()
            self.idempotency.clear()
            self.webauthn_challenges.clear()

    # --- WebAuthn credentials (persisted) ---

    def _credentials_path(self):
        return get_settings().data_dir / "runtime" / "webauthn_credentials.json"

    def get_credentials(self, shopper_id: str) -> list[dict[str, Any]]:
        with self.lock:
            if self.credentials is None:
                path = self._credentials_path()
                self.credentials = json.loads(path.read_text("utf-8")) if path.exists() else {}
            return list(self.credentials.get(shopper_id, []))

    def save_credential(self, shopper_id: str, credential: dict[str, Any]) -> None:
        with self.lock:
            self.get_credentials(shopper_id)
            assert self.credentials is not None
            creds = [c for c in self.credentials.get(shopper_id, []) if c["id"] != credential["id"]]
            self.credentials[shopper_id] = [*creds, credential]
            path = self._credentials_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.credentials, indent=1), "utf-8")


STATE = State()
