from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINSIGHT_", extra="ignore")

    environment: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "postgresql+asyncpg://finsight:finsight@localhost:5432/finsight"
    cors_origins: list[str] = ["http://localhost:5173"]
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    upload_max_bytes: int = 20 * 1024 * 1024
    allowed_upload_types: set[str] = Field(
        default={"application/pdf", "text/plain", "text/markdown", "text/csv"}
    )

    @field_validator("secret_key")
    @classmethod
    def secure_production_secret(cls, value: str, info):
        if info.data.get("environment") == "production" and value == "development-only-change-me":
            raise ValueError("FINSIGHT_SECRET_KEY must be configured in production")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

