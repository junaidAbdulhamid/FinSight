from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINSIGHT_", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://finsight:finsight@localhost:5432/finsight"
    cors_origins: list[str] = ["http://localhost:5173"]
    supabase_auth_enabled: bool = True
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=1200)
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    upload_max_bytes: int = 20 * 1024 * 1024
    allowed_upload_types: set[str] = Field(
        default={"application/pdf", "text/plain", "text/markdown", "text/csv"}
    )

    @model_validator(mode="after")
    def require_supabase_configuration(self):
        if self.supabase_auth_enabled and not (self.supabase_url and self.supabase_publishable_key):
            raise ValueError("Supabase auth is enabled; configure FINSIGHT_SUPABASE_URL and FINSIGHT_SUPABASE_PUBLISHABLE_KEY")
        if self.supabase_url:
            self.supabase_url = self.supabase_url.rstrip("/")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
