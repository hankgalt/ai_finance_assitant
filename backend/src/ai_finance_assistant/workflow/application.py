"""Application composition for one-provider-bundle-per-Run workflow execution."""

from __future__ import annotations

from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from ai_finance_assistant.agents.context import AgentContextRepository
from ai_finance_assistant.agents.runtime import AgentRuntime
from ai_finance_assistant.agents.specialists import (
    FinanceQAAgent,
    GoalPlanningAgent,
    MarketAnalysisAgent,
    NewsSynthesizerAgent,
    PortfolioAnalysisAgent,
    TaxEducationAgent,
)
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.finance.goal_projection import GoalProjection
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.llm.factory import model_adapter_from_settings
from ai_finance_assistant.llm.ports import ModelAdapter
from ai_finance_assistant.observability.langsmith import LangSmithTracing
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.providers.factory import provider_bundle_from_settings
from ai_finance_assistant.providers.ports import ProviderBundle
from ai_finance_assistant.workflow.events import RunEventRecorder
from ai_finance_assistant.workflow.graph import FinanceWorkflow, SpecialistAgent
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowRunResult
from ai_finance_assistant.workflow.retrieval import KnowledgeRetrieval
from ai_finance_assistant.workflow.routing import IntentRouter

ProviderBundleBuilder = Callable[[Settings], ProviderBundle]
ModelAdapterBuilder = Callable[[Settings], ModelAdapter]


class WorkflowApplication:
    """Hide six-agent assembly while fixing provider and model selection per Run."""

    def __init__(
        self,
        *,
        settings: Settings,
        retrieval: KnowledgeRetrieval,
        contexts: AgentContextRepository,
        event_recorder: RunEventRecorder,
        observability: Observability,
        provider_bundle_builder: ProviderBundleBuilder = provider_bundle_from_settings,
        model_adapter_builder: ModelAdapterBuilder = model_adapter_from_settings,
        checkpointer: BaseCheckpointSaver[str] | None = None,
    ) -> None:
        self._settings = settings
        self._retrieval = retrieval
        self._contexts = contexts
        self._event_recorder = event_recorder
        self._observability = observability
        self._provider_bundle_builder = provider_bundle_builder
        self._model_adapter_builder = model_adapter_builder
        self._checkpointer = checkpointer or InMemorySaver()
        self._langsmith = LangSmithTracing(
            enabled=settings.langsmith_tracing_enabled,
            project=settings.langsmith_project,
            api_key=(
                settings.langsmith_api_key.get_secret_value()
                if settings.langsmith_api_key is not None
                else None
            ),
        )

    def run(self, request: WorkflowRequest) -> WorkflowRunResult:
        providers = self._provider_bundle_builder(self._settings)
        model = self._model_adapter_builder(self._settings)
        runtime = AgentRuntime(
            retrieval=self._retrieval,
            model=model,
            event_recorder=self._event_recorder,
            observability=self._observability,
        )
        agents: dict[AgentId, SpecialistAgent] = {
            AgentId.FINANCE_QA: FinanceQAAgent(runtime=runtime),
            AgentId.PORTFOLIO_ANALYSIS: PortfolioAnalysisAgent(
                runtime=runtime,
                contexts=self._contexts,
                market=providers.market,
                analysis=PortfolioAnalysis(),
            ),
            AgentId.MARKET_ANALYSIS: MarketAnalysisAgent(
                runtime=runtime,
                contexts=self._contexts,
                market=providers.market,
            ),
            AgentId.GOAL_PLANNING: GoalPlanningAgent(
                runtime=runtime,
                contexts=self._contexts,
                projection=GoalProjection(),
            ),
            AgentId.NEWS_SYNTHESIZER: NewsSynthesizerAgent(
                runtime=runtime,
                contexts=self._contexts,
                news=providers.news,
            ),
            AgentId.TAX_EDUCATION: TaxEducationAgent(runtime=runtime),
        }
        workflow = FinanceWorkflow(
            agents=agents,
            event_recorder=self._event_recorder,
            observability=self._observability,
            router=IntentRouter(model=model),
            contexts=self._contexts,
            checkpointer=self._checkpointer,
            maximum_graph_hops=self._settings.workflow_maximum_graph_hops,
        )
        with self._langsmith.activate():
            return workflow.run(request)
