"""Configuratie uit omgevingsvariabelen (.env). Geen secrets in code."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production"] = "development"
    database_url: str = "postgresql+psycopg://flow:flow@localhost:5432/flow_social"

    config_dir: Path = REPO_ROOT / "config"
    templates_dir: Path = REPO_ROOT / "templates"
    seed_dir: Path = REPO_ROOT / "seed"
    storage_root: Path = REPO_ROOT / "data" / "storage"

    # Publieke basis-URL van de web-app, nodig voor de OAuth-redirect.
    public_url: str = "http://localhost:5173"
    session_secret: str = Field(default="", repr=False)

    # Allowlist: "email=rol" gescheiden door komma's, bijv. "a@x.nl=admin,b@x.nl=editor".
    allowlist: str = ""
    auth_mode: Literal["google", "dev"] = "google"
    google_client_id: str = ""
    google_client_secret: str = Field(default="", repr=False)

    render_url: str = "http://localhost:3001"
    # URL waarop de render-service (Chromium) assets uit storage kan ophalen.
    render_asset_base_url: str = "http://localhost:3001/storage"

    # Publiceren (docs/publiceren.md). 32 bytes, base64: openssl rand -base64 32
    token_encryption_key: str = Field(default="", repr=False)
    meta_app_id: str = ""
    meta_app_secret: str = Field(default="", repr=False)
    meta_graph_version: str = "v26.0"
    provider_timeout_seconds: float = 15.0
    # Sandbox-netwerk voor ontwikkeling en tests. Nooit aan in productie.
    allow_sandbox_provider: bool = False
    # Hoe lang een publieke beeld-URL voor Instagram geldig is.
    public_media_ttl_seconds: int = 1800

    def allowed_users(self) -> dict[str, str]:
        users: dict[str, str] = {}
        for entry in filter(None, (part.strip() for part in self.allowlist.split(","))):
            email, _, role = entry.partition("=")
            users[email.strip().lower()] = (role.strip() or "editor").lower()
        return users


@lru_cache
def get_settings() -> Settings:
    return Settings()
