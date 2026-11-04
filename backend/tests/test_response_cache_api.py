from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.api.services import ApplicationServices
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.llm.models import (
    PublicRagCacheEligibility,
    RoutingModelOutput,
    RoutingReason,
)
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheWriteOutcome,
)
from ai_finance_assistant.response_cache.service import RouteCacheContext


def _route_context(session_id: str) -> RouteCacheContext:
    return RouteCacheContext(
        session_id=session_id,
        message="What is an ETF?",
        locale="en-US",
        jurisdiction="US",
        workflow_version="1",
        provider_id="deterministic",
        model_id="deterministic-model-v1",
        prompt_version="deterministic-routing-fixture-v1",
    )


def _route_output() -> RoutingModelOutput:
    return RoutingModelOutput(
        selected_agent_ids=(AgentId.FINANCE_QA,),
        reason_category=RoutingReason.SINGLE_DOMAIN,
        cache_eligibility=PublicRagCacheEligibility.PUBLIC_RAG,
    )


def _session(client: TestClient) -> str:
    response = client.post("/api/v1/sessions", json={"label": "Cache lifecycle"})
    assert response.status_code == 201
    return cast(str, response.json()["session_id"])


def _services(client: TestClient) -> ApplicationServices:
    app = client.app
    assert isinstance(app, FastAPI)
    services = app.state.services
    assert isinstance(services, ApplicationServices)
    return services


def test_archive_and_delete_purge_session_cache_namespace(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            mode="test",
            storage_path=tmp_path / "response-cache.sqlite3",
            qdrant_url=None,
            provider_mode="credential_free",
            model_mode="credential_free",
            observability_mode="in_memory",
            response_cache_adapter="in_memory",
        )
    )
    with TestClient(app) as client:
        session_id = _session(client)
        services = _services(client)
        context = _route_context(session_id)
        assert (
            services.response_cache.store_route(context, _route_output()).outcome
            == CacheWriteOutcome.STORED
        )

        archived = client.post(f"/api/v1/sessions/{session_id}/archive")

        assert archived.status_code == 200
        assert services.response_cache.lookup_route(context).outcome == CacheLookupOutcome.MISS
        deleted = client.delete(f"/api/v1/sessions/{session_id}")
        assert deleted.status_code == 204


def test_administrative_response_cache_purge_requires_token(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            mode="test",
            storage_path=tmp_path / "response-cache-admin.sqlite3",
            qdrant_url=None,
            provider_mode="credential_free",
            model_mode="credential_free",
            observability_mode="in_memory",
            response_cache_adapter="in_memory",
            local_admin_token=SecretStr("test-admin-token"),
        )
    )
    with TestClient(app) as client:
        session_id = _session(client)
        services = _services(client)
        assert (
            services.response_cache.store_route(_route_context(session_id), _route_output()).outcome
            == CacheWriteOutcome.STORED
        )
        denied = client.delete(
            "/api/v1/admin/response-cache",
            headers={"X-Admin-Token": "wrong-token"},
        )
        purged = client.delete(
            "/api/v1/admin/response-cache",
            headers={"X-Admin-Token": "test-admin-token"},
        )

    assert denied.status_code == 403
    assert purged.status_code == 200
    assert purged.json() == {"deleted_entry_count": 1}
