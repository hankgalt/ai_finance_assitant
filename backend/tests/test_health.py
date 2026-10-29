from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_finance_assistant.contracts.health import CheckStatus
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.core.health import build_readiness
from ai_finance_assistant.knowledge.models import CollectionCompatibility
from ai_finance_assistant.persistence.database import SQLiteDatabase


def _initialized_settings(tmp_path: Path, *, qdrant_url: str) -> Settings:
    settings = Settings(
        mode="test",
        storage_path=tmp_path / "application.sqlite3",
        qdrant_url=qdrant_url,
        provider_mode="credential_free",
        host="127.0.0.1",
    )
    database = SQLiteDatabase(settings.storage_path)
    database.migrate()
    database.close()
    return settings


def test_aggregate_health_is_live_but_truthfully_not_ready(client: TestClient) -> None:
    response = client.get("/api/health", headers={"x-request-id": "test-request-1"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-1"
    body = response.json()
    assert body["status"] == "degraded"
    assert body["liveness"]["status"] == "ok"
    assert body["readiness"]["status"] == "not_ready"
    assert {check["name"] for check in body["readiness"]["checks"]} == {
        "storage.sqlite",
        "security.local_bind",
        "provider.market",
        "provider.news",
        "provider_cache.rights",
        "qdrant.finance_education",
        "qdrant.tax_education",
    }
    qdrant = [check for check in body["readiness"]["checks"] if check["name"].startswith("qdrant.")]
    assert all(check["status"] == "not_configured" for check in qdrant)
    assert all(
        check["status"] == "ready"
        for check in body["readiness"]["checks"]
        if not check["name"].startswith("qdrant.")
    )


def test_liveness_and_readiness_are_separate(client: TestClient) -> None:
    assert client.get("/api/health/live").status_code == 200
    readiness = client.get("/api/health/ready")
    assert readiness.status_code == 503
    assert readiness.json()["status"] == "not_ready"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health/live", headers={"x-request-id": "unsafe value"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "unsafe value"


def test_configured_but_unavailable_qdrant_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class UnavailableStore:
        def __init__(self, url: str) -> None:
            del url
            raise ConnectionError("test-only connection failure")

    monkeypatch.setattr("ai_finance_assistant.core.health.QdrantKnowledgeStore", UnavailableStore)
    readiness = build_readiness(_initialized_settings(tmp_path, qdrant_url="http://127.0.0.1:6333"))

    assert readiness.status == "not_ready"
    qdrant = tuple(check for check in readiness.checks if check.name.startswith("qdrant."))
    assert all(check.status == CheckStatus.FAILED for check in qdrant)
    assert all("unavailable" in check.detail for check in qdrant)


def test_compatible_active_collections_are_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen: list[tuple[str, CollectionCompatibility]] = []

    class CompatibleStore:
        def __init__(self, url: str) -> None:
            assert url == "http://127.0.0.1:6333"

        def validate_active(
            self, alias: str, expected: CollectionCompatibility
        ) -> tuple[bool, str]:
            seen.append((alias, expected))
            return True, f"{alias} is compatible"

    monkeypatch.setattr("ai_finance_assistant.core.health.QdrantKnowledgeStore", CompatibleStore)
    readiness = build_readiness(_initialized_settings(tmp_path, qdrant_url="http://127.0.0.1:6333"))

    assert readiness.status == "ok"
    assert all(check.status == CheckStatus.READY for check in readiness.checks)
    assert {alias for alias, _ in seen} == {
        "finance_education_active",
        "tax_education_active",
    }


@pytest.mark.parametrize("audience", ["shared_demo", "public"])
def test_unverified_live_cache_rights_fail_non_owner_readiness(
    tmp_path: Path,
    audience: str,
) -> None:
    settings = Settings(
        mode="test",
        storage_path=tmp_path / "application.sqlite3",
        qdrant_url=None,
        provider_mode="live",
        alpha_vantage_api_key="market-key",
        tavily_api_key="news-key",
        alpha_vantage_terms_approved=True,
        tavily_terms_approved=True,
        provider_cache_retention_permission="unverified",
        provider_cache_owner_risk_accepted=True,
        local_deployment_audience=audience,
    )
    database = SQLiteDatabase(settings.storage_path)
    database.migrate()
    database.close()

    readiness = build_readiness(settings)
    cache = next(check for check in readiness.checks if check.name == "provider_cache.rights")

    assert cache.status == CheckStatus.FAILED
    assert "block" in cache.detail.casefold()
