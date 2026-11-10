"""Persistence-only operator configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PersistenceConfiguration(Protocol):
    workflow_id: str
    storage_backend: Literal["sqlite", "postgres"]
    storage_path: Path
    postgres_dsn: SecretStr | None
    postgres_pool_min_size: int
    postgres_pool_max_size: int
    postgres_connect_timeout_seconds: float
    storage_expected_schema_version: int
    response_cache_adapter: Literal["disabled", "in_memory", "redis"]
    session_retention_days: int
    portfolio_retention_days: int
    run_event_retention_days: int


class PersistenceOperatorSettings(BaseSettings):
    """Configuration required by migration, status, and retention jobs only."""

    model_config = SettingsConfigDict(
        env_prefix="AIFA_",
        env_file=os.environ.get("AIFA_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    workflow_id: str = Field(
        default="finance-assistant",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    storage_backend: Literal["sqlite", "postgres"] = "sqlite"
    storage_path: Path = Path("data/ai_finance_assistant.sqlite3")
    postgres_dsn: SecretStr | None = None
    postgres_pool_min_size: int = Field(default=1, ge=1, le=5)
    postgres_pool_max_size: int = Field(default=2, ge=1, le=20)
    postgres_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    postgres_schema: str = Field(default="public", min_length=1, max_length=63)
    postgres_runtime_role: str | None = Field(default=None, min_length=1, max_length=63)
    postgres_retention_role: str | None = Field(default=None, min_length=1, max_length=63)
    storage_expected_schema_version: int = Field(default=4, ge=1, le=1000)
    response_cache_adapter: Literal["disabled", "in_memory", "redis"] = "disabled"
    session_retention_days: int = Field(default=30, ge=1, le=3650)
    portfolio_retention_days: int = Field(default=365, ge=1, le=3650)
    run_event_retention_days: int = Field(default=30, ge=1, le=3650)

    @model_validator(mode="after")
    def validate_storage(self) -> PersistenceOperatorSettings:
        if self.storage_expected_schema_version != 4:
            raise ValueError("operator storage schema version must be 4")
        if self.postgres_pool_min_size > self.postgres_pool_max_size:
            raise ValueError("PostgreSQL pool minimum cannot exceed its maximum")
        if self.storage_backend == "postgres" and self.postgres_dsn is None:
            raise ValueError("PostgreSQL storage requires a DSN")
        if self.storage_backend == "sqlite" and self.postgres_dsn is not None:
            raise ValueError("PostgreSQL DSN cannot be configured for SQLite storage")
        if (self.postgres_runtime_role is None) != (self.postgres_retention_role is None):
            raise ValueError("PostgreSQL runtime and retention roles must be configured together")
        if self.storage_backend == "sqlite" and self.postgres_runtime_role is not None:
            raise ValueError("PostgreSQL roles cannot be configured for SQLite storage")
        return self
