from fastapi.testclient import TestClient


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
