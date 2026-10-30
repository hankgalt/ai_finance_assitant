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


class SessionState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: Identifier
    label: str | None = Field(default=None, max_length=128)
    state: SessionState
    created_at: AwareDatetime
    updated_at: AwareDatetime
    expires_at: AwareDatetime
    archived_at: AwareDatetime | None = None


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    status: StoredRunStatus
    request_message: str | None = Field(default=None, min_length=1, max_length=20_000)
    result: WorkflowRunResult | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IdempotencyConflict(ValueError):
    """One idempotency key was reused with a different request body."""
