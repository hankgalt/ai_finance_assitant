import base64
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.observability.memory import InMemoryObservability


def _app(path: Path) -> FastAPI:
    return create_app(
        Settings(
            mode="test",
            storage_path=path,
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            observability_mode="in_memory",
            langsmith_tracing_enabled=False,
        )
    )


def test_base64_file_import_transport_preserves_json_bytes(tmp_path: Path) -> None:
    app = _app(tmp_path / "imports.sqlite3")
    rows = (
        b'[{"account_id":"account-1","account_type":"taxable",'
        b'"holding_id":"holding-1","identifier_type":"ticker",'
        b'"identifier_value":"DEMO","quantity":"2","currency":"USD",'
        b'"user_price":"10","user_price_as_of":"2026-10-28T12:00:00Z",'
        b'"user_price_provenance":"M6 fixture"}]'
    )
    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/portfolio-imports/validate",
            json={
                "metadata": {
                    "portfolio_id": "portfolio-file-1",
                    "label": "Uploaded JSON",
                    "base_currency": "USD",
                    "imported_at": "2026-10-28T12:00:00Z",
                },
                "payload": {
                    "kind": "json",
                    "content_base64": base64.b64encode(rows).decode(),
                    "filename": "portfolio.json",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["portfolio"]["source_kind"] == "json"


def test_browser_telemetry_is_bounded_and_non_payload_bearing(tmp_path: Path) -> None:
    app = _app(tmp_path / "telemetry.sqlite3")
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/telemetry/browser",
            json={
                "kind": "api_timing",
                "page": "market",
                "api_route": "market_history",
                "status_class": "2xx",
                "failure_category": "none",
                "duration_ms": 42.5,
                "trace_id": "1" * 32,
                "request_id": "web-request-1",
            },
        )
        rejected = client.post(
            "/api/v1/telemetry/browser",
            json={
                "kind": "error_boundary",
                "page": "portfolio",
                "failure_category": "internal",
                "message": "private portfolio content",
            },
        )
        safe = cast(Any, app.state.services.observability)
        memory = cast(InMemoryObservability, safe._delegate)

    assert accepted.status_code == 204
    assert rejected.status_code == 422
    metrics = {metric.name: metric for metric in memory.metrics}
    assert metrics["frontend.api.requests"].attributes == {
        "page": "market",
        "route": "market_history",
        "status_class": "2xx",
        "failure_category": "none",
    }
    assert "web-request-1" not in str(metrics)
    assert "private portfolio content" not in str(metrics)
