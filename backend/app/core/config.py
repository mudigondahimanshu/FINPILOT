"""Application settings — loaded from environment (.env). No secrets in code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core
    environment: str = Field(default="development")
    project_name: str = Field(default="FinPilot")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://finpilot:finpilot@localhost:5432/finpilot"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # Auth / JWT
    jwt_secret_key: str = Field(default="dev-only-change-me")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    # OAuth2 Google (dormant until credentials are supplied)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback"
    )

    # Where to send the browser after a successful OAuth login.
    frontend_url: str = Field(default="http://localhost:3000")

    # CORS allow-list (comma-separated in env)
    cors_origins: str = Field(default="http://localhost:3000")

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
