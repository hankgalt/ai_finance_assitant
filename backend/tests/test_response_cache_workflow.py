from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai_finance_assistant.agents.context import InMemoryAgentContextRepository
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.events import EventType
from ai_finance_assistant.core.config import Settings, get_settings
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase
from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    ModelRequest,
    PublicRagCacheEligibility,
    RoutingModelOutput,
    RoutingModelRequest,
    RoutingReason,
)
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.providers.factory import credential_free_bundle
from ai_finance_assistant.response_cache.adapters import InMemoryModelResponseCache
from ai_finance_assistant.response_cache.service import ResponseCacheService
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import InMemoryRunEventRepository, RunEventRecorder
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowStatus
from ai_finance_assistant.workflow.retrieval import StaticKnowledgeRetrieval


class CountingModel(DeterministicModelAdapter):
    def __init__(self, *, routing_responses: dict[str, RoutingModelOutput]) -> None:
        super().__init__(routing_responses=routing_responses)
        self.route_calls = 0
        self.generate_calls = 0

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        self.route_calls += 1
        return super().route(request)

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        self.generate_calls += 1
        return super().generate(request)


def public_route(agent_id: AgentId) -> RoutingModelOutput:
    return RoutingModelOutput(
        selected_agent_ids=(agent_id,),
        reason_category=RoutingReason.SINGLE_DOMAIN,
        cache_eligibility=PublicRagCacheEligibility.PUBLIC_RAG,
    )


def workflow_evidence(logical_kb: LogicalKnowledgeBase) -> Evidence:
    return Evidence(
        chunk_id=f"{logical_kb.value}-chunk",
        document_id=f"{logical_kb.value}-document",
        title="Public education evidence",
        publisher="Authoritative Publisher",
        canonical_url="https://example.invalid/public-education",
        section_path="Overview",
        text="Grounded educational content.",
        score=0.99,
        rank=1,
        collection_name=f"{logical_kb.value}_v1",
        collection_version="v1",
        document_version="document-v1",
        content_hash=("a" if logical_kb == LogicalKnowledgeBase.FINANCE else "b") * 64,
        fetched_at=datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
        tax_years=(2025,) if logical_kb == LogicalKnowledgeBase.TAX else (),
        jurisdiction="US-Federal",
    )


def run_request(
    execution_id: str, message: str, *, session_id: str = "session-a"
) -> WorkflowRequest:
    return WorkflowRequest(
        execution_id=execution_id,
        session_id=session_id,
        workflow_id=get_settings().workflow_id,
        workflow_version="1",
        message=message,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def application(
    *,
    model: CountingModel,
    events: InMemoryRunEventRepository,
    semantic_mode: str = "serving",
) -> WorkflowApplication:
    telemetry = InMemoryObservability()
    return WorkflowApplication(
        settings=Settings(
            workflow_id="test-workflow",
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            otel_service_name="test-service",
            langsmith_tracing_enabled=False,
            langsmith_project="test-project",
        ),
        retrieval=StaticKnowledgeRetrieval(
            {
                LogicalKnowledgeBase.FINANCE: (workflow_evidence(LogicalKnowledgeBase.FINANCE),),
                LogicalKnowledgeBase.TAX: (workflow_evidence(LogicalKnowledgeBase.TAX),),
            }
        ),
        contexts=InMemoryAgentContextRepository(),
        model_adapter_builder=lambda _: model,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        provider_bundle_builder=lambda _: credential_free_bundle(),
        response_cache=ResponseCacheService(
            adapter=InMemoryModelResponseCache(),
            encoder=DeterministicTestEncoder(),
            policy_version="test-policy-v1",
            schema_version="1",
            ttl_seconds=300,
            minimum_semantic_similarity=0.8,
            semantic_mode=semantic_mode,  # type: ignore[arg-type]
        ),
    )


def test_exact_finance_repeat_retrieves_current_evidence_and_avoids_both_model_calls() -> None:
    message = "What is an ETF?"
    model = CountingModel(routing_responses={message: public_route(AgentId.FINANCE_QA)})
    events = InMemoryRunEventRepository()
    app = application(model=model, events=events)

    first = app.run(run_request("run-cache-first", message))
    second = app.run(run_request("run-cache-second", message))

    assert first.status == second.status == WorkflowStatus.COMPLETED
    assert model.route_calls == 1
    assert model.generate_calls == 1
    second_events = events.list_for_run("run-cache-second", session_id="session-a")
    assert any(event.event_type == EventType.RETRIEVAL_COMPLETED for event in second_events)
    assert not any(event.event_type == EventType.MODEL_STARTED for event in second_events)
    cache_events = [
        event
        for event in second_events
        if event.tool_name == "model_response_cache"
        and event.event_type == EventType.TOOL_COMPLETED
    ]
    assert all(event.tool_result is not None for event in cache_events)
    assert [
        event.tool_result.cache_status for event in cache_events if event.tool_result is not None
    ] == ["hit", "hit"]
    assert first.agent_results[0].evidence == second.agent_results[0].evidence


def test_exact_tax_repeat_is_cached_with_current_year_matched_retrieval() -> None:
    message = "What tax considerations apply to pension income for 2025?"
    model = CountingModel(routing_responses={message: public_route(AgentId.TAX_EDUCATION)})
    events = InMemoryRunEventRepository()
    app = application(model=model, events=events)

    first = app.run(run_request("run-tax-first", message))
    second = app.run(run_request("run-tax-second", message))

    assert first.status == second.status == WorkflowStatus.COMPLETED
    assert model.route_calls == 1
    assert model.generate_calls == 1
    assert second.agent_results[0].facts[0]["tax_year"] == 2025
    second_events = events.list_for_run("run-tax-second", session_id="session-a")
    assert any(event.event_type == EventType.RETRIEVAL_COMPLETED for event in second_events)
    assert not any(event.event_type == EventType.MODEL_STARTED for event in second_events)


def test_same_question_in_another_session_cannot_reuse_route_or_generation() -> None:
    message = "What is an ETF?"
    model = CountingModel(routing_responses={message: public_route(AgentId.FINANCE_QA)})
    events = InMemoryRunEventRepository()
    app = application(model=model, events=events)

    app.run(run_request("run-session-a", message, session_id="session-a"))
    app.run(run_request("run-session-b", message, session_id="session-b"))

    assert model.route_calls == 2
    assert model.generate_calls == 2


def test_multi_agent_route_is_never_cached() -> None:
    message = "Explain diversification and related federal tax considerations."
    route = RoutingModelOutput(
        selected_agent_ids=(AgentId.FINANCE_QA, AgentId.TAX_EDUCATION),
        reason_category=RoutingReason.MULTI_DOMAIN,
    )
    model = CountingModel(routing_responses={message: route})
    events = InMemoryRunEventRepository()
    app = application(model=model, events=events)

    app.run(run_request("run-multi-first", message))
    app.run(run_request("run-multi-second", message))

    assert model.route_calls == 2
    assert model.generate_calls == 4
    second_events = events.list_for_run("run-multi-second", session_id="session-a")
    assert any(event.node_id == "synthesize" for event in second_events)
    assert not any(
        event.tool_name == "model_response_cache" and event.agent_id is not None
        for event in second_events
    )
