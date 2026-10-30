from datetime import UTC, datetime, timedelta

from ai_finance_assistant.agents.context import InMemoryAgentContextRepository
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
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
                workflow_id="finance-assistant",
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
