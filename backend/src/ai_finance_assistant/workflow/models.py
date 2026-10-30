"""Versioned workflow request and result contracts."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.agents import AgentId, AgentResult
from ai_finance_assistant.contracts.common import Identifier, NarrativeText, ShortText
from ai_finance_assistant.contracts.errors import SafeError


class WorkflowStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CLARIFICATION = "clarification"


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    message: str = Field(min_length=1, max_length=20_000)
    context_references: tuple[Identifier, ...] = ()
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)
    deadline_at: AwareDatetime


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
    trace_id: Identifier | None = None
    trace_unavailable_reason: str | None = Field(default=None, max_length=256)
