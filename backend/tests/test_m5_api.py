from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    ModelOutput,
    ModelRequest,
    RoutingModelOutput,
    RoutingModelRequest,
    RoutingReason,
)

LONG_EDUCATIONAL_NARRATIVE = " ".join(
    ["ETFs and mutual funds share features but differ in trading and pricing."] * 20
)


class LongNarrativeModelAdapter:
    provider_id = "long-narrative-fixture"
    model_id = "long-narrative-fixture-v1"
    prompt_version = "long-narrative-fixture-v1"
    routing_prompt_version = "long-narrative-routing-fixture-v1"

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        del request
        output = ModelOutput(summary=LONG_EDUCATIONAL_NARRATIVE)
        return ModelAdapterResult(payload=output.model_dump(mode="json"))

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        del request
        output = RoutingModelOutput(
            selected_agent_ids=(AgentId.NEWS_SYNTHESIZER,),
            reason_category=RoutingReason.SINGLE_DOMAIN,
        )
        return ModelAdapterResult(payload=output.model_dump(mode="json"))


class PortfolioQuestionModelAdapter:
    provider_id = "portfolio-question-fixture"
    model_id = "portfolio-question-fixture-v1"
    prompt_version = "portfolio-question-fixture-v1"
    routing_prompt_version = "portfolio-question-routing-fixture-v1"

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        output = ModelOutput(
            summary=(
                f"Compared {len(request.facts)} authorized Portfolio Snapshot"
                f"{'s' if len(request.facts) != 1 else ''} separately."
            )
        )
        return ModelAdapterResult(payload=output.model_dump(mode="json"))

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        del request
        output = RoutingModelOutput(
            selected_agent_ids=(AgentId.PORTFOLIO_ANALYSIS,),
            reason_category=RoutingReason.SINGLE_DOMAIN,
        )
        return ModelAdapterResult(payload=output.model_dump(mode="json"))


class OutOfScopeModelAdapter:
    provider_id = "out-of-scope-fixture"
    model_id = "out-of-scope-fixture-v1"
    prompt_version = "out-of-scope-fixture-v1"
    routing_prompt_version = "out-of-scope-routing-fixture-v1"

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        raise AssertionError(f"No specialist generation expected for {request.agent_id}")

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        del request
        output = RoutingModelOutput(
            selected_agent_ids=(),
            reason_category=RoutingReason.OUT_OF_SCOPE,
        )
        return ModelAdapterResult(payload=output.model_dump(mode="json"))


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


def test_run_record_preserves_the_asked_question(client: TestClient) -> None:
    session_id = _session(client, "question history")
    question = "What's the difference between ETFs and mutual funds?"

    created = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": question},
    )

    assert created.status_code == 201
    execution_id = created.json()["execution_id"]
    assert created.json()["request_message"] == question
    persisted = client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}")
    assert persisted.json()["request_message"] == question
    listed = client.get(f"/api/v1/sessions/{session_id}/runs")
    assert listed.json()["items"][0]["request_message"] == question


def test_run_returns_bounded_response_without_specialists_for_out_of_scope_question(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    services = cast(Any, cast(Any, client.app).state.services)
    monkeypatch.setattr(
        services.workflow,
        "_model_adapter_builder",
        lambda _: OutOfScopeModelAdapter(),
    )
    session_id = _session(client, "out of scope")

    created = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "How's the weather?"},
    )

    assert created.status_code == 201
    result = created.json()["result"]
    assert result["status"] == "completed"
    assert result["selected_agent_ids"] == []
    assert result["agent_results"] == []
    assert "can't answer unrelated general-knowledge questions" in result["summary"]


def test_run_uses_each_explicit_authorized_portfolio_context(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    services = cast(Any, cast(Any, client.app).state.services)
    monkeypatch.setattr(
        services.workflow,
        "_model_adapter_builder",
        lambda _: PortfolioQuestionModelAdapter(),
    )
    session_id = _session(client, "portfolio questions")
    portfolio_path = f"/api/v1/sessions/{session_id}/portfolios"
    portfolio_ids = ("portfolio-chat-1", "portfolio-chat-2")
    for portfolio_id in portfolio_ids:
        saved = client.post(
            portfolio_path,
            json=_portfolio_payload(portfolio_id),
            headers={"Idempotency-Key": f"save-{portfolio_id}"},
        )
        assert saved.status_code == 201

    clarification = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={
            "message": "How many holdings in these portfolios have usable prices?",
        },
    )
    assert clarification.status_code == 201
    assert clarification.json()["status"] == "clarification"
    assert clarification.json()["result"]["required_input"] == {
        "kind": "portfolio_selection",
        "agent_id": "portfolio_analysis",
        "selection_mode": "one_or_explicit_comparison",
        "prompt": "Select the saved Portfolio you want me to analyze.",
    }

    other_session_id = _session(client, "other portfolio owner")
    denied = client.post(
        f"/api/v1/sessions/{other_session_id}/runs/{clarification.json()['execution_id']}/continue",
        json={"context_references": [portfolio_ids[0]]},
    )
    missing_context = client.post(
        f"/api/v1/sessions/{session_id}/runs/{clarification.json()['execution_id']}/continue",
        json={"context_references": ["missing-portfolio"]},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "RUN_SCOPE_DENIED"
    assert missing_context.status_code == 403
    assert missing_context.json()["error"]["code"] == "PORTFOLIO_CONTEXT_DENIED"

    created = client.post(
        f"/api/v1/sessions/{session_id}/runs/{clarification.json()['execution_id']}/continue",
        json={"context_references": list(portfolio_ids)},
    )

    assert created.status_code == 201
    result = created.json()["result"]
    assert result["selected_agent_ids"] == ["portfolio_analysis"]
    assert result["agent_results"][0]["summary"] == (
        "Compared 2 authorized Portfolio Snapshots separately."
    )
    assert [fact["portfolio_id"] for fact in result["agent_results"][0]["facts"]] == list(
        portfolio_ids
    )
    assert result["continuation_of_execution_id"] == clarification.json()["execution_id"]

    replayed = client.post(
        f"/api/v1/sessions/{session_id}/runs/{clarification.json()['execution_id']}/continue",
        json={"context_references": [portfolio_ids[0]]},
    )
    assert replayed.status_code == 200
    assert replayed.json()["execution_id"] == created.json()["execution_id"]

    not_waiting = client.post(
        f"/api/v1/sessions/{session_id}/runs/{created.json()['execution_id']}/continue",
        json={"context_references": [portfolio_ids[0]]},
    )
    assert not_waiting.status_code == 409
    assert not_waiting.json()["error"]["code"] == "RUN_CONTINUATION_NOT_AVAILABLE"


def test_complete_narrative_persists_and_streams_without_truncation(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    services = cast(Any, cast(Any, client.app).state.services)
    monkeypatch.setattr(
        services.workflow,
        "_model_adapter_builder",
        lambda _: LongNarrativeModelAdapter(),
    )
    session_id = _session(client, "long narrative")

    created = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "What's the latest news on MSFT?"},
    )

    assert created.status_code == 201
    execution_id = created.json()["execution_id"]
    assert created.json()["result"]["agent_results"][0]["summary"] == (LONG_EDUCATIONAL_NARRATIVE)
    persisted = client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}")
    assert persisted.json()["result"]["summary"] == LONG_EDUCATIONAL_NARRATIVE
    stream = client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}/stream")
    assert LONG_EDUCATIONAL_NARRATIVE in stream.text
    assert "truncated due to a generation error" not in stream.text


