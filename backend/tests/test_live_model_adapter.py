import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from ai_finance_assistant.agents.context import (
    GoalAgentContext,
    InMemoryAgentContextRepository,
    MarketAgentContext,
    NewsAgentContext,
    PortfolioAgentContext,
)
from ai_finance_assistant.contracts.agents import AgentId, AgentResultStatus
from ai_finance_assistant.contracts.events import EventType, MeasurementAvailability
from ai_finance_assistant.contracts.portfolio import SecurityIdentifier
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.finance.models import (
    GoalProjectionRequest,
    GoalScenario,
    ImportedAccount,
    ImportedHolding,
    ImportedPortfolio,
)
from ai_finance_assistant.knowledge.models import Evidence, LogicalKnowledgeBase
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.providers.factory import credential_free_bundle
from ai_finance_assistant.workflow.application import WorkflowApplication
from ai_finance_assistant.workflow.events import InMemoryRunEventRepository, RunEventRecorder
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowStatus
from ai_finance_assistant.workflow.retrieval import StaticKnowledgeRetrieval

pytestmark = pytest.mark.live_model


def _live_tests_enabled() -> bool:
    return os.environ.get("AIFA_RUN_LIVE_MODEL_TESTS", "").casefold() in {
        "1",
        "true",
        "yes",
    }


def test_openai_live_account_supports_all_six_agent_contracts() -> None:
    if not _live_tests_enabled():
        pytest.skip("set AIFA_RUN_LIVE_MODEL_TESTS=true to permit external model calls")
    settings = Settings()
    if settings.model_mode != "openai_live":
        pytest.fail("live-model tests require AIFA_MODEL_MODE=openai_live")
    if not settings.openai_terms_approved:
        pytest.fail("live-model tests require AIFA_OPENAI_TERMS_APPROVED=true")
    if settings.openai_api_key is None:
        pytest.fail("live-model tests require OPENAI_API_KEY or AIFA_OPENAI_API_KEY")
    if settings.openai_model != "gpt-6.1-sol":
        pytest.fail("M4.1 qualification is pinned to AIFA_OPENAI_MODEL=gpt-6.1-sol")

    only_agent_value = os.environ.get("AIFA_LIVE_MODEL_ONLY_AGENT")
    only_agent = AgentId(only_agent_value) if only_agent_value else None
    expected_agents = {only_agent} if only_agent is not None else set(AgentId)
    settings = settings.model_copy(
        update={
            "model_request_budget": len(expected_agents) + 1,
            "model_maximum_attempts": 1,
            "provider_mode": "credential_free",
        }
    )
    assert settings.openai_api_key is not None
    now = datetime.now(UTC)
    finance_evidence = _evidence(
        logical_kb=LogicalKnowledgeBase.FINANCE,
        text="Diversification spreads exposure but does not eliminate investment risk.",
        now=now,
    )
    tax_evidence = _evidence(
        logical_kb=LogicalKnowledgeBase.TAX,
        text=(
            "For tax year 2026, investment tax treatment depends on account and transaction "
            "facts; educational summaries are not individualized tax advice."
        ),
        now=now,
    )
    contexts = _contexts(now)
    telemetry = InMemoryObservability()
    event_repository = InMemoryRunEventRepository()
    application = WorkflowApplication(
        settings=settings,
        retrieval=StaticKnowledgeRetrieval(
            {
                LogicalKnowledgeBase.FINANCE: (finance_evidence,),
                LogicalKnowledgeBase.TAX: (tax_evidence,),
            }
        ),
        contexts=contexts,
        event_recorder=RunEventRecorder(repository=event_repository, observability=telemetry),
        observability=telemetry,
        provider_bundle_builder=lambda _: credential_free_bundle(),
    )

    messages = {
        AgentId.FINANCE_QA: "Explain diversification.",
        AgentId.PORTFOLIO_ANALYSIS: "Analyze my portfolio.",
        AgentId.MARKET_ANALYSIS: "Describe DEMO historical price data.",
        AgentId.GOAL_PLANNING: "Project my goal scenario.",
        AgentId.NEWS_SYNTHESIZER: "Summarize recent DEMO company news.",
        AgentId.TAX_EDUCATION: "What is a SEP IRA for tax year 2026?",
    }
    all_agent_message = (
        "Explain diversification and 2026 investment taxes, analyze my portfolio, "
        "describe DEMO historical price data, project my goal scenario, and summarize recent "
        "DEMO company news."
    )
    result = application.run(
        WorkflowRequest(
            execution_id="run-live-model-m4-1",
            session_id="session-live-model-m4-1",
            workflow_id="finance-assistant",
            workflow_version="1",
            message=messages[only_agent] if only_agent is not None else all_agent_message,
            context_references=(
                "portfolio-live-context",
                "market-live-context",
                "goal-live-context",
                "news-live-context",
            ),
            deadline_at=datetime.now(UTC) + timedelta(minutes=3),
        )
    )

    assert result.status in {WorkflowStatus.COMPLETED, WorkflowStatus.PARTIAL}, result
    assert set(result.selected_agent_ids) == expected_agents
    assert {item.agent_id for item in result.agent_results} == expected_agents
    assert all(
        item.status in {AgentResultStatus.OK, AgentResultStatus.PARTIAL}
        for item in result.agent_results
    )
    by_agent = {item.agent_id: item for item in result.agent_results}
    if AgentId.FINANCE_QA in expected_agents:
        assert by_agent[AgentId.FINANCE_QA].evidence
    if AgentId.TAX_EDUCATION in expected_agents:
        assert by_agent[AgentId.TAX_EDUCATION].facts[0]["tax_year"] == 2026
    if AgentId.PORTFOLIO_ANALYSIS in expected_agents:
        assert (
            by_agent[AgentId.PORTFOLIO_ANALYSIS].facts[0]["calculation_policy_version"]
            == "finance-calculation-v1"
        )
    if AgentId.GOAL_PLANNING in expected_agents:
        assert by_agent[AgentId.GOAL_PLANNING].facts[0]["annual_return_rate"] == "0.05"
    if AgentId.MARKET_ANALYSIS in expected_agents:
        assert by_agent[AgentId.MARKET_ANALYSIS].facts[0]["provider"] == "fake_market_data_v1"
    if AgentId.NEWS_SYNTHESIZER in expected_agents:
        assert by_agent[AgentId.NEWS_SYNTHESIZER].evidence

    events = event_repository.list_for_run(
        "run-live-model-m4-1",
        session_id="session-live-model-m4-1",
    )
    model_events = [event for event in events if event.event_type == EventType.MODEL_COMPLETED]
    assert len(model_events) == len(expected_agents) + 1
    assert all(event.safe_metadata["provider"] == "openai" for event in model_events)
    assert all(event.safe_metadata["model_id"] == "gpt-6.1-sol" for event in model_events)
    assert any(event.node_id == "router" for event in model_events)
    assert all(
        event.usage.availability == MeasurementAvailability.MEASURED for event in model_events
    )
    serialized = "".join(event.model_dump_json() for event in events)
    assert "Diversification spreads exposure" not in serialized
    assert settings.openai_api_key.get_secret_value() not in serialized


