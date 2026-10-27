"""Local-safe configuration with environment-only secret loading."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIFA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Finance Assistant API"
    app_version: str = "0.1.0"
    mode: Literal["local", "test", "production"] = "local"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"
    qdrant_url: str | None = None
    finance_collection_alias: str = "finance_education_active"
    tax_collection_alias: str = "tax_education_active"
    expected_payload_schema_version: str = "1"
    expected_dense_model_id: str | None = None
    expected_sparse_model_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
