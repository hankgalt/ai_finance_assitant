"""Versioned M5 REST and SSE recovery contracts."""

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import Identifier
from ai_finance_assistant.contracts.errors import SafeError
from ai_finance_assistant.contracts.events import RunEvent
from ai_finance_assistant.finance.models import QuoteSet, SecurityReference
from ai_finance_assistant.persistence.models import RunRecord, SessionRecord


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = Field(default=None, max_length=128)


class SessionList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[SessionRecord, ...]


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(min_length=1, max_length=20_000)
    context_references: tuple[Identifier, ...] = Field(default=(), max_length=20)
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)


class RunList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[RunRecord, ...]


class RunEventHistory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    events: tuple[RunEvent, ...]
    recovery: str = "Use Last-Event-ID for SSE replay or reload this resource and the Run."


class ResponseChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    chunk_id: Identifier
    text: str = Field(max_length=512)
    terminal: bool = True


class CreateSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: Identifier | None = None
    security_references: tuple[SecurityReference, ...] = ()
    quote_set: QuoteSet


class PurgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = Field(default=None, max_length=128)
    deleted_bar_count: int = Field(ge=0)
    memory_cache_cleared: bool = True


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: SafeError
