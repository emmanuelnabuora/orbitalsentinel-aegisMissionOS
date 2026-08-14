"""Application settings.

All configuration flows through this module — never read os.environ elsewhere.
Settings are typed, validated at startup, and fail fast on misconfiguration.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_", env_file=".env", extra="ignore")

    # Runtime
    env: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "AEGIS MissionOS API"
    version: str = "0.1.0"

    # Security
    secret_key: str = Field(min_length=32, default="dev-only-secret-key-not-for-production!!")
    access_token_ttl_minutes: int = 15
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "aegis-missionos"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Data stores (no AEGIS_ prefix — shared with infra tooling)
    database_url: str = Field(
        default="postgresql+asyncpg://aegis:change-me-locally@localhost:5432/aegis",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    encryption_key: str | None = Field(default=None, alias="AEGIS_ENCRYPTION_KEY")
    oidc_issuer: str | None = Field(default=None, alias="AEGIS_OIDC_ISSUER")
    oidc_client_id: str | None = Field(default=None, alias="AEGIS_OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, alias="AEGIS_OIDC_CLIENT_SECRET")
    oidc_redirect_url: str | None = Field(default=None, alias="AEGIS_OIDC_REDIRECT_URL")
    oidc_auto_provision: bool = Field(default=False, alias="AEGIS_OIDC_AUTO_PROVISION")
    login_rate_limit: int = Field(default=10, alias="AEGIS_LOGIN_RATE_LIMIT")
    login_rate_window_seconds: int = Field(default=300, alias="AEGIS_LOGIN_RATE_WINDOW")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")

    # Live data ingestion (Phase 11)
    data_source: Literal["seed", "live"] = "seed"
    ingest_catalog_group: str = "active"

    # SentinelAI live provider (Phase 19). The key comes from the
    # environment (AWS Secrets Manager in deployment, ADR-0007 pattern);
    # ANTHROPIC_API_KEY is also honored for developer convenience.
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    sentinel_model: str = "claude-sonnet-5"
    sentinel_max_tokens: int = 1000

    @field_validator("secret_key")
    @classmethod
    def _forbid_default_secret_outside_local(cls, v: str, info) -> str:
        env = info.data.get("env", "local")
        if env in ("staging", "production") and v.startswith("dev-only-"):
            raise ValueError("AEGIS_SECRET_KEY must be set explicitly outside local/test")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
