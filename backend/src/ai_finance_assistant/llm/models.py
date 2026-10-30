"""Versioned, minimized model request and response contracts."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.common import Identifier, NarrativeText, ShortText


class ModelEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: Identifier
    content: str = Field(min_length=1, max_length=8_000)


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    agent_id: AgentId
    user_message: str = Field(min_length=1, max_length=20_000)
    instructions: str = Field(min_length=1, max_length=4_000)
    evidence: tuple[ModelEvidence, ...] = Field(default=(), max_length=10)
    facts: tuple[dict[str, JsonValue], ...] = Field(default=(), max_length=100)
    max_output_tokens: int = Field(default=1_200, ge=1, le=4_000)
    deadline_at: AwareDatetime


class ModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    summary: NarrativeText = Field(
        description="Complete user-facing narrative grounded in the supplied evidence and facts."
    )
    warnings: tuple[ShortText, ...] = Field(
        default=(),
        max_length=20,
        description=(
            "User-relevant domain limitations or missing evidence only; never internal model or "
            "provider mechanics."
        ),
    )


class ModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    method: str | None = Field(default=None, max_length=128)


class ModelAdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, JsonValue]
    usage: ModelUsage = Field(default_factory=ModelUsage)


class RoutingReason(StrEnum):
    SINGLE_DOMAIN = "single_domain"
    MULTI_DOMAIN = "multi_domain"
    CLARIFICATION_REQUIRED = "clarification_required"
    CHECKPOINT_FOLLOW_UP = "checkpoint_follow_up"
    OUT_OF_SCOPE = "out_of_scope"


class RoutingModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    user_message: str = Field(min_length=1, max_length=20_000)
    previous_agent_ids: tuple[AgentId, ...] = Field(default=(), max_length=6)
    deadline_at: AwareDatetime


class RoutingModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    selected_agent_ids: tuple[AgentId, ...] = Field(default=(), max_length=6)
    reason_category: RoutingReason

    @model_validator(mode="after")
    def validate_decision(self) -> "RoutingModelOutput":
        if len(set(self.selected_agent_ids)) != len(self.selected_agent_ids):
            raise ValueError("routing decisions cannot select an agent more than once")
        if not self.selected_agent_ids:
            if self.reason_category not in {
                RoutingReason.CLARIFICATION_REQUIRED,
                RoutingReason.OUT_OF_SCOPE,
            }:
                raise ValueError("an empty route requires clarification_required or out_of_scope")
        elif self.reason_category in {
            RoutingReason.CLARIFICATION_REQUIRED,
            RoutingReason.OUT_OF_SCOPE,
        }:
            raise ValueError("a selected route cannot require clarification or be out of scope")
        elif (
            len(self.selected_agent_ids) == 1 and self.reason_category == RoutingReason.MULTI_DOMAIN
        ):
            raise ValueError("a single selected agent cannot use multi_domain")
        elif (
            len(self.selected_agent_ids) > 1 and self.reason_category == RoutingReason.SINGLE_DOMAIN
        ):
            raise ValueError("multiple selected agents cannot use single_domain")
        return self
