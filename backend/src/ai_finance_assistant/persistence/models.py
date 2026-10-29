"""Small persistence-facing resource contracts."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import Identifier
from ai_finance_assistant.workflow.models import WorkflowRunResult


class StoredRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CLARIFICATION = "clarification"


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: Identifier
    label: str | None = Field(default=None, max_length=128)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    expires_at: AwareDatetime


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    status: StoredRunStatus
    result: WorkflowRunResult | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IdempotencyConflict(ValueError):
    """One idempotency key was reused with a different request body."""
