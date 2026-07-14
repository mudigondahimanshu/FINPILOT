"""Application settings — loaded from environment (.env). No secrets in code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
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

    # Phase 3 — AI Brain. All optional: the copilot answers keylessly without
    # them; setting any ONE (server-side) upgrades generation quality.
    groq_api_key: str = Field(default="")           # Groq free tier (recommended)
    gemini_api_key: str = Field(default="")         # Google AI Studio free tier
    anthropic_api_key: str = Field(default="")
    ollama_url: str = Field(default="")             # e.g. http://localhost:11434
    hf_api_key: str = Field(default="")             # HuggingFace Inference API key
    ml_models_dir: str = Field(default="/app/models")
    bandit_epsilon: float = Field(default=0.15)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_scheme(cls, v: str) -> str:
        """Accept Heroku/Render-style postgres:// URLs and force the async driver."""
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

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
