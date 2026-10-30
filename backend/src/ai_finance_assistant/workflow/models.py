"""Versioned workflow request and result contracts."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from ai_finance_assistant.contracts.agents import AgentId, AgentResult
from ai_finance_assistant.contracts.common import Identifier, NarrativeText, ShortText
from ai_finance_assistant.contracts.errors import SafeError


class WorkflowStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CLARIFICATION = "clarification"


class RequiredInputKind(StrEnum):
    PORTFOLIO_SELECTION = "portfolio_selection"


class RequiredInputSelectionMode(StrEnum):
    ONE_OR_EXPLICIT_COMPARISON = "one_or_explicit_comparison"


class RequiredInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: RequiredInputKind
    agent_id: AgentId
    selection_mode: RequiredInputSelectionMode
    prompt: ShortText


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    message: str = Field(min_length=1, max_length=20_000)
    context_references: tuple[Identifier, ...] = ()
    continuation_of_execution_id: Identifier | None = None
    continuation_agent_ids: tuple[AgentId, ...] = Field(default=(), max_length=6)
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)
    deadline_at: AwareDatetime

    @model_validator(mode="after")
    def validate_continuation(self) -> "WorkflowRequest":
        if self.continuation_of_execution_id is None and self.continuation_agent_ids:
            raise ValueError("continuation agents require an originating execution")
        if self.continuation_of_execution_id is not None and not self.continuation_agent_ids:
            raise ValueError("a continuation requires its previously selected agents")
        if len(set(self.continuation_agent_ids)) != len(self.continuation_agent_ids):
            raise ValueError("continuation agents must be distinct")
        return self


class WorkflowRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    status: WorkflowStatus
    selected_agent_ids: tuple[AgentId, ...]
    agent_results: tuple[AgentResult, ...]
    summary: NarrativeText
    warnings: tuple[ShortText, ...] = ()
    errors: tuple[SafeError, ...] = ()
    required_input: RequiredInput | None = None
    continuation_of_execution_id: Identifier | None = None
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)
    trace_id: Identifier | None = None
    trace_unavailable_reason: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_required_input(self) -> "WorkflowRunResult":
        if self.required_input is not None:
            if self.status != WorkflowStatus.CLARIFICATION:
                raise ValueError("required input is valid only for a clarification result")
            if self.required_input.agent_id not in self.selected_agent_ids:
                raise ValueError("required input agent must be selected by the router")
        return self
