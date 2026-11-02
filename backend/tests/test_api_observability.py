from pathlib import Path
from typing import Any, Literal, cast

import httpx
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.observability.memory import InMemoryObservability


def _settings(
    path: Path,
    *,
    observability_mode: Literal["in_memory", "opentelemetry"],
) -> Settings:
    return Settings(
        mode="test",
        storage_path=path,
        provider_mode="credential_free",
        model_mode="credential_free",
        qdrant_url=None,
        observability_mode=observability_mode,
        langsmith_tracing_enabled=False,
    )


def test_inbound_w3c_trace_context_correlates_run_events(tmp_path: Path) -> None:
    expected_trace_id = "1" * 32
    traceparent = f"00-{expected_trace_id}-{'2' * 16}-01"
    app = create_app(_settings(tmp_path / "trace.sqlite3", observability_mode="opentelemetry"))

    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
        run = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
            headers={"traceparent": traceparent},
        )
        execution_id = run.json()["execution_id"]
        events = client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}/events").json()[
            "events"
        ]

    assert run.status_code == 201
    assert run.json()["result"]["trace_id"] == expected_trace_id
    assert {event["trace_id"] for event in events} == {expected_trace_id}


def test_http_metrics_use_route_templates_and_exclude_health(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path / "metrics.sqlite3", observability_mode="in_memory"))

    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
        client.get(f"/api/v1/sessions/{session_id}")
        client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
        )
        client.post(
            f"/api/v1/sessions/{session_id}/market/history",
            json={
                "symbol": "DEMO",
                "currency": "USD",
                "start_date": "2026-10-23",
                "end_date": "2026-10-26",
            },
        )
        client.get("/api/health/live")
        safe = cast(Any, app.state.services.observability)
        memory = cast(InMemoryObservability, safe._delegate)
        request_metrics = tuple(
            metric for metric in memory.metrics if metric.name == "backend.http.requests"
        )

    assert request_metrics
    assert {metric.attributes["route"] for metric in request_metrics} == {
        "/api/v1/sessions",
        "/api/v1/sessions/{session_id}",
        "/api/v1/sessions/{session_id}/market/history",
        "/api/v1/sessions/{session_id}/runs",
    }
    assert all(session_id not in str(metric.attributes) for metric in request_metrics)
    metric_names = {metric.name for metric in memory.metrics}
    assert {
        "backend.http.requests",
        "backend.http.duration_ms",
        "persistence.operations",
        "persistence.duration_ms",
        "retrieval.requests",
        "retrieval.duration_ms",
        "provider.requests",
        "provider.duration_ms",
        "provider.cache.requests",
    }.issubset(metric_names)


def test_instrumented_httpx_injects_w3c_trace_context() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    provider = TracerProvider()
    tracer = provider.get_tracer("m5-outbound-test")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    HTTPXClientInstrumentor.instrument_client(client, tracer_provider=provider)
    try:
        with tracer.start_as_current_span("provider.request"):
            response = client.get("https://example.invalid/provider")
    finally:
        HTTPXClientInstrumentor.uninstrument_client(client)
        client.close()
        provider.shutdown()

    assert response.status_code == 200
    assert captured["traceparent"].startswith("00-")
