"""Deterministic credential-free structured model adapter."""

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    ModelOutput,
    ModelRequest,
    ModelUsage,
)

_SUMMARIES: dict[AgentId, str] = {
    AgentId.FINANCE_QA: "Educational explanation grounded in the cited Finance evidence.",
    AgentId.PORTFOLIO_ANALYSIS: (
        "Portfolio results are explained from the deterministic snapshot and its coverage."
    ),
    AgentId.MARKET_ANALYSIS: (
        "Market observations describe the requested history without forecasting returns."
    ),
    AgentId.GOAL_PLANNING: (
        "Goal scenarios use only the explicit assumptions in the deterministic projection."
    ),
    AgentId.NEWS_SYNTHESIZER: (
        "News findings are attributed and do not imply a future price direction."
    ),
    AgentId.TAX_EDUCATION: (
        "Tax education is grounded in the cited year-specific U.S. federal evidence."
    ),
}


class DeterministicModelAdapter:
    provider_id = "deterministic"
    model_id = "deterministic-model-v1"
    prompt_version = "deterministic-template-v1"

    def generate(self, request: ModelRequest) -> ModelAdapterResult:
        output = ModelOutput(
            summary=_SUMMARIES[request.agent_id],
        )
        return ModelAdapterResult(
            payload=output.model_dump(mode="json"),
            usage=ModelUsage(
                input_tokens=len(request.evidence) + len(request.facts) + 1,
                output_tokens=12,
                method="deterministic_fixture_count_v1",
            ),
        )
