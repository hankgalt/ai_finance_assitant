"""Runtime configuration invariants that must fail before service initialization."""

import pytest
from pydantic import SecretStr, ValidationError

from ai_finance_assistant.core.config import Settings


def test_runtime_rejects_a_stale_application_schema_pin() -> None:
    with pytest.raises(ValidationError, match="runtime storage schema version must be 4"):
        Settings(storage_expected_schema_version=3)


def test_production_requires_managed_storage_and_operator_migrations() -> None:
    settings = Settings(
        mode="production",
        host="0.0.0.0",
        identity_mode="iap",
        iap_audience="/projects/123/global/backendServices/456",
        iap_owner_email="owner@example.com",
        storage_backend="postgres",
        postgres_dsn=SecretStr("postgresql://runtime.invalid/application"),
        storage_migration_mode="verify_only",
        retention_execution_mode="scheduled",
        qdrant_url="https://qdrant.invalid",
        qdrant_api_key=SecretStr("not-a-real-key"),
        response_cache_adapter="disabled",
    )

    assert settings.storage_backend == "postgres"
    assert settings.storage_migration_mode == "verify_only"
    assert settings.retention_execution_mode == "scheduled"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"storage_backend": "sqlite", "postgres_dsn": None}, "requires PostgreSQL"),
        ({"storage_migration_mode": "auto"}, "without applying DDL"),
        ({"retention_execution_mode": "startup"}, "scheduled job"),
        ({"response_cache_adapter": "in_memory"}, "response cache is disabled"),
    ],
)
def test_production_rejects_unapproved_runtime_state_modes(
    override: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        "mode": "production",
        "host": "0.0.0.0",
        "identity_mode": "iap",
        "iap_audience": "/projects/123/global/backendServices/456",
        "iap_owner_email": "owner@example.com",
        "storage_backend": "postgres",
        "postgres_dsn": SecretStr("postgresql://runtime.invalid/application"),
        "storage_migration_mode": "verify_only",
        "retention_execution_mode": "scheduled",
        "qdrant_url": "https://qdrant.invalid",
        "qdrant_api_key": SecretStr("not-a-real-key"),
        "response_cache_adapter": "disabled",
    }
    values.update(override)

    with pytest.raises(ValidationError, match=message):
        Settings.model_validate(values)
