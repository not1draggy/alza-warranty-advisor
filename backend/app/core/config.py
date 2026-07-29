"""Application configuration, loaded from environment variables only."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Core ---------------------------------------------------------------
    environment: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    secret_key: SecretStr = SecretStr("insecure-development-key")
    access_token_ttl_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    api_prefix: str = "/api/v1"
    project_name: str = "Warranty Advisor AI"

    # --- Database -----------------------------------------------------------
    postgres_user: str = "warranty"
    postgres_password: SecretStr = SecretStr("warranty")
    postgres_db: str = "warranty"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url_override: str | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Redis --------------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- LLM ----------------------------------------------------------------
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    llm_max_tokens: int = 8000
    llm_timeout_seconds: float = 180.0

    # --- Search -------------------------------------------------------------
    tavily_api_key: SecretStr | None = None
    serpapi_api_key: SecretStr | None = None
    google_search_api_key: SecretStr | None = None
    google_search_engine_id: str | None = None
    max_search_results: int = 24
    search_timeout_seconds: float = 25.0

    # --- Behaviour ----------------------------------------------------------
    analysis_cache_ttl_seconds: int = 60 * 60 * 24 * 7
    search_cache_ttl_seconds: int = 60 * 60 * 24
    rate_limit_per_minute: int = 30
    rate_limit_burst: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def secret(self, value: SecretStr | None) -> str | None:
        """Unwrap an optional secret, treating blank strings as unset."""
        if value is None:
            return None
        raw = value.get_secret_value().strip()
        return raw or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
