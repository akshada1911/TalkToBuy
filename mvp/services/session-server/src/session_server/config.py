"""Settings for the session server (T025), read from env and mvp/.env.

Set TTB_NO_DOTENV=1 to ignore mvp/.env (tests do this so they never touch real projects).
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

MVP_ROOT = Path(__file__).resolve().parents[4]  # .../mvp

# Projects that must never be used for TalkToBuy (e.g. the gcloud default on a dev machine).
FORBIDDEN_GCP_PROJECTS = frozenset({"zeroqueue-503710"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if os.environ.get("TTB_NO_DOTENV") == "1" else MVP_ROOT / ".env",
        extra="ignore",
    )

    gcp_project: str = ""
    gcp_location: str = "us-central1"
    live_model: str = "gemini-3.8-live"
    flash_model: str = "gemini-2.5-flash"  # verified on talktobuy/us-central1 (3.x Flash IDs 404)
    avatar_name: str = "Kai"
    voice_name: str = "Charon"
    firestore_database: str = "(default)"

    store_base_url: str = "http://localhost:3000"
    session_server_url: str = "http://localhost:8080"
    shop_origin: str = "http://localhost:5173"

    commerce_adapter: str = "ucp"
    # memory = in-process (local dev); firestore = Cloud Run (needs the Firestore API enabled)
    state_backend: str = "memory"
    media_mode_default: str = "avatar"

    demo_admin_key: str = "change-me"
    ticket_signing_secret: str = "change-me-too"
    max_concurrent_sessions: int = 3
    daily_session_quota: int = 100
    demo_tickets_enabled: bool = True

    session_cap_s: int = 600
    session_warn_s: int = 540
    payment_timeout_s: int = 120

    @property
    def gcp_ready(self) -> bool:
        """True only for an explicit, allowed TalkToBuy project. Never falls back to gcloud."""
        p = self.gcp_project.strip()
        return bool(p) and not p.startswith("REPLACE_") and p not in FORBIDDEN_GCP_PROJECTS

    def require_gcp(self) -> str:
        if not self.gcp_ready:
            raise RuntimeError(
                "GCP_PROJECT must be set to the dedicated TalkToBuy project "
                "(placeholders and the gcloud default project are refused)."
            )
        return self.gcp_project.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
