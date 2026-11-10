"""Local-safe configuration with environment-only secret loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings, SettingsConfigDict

_REQUIRED_ENVIRONMENT_VALUE = cast(str, PydanticUndefined)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIFA_",
        env_file=os.environ.get("AIFA_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "AI Finance Assistant API"
    app_version: str = "0.1.0"
    workflow_id: str = Field(
        default=_REQUIRED_ENVIRONMENT_VALUE,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        validation_alias=AliasChoices("AIFA_WORKFLOW_ID", "workflow_id"),
    )
    mode: Literal["local", "test", "production"] = "local"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    base_path: str = Field(default="/finance_assistant", pattern=r"^/[A-Za-z0-9_-]+$")
    identity_mode: Literal["loopback_development", "iap"] = "loopback_development"
    iap_audience: str | None = Field(default=None, min_length=1, max_length=512)
    iap_owner_email: str | None = Field(default=None, min_length=3, max_length=320)
    iap_viewer_emails: list[str] = Field(default_factory=list)
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
    provider_mode: Literal["credential_free", "live"] = "credential_free"
    market_data_provider: Literal["alpha_vantage", "massive"] = "alpha_vantage"
    alpha_vantage_api_key: SecretStr | None = None
    massive_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    alpha_vantage_terms_approved: bool = False
    massive_terms_approved: bool = False
    tavily_terms_approved: bool = False
    market_provider_request_budget: int = Field(default=5, ge=0, le=100)
    news_provider_request_budget: int = Field(default=3, ge=0, le=100)
    market_provider_requests_per_minute: int = Field(default=5, ge=1, le=600)
    news_provider_requests_per_minute: int = Field(default=10, ge=1, le=600)
    alpha_vantage_entitlement: str = Field(
        default="conditional-private-demo; verify account terms before live use",
        min_length=1,
        max_length=512,
    )
    massive_entitlement: str = Field(
        default=("conditional-owner-only-demo; verify business/display rights before sharing data"),
        min_length=1,
        max_length=512,
    )
    tavily_entitlement: str = Field(
        default="conditional-private-demo; third-party source rights remain separate",
        min_length=1,
        max_length=512,
    )
    model_mode: Literal["credential_free", "openai_live"] = "credential_free"
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AIFA_OPENAI_API_KEY",
            "OPENAI_API_KEY",
            "openai_api_key",
        ),
    )
    openai_model: str = Field(default="gpt-6.1-sol", min_length=1, max_length=128)
    openai_terms_approved: bool = False
    model_request_budget: int = Field(default=8, ge=1, le=24)
    model_maximum_attempts: int = Field(default=3, ge=1, le=3)
    model_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    model_maximum_input_characters: int = Field(default=40_000, ge=1_000, le=200_000)
    storage_path: Path = Path("data/ai_finance_assistant.sqlite3")
    storage_expected_schema_version: int = Field(default=4, ge=1, le=1000)
    local_deployment_audience: Literal["owner_only", "shared_demo", "public"] = "owner_only"
    local_admin_token: SecretStr | None = None
    session_retention_days: int = Field(default=30, ge=1, le=3650)
    portfolio_retention_days: int = Field(default=365, ge=1, le=3650)
    run_event_retention_days: int = Field(default=30, ge=1, le=3650)
    provider_cache_enabled: bool = True
    provider_cache_retention_permission: Literal["verified", "unverified"] = "unverified"
    provider_cache_owner_risk_accepted: bool = False
    provider_cache_retention_days: int = Field(default=3650, ge=1, le=3650)
    provider_cache_recent_tail_days: int = Field(default=7, ge=0, le=31)
    provider_cache_tail_refresh_seconds: int = Field(default=21_600, ge=60, le=604_800)
    provider_cache_memory_ttl_seconds: int = Field(default=300, ge=0, le=86_400)
    provider_cache_memory_max_entries: int = Field(default=128, ge=1, le=10_000)
    provider_cache_schema_version: str = Field(default="1", pattern=r"^1$")
    provider_cache_policy_version: str = Field(
        default="historical-daily-v1",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    response_cache_adapter: Literal["disabled", "in_memory", "redis"] = "disabled"
    response_cache_semantic_mode: Literal["disabled", "shadow", "serving"] = "shadow"
    response_cache_redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        min_length=1,
        max_length=512,
    )
    response_cache_index_name: str = Field(
        default="aifa_model_response_cache_v1",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$",
    )
    response_cache_ttl_seconds: int = Field(default=86_400, ge=1, le=86_400)
    response_cache_lookup_timeout_milliseconds: int = Field(default=100, ge=10, le=2_000)
    response_cache_minimum_similarity: float = Field(default=0.92, ge=0.0, le=1.0)
    response_cache_memory_max_entries: int = Field(default=1_000, ge=1, le=100_000)
    response_cache_schema_version: str = Field(default="1", pattern=r"^1$")
    response_cache_policy_version: str = Field(
        default="public-rag-evidence-bound-v2",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    api_run_deadline_seconds: int = Field(default=60, ge=5, le=300)
    api_sse_replay_limit: int = Field(default=1000, ge=1, le=10_000)
    observability_mode: Literal["disabled", "in_memory", "opentelemetry"] = "opentelemetry"
    otel_service_name: str = Field(
        default=_REQUIRED_ENVIRONMENT_VALUE,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
        validation_alias=AliasChoices("AIFA_OTEL_SERVICE_NAME", "otel_service_name"),
    )
    otel_export_enabled: bool = False
    otel_exporter_otlp_endpoint: str = Field(
        default="http://127.0.0.1:4318",
        min_length=1,
        max_length=512,
    )
    otel_metric_export_interval_millis: int = Field(default=60_000, ge=1_000, le=600_000)
    langsmith_tracing_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "AIFA_LANGSMITH_TRACING_ENABLED",
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING_V2",
            "langsmith_tracing_enabled",
        ),
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AIFA_LANGSMITH_API_KEY",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "langsmith_api_key",
        ),
    )
    langsmith_project: str = Field(
        default=_REQUIRED_ENVIRONMENT_VALUE,
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices(
            "AIFA_LANGSMITH_PROJECT",
            "LANGSMITH_PROJECT",
            "LANGCHAIN_PROJECT",
            "langsmith_project",
        ),
    )
    workflow_maximum_graph_hops: int = Field(default=16, ge=4, le=64)

    @model_validator(mode="after")
    def validate_identity_mode(self) -> Settings:
        if self.storage_expected_schema_version != 4:
            raise ValueError("runtime storage schema version must be 4")
        loopback_hosts = {"127.0.0.1", "::1", "localhost"}
        if self.identity_mode == "loopback_development":
            if self.mode == "production":
                raise ValueError("production mode requires IAP identity")
            if self.host not in loopback_hosts:
                raise ValueError("loopback development identity requires a loopback host")
        else:
            if self.iap_audience is None or self.iap_owner_email is None:
                raise ValueError("IAP identity requires its audience and owner email")
        normalized = [email.strip().lower() for email in self.iap_viewer_emails]
        if any("@" not in email for email in normalized):
            raise ValueError("IAP viewer emails must be valid email-like identifiers")
        if len(set(normalized)) != len(normalized):
            raise ValueError("IAP viewer emails must be unique")
        self.iap_viewer_emails = normalized
        if self.iap_owner_email is not None:
            self.iap_owner_email = self.iap_owner_email.strip().lower()
            if "@" not in self.iap_owner_email:
                raise ValueError("IAP owner email must be a valid email-like identifier")
            if self.iap_owner_email in normalized:
                raise ValueError("IAP owner email cannot also be a viewer email")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
