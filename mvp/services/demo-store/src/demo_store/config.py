"""Demo store settings, read from the environment (and mvp/.env when present)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[2]
MVP_DIR = SERVICE_DIR.parents[1]
DEFAULT_DATA_DIR = SERVICE_DIR / "data"

# The gcloud default project on the dev machines. It belongs to another product and must never
# be used by TalkToBuy, even by accident.
FORBIDDEN_GCP_PROJECTS = {"zeroqueue-503710"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=MVP_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    store_base_url: str = "http://localhost:3000"
    shop_origin: str = "http://localhost:5173"
    search_mode: str = "live"
    demo_admin_key: str = ""
    data_dir: Path = DEFAULT_DATA_DIR
    store_signing_key_pem: str = ""
    mandate_signing_key_pem: str = ""
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "TalkToBuy demo shop"
    gcp_project: str = ""
    gcp_location: str = "us-central1"
    # Optional fixed "now" (ISO 8601) for rehearsals and tests; empty = real clock.
    demo_clock: str = ""
    mandate_ttl_s: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()


def gcp_project_or_none(settings: Settings | None = None) -> str | None:
    """Return the configured TalkToBuy GCP project, or None when Google calls must not happen."""
    project = (settings or get_settings()).gcp_project.strip()
    if not project or project.startswith("REPLACE_") or project in FORBIDDEN_GCP_PROJECTS:
        return None
    return project
