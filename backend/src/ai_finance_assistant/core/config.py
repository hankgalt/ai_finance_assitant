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
    expected_dense_model_id: str = "BAAI/bge-small-en-v1.5"
    expected_dense_model_revision: str = "aa8f8b060edb00e03bfdd08813a2949946c8ba55"
    expected_dense_artifact_sha256: str = (
        "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"
    )
    expected_dense_dimensions: int = Field(default=384, gt=0)
    expected_sparse_model_id: str = "Qdrant/bm25"
    expected_sparse_model_revision: str = "22b8d2af71a76161e18dd432d2cee0eefa66e412"
    expected_sparse_artifact_sha256: str = (
        "019f104ba2ed07436d05f9cdd3383034ad66014edc27fc651f837e1a038b6451"
    )
    expected_chunking_policy_version: str = "structural-v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
