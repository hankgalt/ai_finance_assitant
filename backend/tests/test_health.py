import pytest
from fastapi.testclient import TestClient

from ai_finance_assistant.contracts.health import CheckStatus
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.core.health import build_readiness
from ai_finance_assistant.knowledge.models import CollectionCompatibility


def test_aggregate_health_is_live_but_truthfully_not_ready(client: TestClient) -> None:
    response = client.get("/api/health", headers={"x-request-id": "test-request-1"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-1"
    body = response.json()
    assert body["status"] == "degraded"
    assert body["liveness"]["status"] == "ok"
    assert body["readiness"]["status"] == "not_ready"
    assert {check["name"] for check in body["readiness"]["checks"]} == {
        "qdrant.finance_education",
        "qdrant.tax_education",
    }
    assert all(check["status"] == "not_configured" for check in body["readiness"]["checks"])


def test_liveness_and_readiness_are_separate(client: TestClient) -> None:
    assert client.get("/api/health/live").status_code == 200
    readiness = client.get("/api/health/ready")
    assert readiness.status_code == 503
    assert readiness.json()["status"] == "not_ready"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health/live", headers={"x-request-id": "unsafe value"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "unsafe value"


def test_configured_but_unavailable_qdrant_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnavailableStore:
        def __init__(self, url: str) -> None:
            del url
            raise ConnectionError("test-only connection failure")

    monkeypatch.setattr("ai_finance_assistant.core.health.QdrantKnowledgeStore", UnavailableStore)
    readiness = build_readiness(Settings(mode="test", qdrant_url="http://127.0.0.1:6333"))

    assert readiness.status == "not_ready"
    assert all(check.status == CheckStatus.FAILED for check in readiness.checks)
    assert all("unavailable" in check.detail for check in readiness.checks)


def test_compatible_active_collections_are_ready(monkeypatch: pytest.MonkeyPatch) -> None:
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
    readiness = build_readiness(Settings(mode="test", qdrant_url="http://127.0.0.1:6333"))

    assert readiness.status == "ok"
    assert all(check.status == CheckStatus.READY for check in readiness.checks)
    assert {alias for alias, _ in seen} == {
        "finance_education_active",
        "tax_education_active",
    }
