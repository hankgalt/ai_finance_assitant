from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings


def _session(client: TestClient, label: str = "test") -> str:
    response = client.post("/api/v1/sessions", json={"label": label})
    assert response.status_code == 201
    return str(response.json()["session_id"])


def _portfolio_payload(portfolio_id: str) -> dict[str, object]:
    return {
        "metadata": {
            "portfolio_id": portfolio_id,
            "label": "API fixture",
            "base_currency": "USD",
            "imported_at": datetime(2026, 10, 28, 12, 0, tzinfo=UTC).isoformat(),
        },
        "payload": {
            "kind": "manual",
            "rows": [
                {
                    "account_id": "account-1",
                    "account_type": "taxable",
                    "holding_id": "holding-1",
                    "identifier_type": "ticker",
                    "identifier_value": "DEMO",
                    "quantity": "2",
                    "currency": "USD",
                    "user_price": "10",
                    "user_price_as_of": "2026-10-28T12:00:00Z",
                    "user_price_provenance": "test fixture",
                }
            ],
        },
    }


def test_run_idempotency_session_scope_and_sse_recovery(client: TestClient) -> None:
    session_id = _session(client, "first")
    other_session_id = _session(client, "second")
    path = f"/api/v1/sessions/{session_id}/runs"
    headers = {"Idempotency-Key": "run-key-1"}

    created = client.post(path, json={"message": "What is an ETF?"}, headers=headers)
    replayed = client.post(path, json={"message": "What is an ETF?"}, headers=headers)
    conflict = client.post(path, json={"message": "What is a bond?"}, headers=headers)

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json()["execution_id"] == created.json()["execution_id"]
    assert conflict.status_code == 409
    execution_id = created.json()["execution_id"]
    denied = client.get(f"/api/v1/sessions/{other_session_id}/runs/{execution_id}")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "RUN_SCOPE_DENIED"
    denied_stream = client.get(f"/api/v1/sessions/{other_session_id}/runs/{execution_id}/stream")
    assert denied_stream.status_code == 403

    history = client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}/events")
    assert history.status_code == 200
    events = history.json()["events"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))

    stream_path = f"/api/v1/sessions/{session_id}/runs/{execution_id}/stream"
    full_stream = client.get(stream_path)
    replay_stream = client.get(stream_path, headers={"Last-Event-ID": events[0]["event_id"]})
    completed_stream = client.get(
        stream_path,
        headers={"Last-Event-ID": f"chunk:{execution_id}:1"},
    )
    assert full_stream.headers["content-type"].startswith("text/event-stream")
    assert "event: run_event" in full_stream.text
    assert "event: response_chunk" in full_stream.text
    replayed_ids = tuple(
        line.removeprefix("id: ")
        for line in replay_stream.text.splitlines()
        if line.startswith("id: ")
    )
    assert events[0]["event_id"] not in replayed_ids
    assert completed_stream.text == ""


def test_portfolio_snapshot_goal_and_deletion_lifecycle(client: TestClient) -> None:
    session_id = _session(client)
    portfolio_id = "portfolio-api-1"
    payload = _portfolio_payload(portfolio_id)
    path = f"/api/v1/sessions/{session_id}/portfolios"

    created = client.post(path, json=payload, headers={"Idempotency-Key": "portfolio-key-1"})
    replayed = client.post(path, json=payload, headers={"Idempotency-Key": "portfolio-key-1"})
    assert created.status_code == 201
    assert replayed.status_code == 200
    assert created.json()["accepted"] is True

    snapshot = client.post(
        f"{path}/{portfolio_id}/snapshots",
        json={
            "snapshot_id": "snapshot-api-1",
            "security_references": [],
            "quote_set": {"quote_set_id": "quotes-api-1", "quotes": []},
        },
    )
    assert snapshot.status_code == 201
    assert snapshot.json()["base_currency_total"] == "20.00"

    goal = client.post(
        f"/api/v1/sessions/{session_id}/goal-projections",
        json={
            "projection_id": "goal-api-1",
            "currency": "USD",
            "starting_amount": "1000",
            "goal_amount": "2000",
            "contribution_amount": "100",
            "contribution_frequency": "monthly",
            "contribution_timing": "end",
            "horizon_months": 12,
            "risk_tolerance": "not_declared",
            "scenarios": [
                {
                    "label": "explicit",
                    "annual_return_rate": "0.05",
                    "annual_inflation_rate": "0.02",
                    "annual_fee_rate": "0",
                }
            ],
        },
    )
    assert goal.status_code == 200
    assert goal.json()["projection_id"] == "goal-api-1"

    deleted = client.delete(f"/api/v1/sessions/{session_id}")
    assert deleted.status_code == 204
    assert client.get(f"{path}/{portfolio_id}").status_code == 404


