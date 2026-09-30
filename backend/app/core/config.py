from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vanco AI Document Intelligence"
    environment: str = "development"
    secret_key: str = "change-this-before-deploying"
    database_url: str = "postgresql+asyncpg://vanco:vanco@localhost:5432/vanco"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    upload_dir: str = "/app/storage"
    max_upload_bytes: int = 25 * 1024 * 1024
    access_token_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
