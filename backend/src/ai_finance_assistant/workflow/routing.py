"""Schema-validated LLM routing for the six specialist agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.llm.models import (
    ModelUsage,
    RoutingModelOutput,
    RoutingModelRequest,
    RoutingReason,
)
from ai_finance_assistant.llm.ports import ModelAdapter


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_agent_ids: tuple[AgentId, ...] = Field(max_length=6)
    reason_category: RoutingReason
    usage: ModelUsage = Field(default_factory=ModelUsage)


class IntentRouter:
    def __init__(self, *, model: ModelAdapter) -> None:
        self._model = model

    @property
    def model_metadata(self) -> dict[str, str]:
        return {
            "provider": self._model.provider_id,
            "model_id": self._model.model_id,
            "prompt_version": self._model.routing_prompt_version,
        }

    def route(
        self,
        message: str,
        *,
        previous_agent_ids: tuple[AgentId, ...] = (),
        deadline_at: datetime,
    ) -> RouteDecision:
        result = self._model.route(
            RoutingModelRequest(
                user_message=message,
                previous_agent_ids=previous_agent_ids,
                deadline_at=deadline_at,
            )
        )
        output = RoutingModelOutput.model_validate(result.payload)
        return RouteDecision(
            selected_agent_ids=output.selected_agent_ids,
            reason_category=output.reason_category,
            usage=result.usage,
        )