def test_market_history_exposes_cache_layer_and_coverage(client: TestClient) -> None:
    session_id = _session(client)
    path = f"/api/v1/sessions/{session_id}/market/history"
    body = {
        "symbol": "DEMO",
        "currency": "USD",
        "start_date": "2026-10-23",
        "end_date": "2026-10-26",
    }

    first = client.post(path, json=body)
    second = client.post(path, json=body)

    assert first.status_code == 200
    assert first.json()["provenance"]["cache_coverage"] == "complete"
    assert second.json()["provenance"]["cache_layer"] == "memory"
    assert second.json()["provenance"]["cache_status"] == "hit"


def test_openapi_contains_m5_resources_without_secret_values(client: TestClient) -> None:
    document = client.get("/openapi.json")

    assert document.status_code == 200
    paths = document.json()["paths"]
    assert "/api/v1/sessions" in paths
    assert "/api/v1/sessions/{session_id}/runs/{execution_id}/stream" in paths
    assert "/api/v1/sessions/{session_id}/portfolios" in paths
    assert "/api/v1/sessions/{session_id}/market/history" in paths
    assert "/api/v1/sessions/{session_id}/goal-projections" in paths
    serialized = document.text.casefold()
    assert "openai_api_key" not in serialized
    assert "langsmith_api_key" not in serialized


def test_concurrent_runs_complete_without_crossing_sessions(client: TestClient) -> None:
    session_ids = (_session(client, "concurrent-a"), _session(client, "concurrent-b"))

    def run(session_id: str) -> tuple[int, str, str]:
        response = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
        )
        body = response.json()
        return response.status_code, str(body["session_id"]), str(body["status"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(run, session_ids))

    assert {result[0] for result in results} == {201}
    assert {result[1] for result in results} == set(session_ids)
    assert {result[2] for result in results} <= {
        "completed",
        "partial",
        "failed",
        "clarification",
    }


def test_request_limits_cors_and_stable_not_ready_errors(client: TestClient) -> None:
    session_id = _session(client)
    oversized = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "x" * 20_001},
    )
    preflight = client.options(
        "/api/v1/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    disabled_purge = client.delete("/api/v1/admin/provider-cache")

    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert disabled_purge.status_code == 503
    assert disabled_purge.json()["error"]["code"] == "ADMIN_PURGE_NOT_READY"


def test_unexpected_workflow_failure_persists_safe_terminal_run(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    session_id = _session(client)
    services = cast(Any, cast(Any, client.app).state.services)

    def fail_safely(request: object) -> None:
        del request
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(services.workflow, "run", fail_safely)
    response = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "What is an ETF?"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["result"]["errors"][0] == {
        "code": "RUN_EXECUTION_FAILED",
        "category": "internal",
        "message": "The Run failed safely before a result was available.",
        "retryable": True,
        "attempt_count": 1,
        "safe_details": {},
    }
    assert "private implementation detail" not in response.text


def test_administrative_provider_cache_purge_requires_token(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            mode="test",
            storage_path=tmp_path / "purge.sqlite3",
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            observability_mode="in_memory",
            langsmith_tracing_enabled=False,
            local_admin_token="test-admin-token",
        )
    )
    with TestClient(app) as local:
        session_id = _session(local)
        local.post(
            f"/api/v1/sessions/{session_id}/market/history",
            json={
                "symbol": "DEMO",
                "currency": "USD",
                "start_date": "2026-10-23",
                "end_date": "2026-10-26",
            },
        )
        denied = local.delete(
            "/api/v1/admin/provider-cache",
            headers={"X-Admin-Token": "wrong-token"},
        )
        purged = local.delete(
            "/api/v1/admin/provider-cache",
            headers={"X-Admin-Token": "test-admin-token"},
        )

    assert denied.status_code == 403
    assert purged.status_code == 200
    assert purged.json()["deleted_bar_count"] > 0
