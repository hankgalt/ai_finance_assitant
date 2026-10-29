"""Deterministic credential-free structured model adapter."""

from collections.abc import Mapping

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    ModelOutput,
    ModelRequest,
    ModelUsage,
    RoutingModelOutput,
    RoutingModelRequest,
    RoutingReason,
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
    routing_prompt_version = "deterministic-routing-fixture-v1"

    def __init__(
        self,
        *,
        routing_responses: Mapping[str, RoutingModelOutput] | None = None,
    ) -> None:
        self._routing_responses = {
            _routing_key(message): response
            for message, response in (
                routing_responses
                or {
                    "What is an ETF?": RoutingModelOutput(
                        selected_agent_ids=(AgentId.FINANCE_QA,),
                        reason_category=RoutingReason.SINGLE_DOMAIN,
                    )
                }
            ).items()
        }

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

    def route(self, request: RoutingModelRequest) -> ModelAdapterResult:
        output = self._routing_responses.get(_routing_key(request.user_message))
        if output is None and request.previous_agent_ids:
            output = RoutingModelOutput(
                selected_agent_ids=request.previous_agent_ids,
                reason_category=RoutingReason.CHECKPOINT_FOLLOW_UP,
            )
        if output is None:
            output = RoutingModelOutput(
                selected_agent_ids=(),
                reason_category=RoutingReason.CLARIFICATION_REQUIRED,
            )
        return ModelAdapterResult(
            payload=output.model_dump(mode="json"),
            usage=ModelUsage(
                input_tokens=1,
                output_tokens=1,
                method="deterministic_fixture_count_v1",
            ),
        )


def _routing_key(message: str) -> str:
    return " ".join(message.casefold().split())
