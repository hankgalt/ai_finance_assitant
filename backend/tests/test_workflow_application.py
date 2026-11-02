from datetime import UTC, datetime, timedelta

from ai_finance_assistant.agents.context import InMemoryAgentContextRepository
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.events import EventType
from ai_finance_assistant.core.config import Settings, get_settings
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import RoutingModelOutput, RoutingReason
from ai_finance_assistant.llm.ports import ModelAdapter
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.providers.factory import credential_free_bundle
from ai_finance_assistant.providers.ports import ProviderBundle
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import InMemoryRunEventRepository, RunEventRecorder
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowStatus
from ai_finance_assistant.workflow.retrieval import StaticKnowledgeRetrieval


def test_application_creates_one_provider_bundle_per_run() -> None:
    calls = 0
    model_calls = 0

    def bundle_builder(settings: Settings) -> ProviderBundle:
        nonlocal calls
        assert settings.provider_mode == "credential_free"
        calls += 1
        return credential_free_bundle()

    def model_builder(settings: Settings) -> ModelAdapter:
        nonlocal model_calls
        assert settings.model_mode == "credential_free"
        model_calls += 1
        return DeterministicModelAdapter()

    now = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    evidence = Evidence(
        chunk_id="finance-chunk",
        document_id="finance-document",
        title="ETF basics",
        publisher="Investor Education Test Publisher",
        canonical_url="https://example.invalid/etf",
        section_path="Basics",
        text="An ETF is a pooled investment vehicle.",
        score=0.95,
        rank=1,
        collection_name="finance_v1",
        collection_version="v1",
        document_version="v1",
        content_hash="a" * 64,
        fetched_at=now,
        jurisdiction="US-Federal",
    )
    telemetry = InMemoryObservability()
    application = WorkflowApplication(
        settings=Settings(
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            langsmith_tracing_enabled=False,
        ),
        retrieval=StaticKnowledgeRetrieval({LogicalKnowledgeBase.FINANCE: (evidence,)}),
        contexts=InMemoryAgentContextRepository(),
        model_adapter_builder=model_builder,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=telemetry,
        ),
        observability=telemetry,
        provider_bundle_builder=bundle_builder,
    )

    results = tuple(
        application.run(
            WorkflowRequest(
                execution_id=f"run-bundle-{index}",
                session_id=f"session-bundle-{index}",
                workflow_id=get_settings().workflow_id,
                workflow_version="1",
                message="What is an ETF?",
                deadline_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
        for index in range(2)
    )

    assert calls == 2
    assert model_calls == 2
    assert all(result.status == WorkflowStatus.COMPLETED for result in results)


def test_application_composes_finance_and_tax_results_through_synthesis() -> None:
    message = "Explain diversification and U.S. federal tax considerations for taxable investing."
    now = datetime(2026, 10, 31, 18, 0, tzinfo=UTC)
    finance_evidence = Evidence(
        chunk_id="finance-synthesis-chunk",
        document_id="finance-synthesis-document",
        title="Diversification basics",
        publisher="Investor Education Test Publisher",
        canonical_url="https://example.invalid/diversification",
        section_path="Basics",
        text="Diversification can reduce concentration risk but cannot prevent loss.",
        score=0.95,
        rank=1,
        collection_name="finance_v1",
        collection_version="v1",
        document_version="v1",
        content_hash="b" * 64,
        fetched_at=now,
        jurisdiction="US-Federal",
    )
    tax_evidence = Evidence(
        chunk_id="tax-synthesis-chunk",
        document_id="tax-synthesis-document",
        title="Investment income tax basics",
        publisher="Internal Revenue Service",
        canonical_url="https://example.invalid/tax",
        section_path="Capital gains",
        text="Tax treatment depends on the account and transaction facts.",
        score=0.96,
        rank=1,
        collection_name="tax_v1",
        collection_version="v1",
        document_version="v1",
        content_hash="c" * 64,
        fetched_at=now,
        tax_years=(2026,),
        jurisdiction="US-Federal",
    )
    telemetry = InMemoryObservability()
    event_repository = InMemoryRunEventRepository()
    application = WorkflowApplication(
        settings=Settings(
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            langsmith_tracing_enabled=False,
        ),
        retrieval=StaticKnowledgeRetrieval(
            {
                LogicalKnowledgeBase.FINANCE: (finance_evidence,),
                LogicalKnowledgeBase.TAX: (tax_evidence,),
            }
        ),
        contexts=InMemoryAgentContextRepository(),
        model_adapter_builder=lambda _: DeterministicModelAdapter(
            routing_responses={
                message: RoutingModelOutput(
                    selected_agent_ids=(AgentId.FINANCE_QA, AgentId.TAX_EDUCATION),
                    reason_category=RoutingReason.MULTI_DOMAIN,
                )
            }
        ),
        event_recorder=RunEventRecorder(
            repository=event_repository,
            observability=telemetry,
        ),
        observability=telemetry,
        provider_bundle_builder=lambda _: credential_free_bundle(),
    )

    result = application.run(
        WorkflowRequest(
            execution_id="run-application-synthesis",
            session_id="session-application-synthesis",
            workflow_id=get_settings().workflow_id,
            workflow_version="1",
            message=message,
            deadline_at=datetime.now(UTC) + timedelta(minutes=1),
        )
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.selected_agent_ids == (AgentId.FINANCE_QA, AgentId.TAX_EDUCATION)
    assert len(result.agent_results) == 2
    assert result.summary.startswith("Finance Qa:")
    assert "Tax Education:" in result.summary
    events = event_repository.list_for_run(
        "run-application-synthesis",
        session_id="session-application-synthesis",
    )
    assert any(
        event.event_type == EventType.MODEL_COMPLETED and event.node_id == "synthesize"
        for event in events
    )