def _evidence(
    *,
    logical_kb: LogicalKnowledgeBase,
    text: str,
    now: datetime,
) -> Evidence:
    return Evidence(
        chunk_id=f"{logical_kb.value}-live-chunk",
        document_id=f"{logical_kb.value}-live-document",
        title="M4.1 permitted synthetic evidence",
        publisher="AI Finance Assistant test fixture",
        canonical_url="https://example.invalid/m4-1-live",
        section_path="Synthetic qualification",
        text=text,
        score=1.0,
        rank=1,
        collection_name=f"{logical_kb.value}_live_fixture",
        collection_version="m4-1-live-v1",
        document_version="v1",
        content_hash="a" * 64,
        fetched_at=now,
        tax_years=(2026,) if logical_kb == LogicalKnowledgeBase.TAX else (),
        jurisdiction="US-Federal",
    )


def _contexts(now: datetime) -> InMemoryAgentContextRepository:
    contexts = InMemoryAgentContextRepository()
    portfolio = ImportedPortfolio(
        portfolio_id="portfolio-live",
        base_currency="USD",
        imported_at=now,
        source_kind="manual",
        source_file_hash="b" * 64,
        accounts=(
            ImportedAccount(
                account_id="account-live",
                portfolio_id="portfolio-live",
                account_type="taxable",
                holdings=(
                    ImportedHolding(
                        holding_id="holding-live",
                        account_id="account-live",
                        source_row=1,
                        security=SecurityIdentifier(identifier_type="ticker", value="DEMO"),
                        quantity=Decimal("2"),
                        currency="USD",
                    ),
                ),
            ),
        ),
    )
    contexts.put(
        "session-live-model-m4-1",
        PortfolioAgentContext(
            context_id="portfolio-live-context",
            portfolio=portfolio,
            calculated_at=now,
        ),
    )
    contexts.put(
        "session-live-model-m4-1",
        MarketAgentContext(
            context_id="market-live-context",
            symbol="DEMO",
            currency="USD",
            start_date=date(2026, 10, 23),
            end_date=date(2026, 10, 26),
        ),
    )
    contexts.put(
        "session-live-model-m4-1",
        GoalAgentContext(
            context_id="goal-live-context",
            projection=GoalProjectionRequest(
                projection_id="goal-live",
                currency="USD",
                starting_amount="1000",
                goal_amount="3000",
                contribution_amount="100",
                contribution_frequency="monthly",
                contribution_timing="end",
                horizon_months=12,
                risk_tolerance="moderate",
                scenarios=(
                    GoalScenario(
                        label="user scenario",
                        annual_return_rate="0.05",
                        annual_inflation_rate="0.02",
                    ),
                ),
            ),
        ),
    )
    contexts.put(
        "session-live-model-m4-1",
        NewsAgentContext(
            context_id="news-live-context",
            query="DEMO company financial news",
            symbols=("DEMO",),
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 27),
        ),
    )
    return contexts