def test_broad_financial_news_run_does_not_require_a_ticker(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    services = cast(Any, cast(Any, client.app).state.services)
    monkeypatch.setattr(
        services.workflow,
        "_model_adapter_builder",
        lambda _: LongNarrativeModelAdapter(),
    )
    session_id = _session(client, "broad financial news")

    created = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "Whats the latest in financial news?"},
    )

    assert created.status_code == 201
    result = created.json()["result"]
    assert result["status"] == "completed"
    assert result["selected_agent_ids"] == ["news_synthesizer"]
    assert result["agent_results"][0]["status"] == "ok"
    assert result["agent_results"][0]["summary"] == LONG_EDUCATIONAL_NARRATIVE
    assert result["agent_results"][0]["warnings"] == [
        "No date window was specified; using the latest 7 days for public financial news."
    ]


def test_portfolio_snapshot_goal_archive_and_deletion_lifecycle(client: TestClient) -> None:
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

    active_delete = client.delete(f"/api/v1/sessions/{session_id}")
    archived = client.post(f"/api/v1/sessions/{session_id}/archive")
    archived_sessions = client.get("/api/v1/sessions", params={"state": "archived"})
    preserved = client.get(f"{path}/{portfolio_id}")
    archived_write = client.post(
        f"/api/v1/sessions/{session_id}/runs",
        json={"message": "What is a bond?"},
    )
    deleted = client.delete(f"/api/v1/sessions/{session_id}")

    assert active_delete.status_code == 409
    assert active_delete.json()["error"]["code"] == "SESSION_ARCHIVE_REQUIRED"
    assert archived.status_code == 200
    assert archived.json()["state"] == "archived"
    assert archived.json()["archived_at"] is not None
    assert [item["session_id"] for item in archived_sessions.json()["items"]] == [session_id]
    assert preserved.status_code == 200
    assert archived_write.status_code == 409
    assert archived_write.json()["error"]["code"] == "SESSION_ARCHIVED"
    assert deleted.status_code == 204
    assert client.get(f"{path}/{portfolio_id}").status_code == 404


def test_portfolio_delete_is_scoped_cascades_and_allows_reimport(
    client: TestClient,
) -> None:
    session_id = _session(client, "portfolio owner")
    other_session_id = _session(client, "other owner")
    portfolio_id = "portfolio-delete-1"
    portfolio_path = f"/api/v1/sessions/{session_id}/portfolios/{portfolio_id}"
    collection_path = f"/api/v1/sessions/{session_id}/portfolios"
    payload = _portfolio_payload(portfolio_id)
    headers = {"Idempotency-Key": "portfolio-delete-key"}

    created = client.post(collection_path, json=payload, headers=headers)
    snapshot = client.post(
        f"{portfolio_path}/snapshots",
        json={
            "snapshot_id": "snapshot-delete-1",
            "security_references": [],
            "quote_set": {"quote_set_id": "quotes-delete-1", "quotes": []},
        },
    )
    services = cast(Any, cast(Any, client.app).state.services)
    assert services.context_repository.get(session_id, portfolio_id) is not None
    denied = client.delete(f"/api/v1/sessions/{other_session_id}/portfolios/{portfolio_id}")
    deleted = client.delete(portfolio_path)

    assert created.status_code == 201
    assert snapshot.status_code == 201
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PORTFOLIO_SCOPE_DENIED"
    assert deleted.status_code == 204
    assert client.get(portfolio_path).status_code == 404
    assert (
        client.get(f"/api/v1/sessions/{session_id}/snapshots/snapshot-delete-1").status_code == 404
    )
    assert services.context_repository.get(session_id, portfolio_id) is None
    assert client.get(collection_path).json() == []

    recreated = client.post(collection_path, json=payload, headers=headers)
    assert recreated.status_code == 201
    assert recreated.json()["portfolio"]["portfolio_id"] == portfolio_id


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
    assert "/api/v1/sessions/{session_id}/archive" in paths
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
