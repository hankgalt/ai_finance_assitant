"""RunEvent v1 contract for synthetic M0 fixtures and future measured execution."""

from enum import StrEnum

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from ai_finance_assistant.contracts.common import Identifier, ShortText
from ai_finance_assistant.contracts.errors import SafeError


class EventType(StrEnum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_PARTIAL = "run_partial"
    RUN_FAILED = "run_failed"
    ROUTE_SELECTED = "route_selected"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    RETRIEVAL_STARTED = "retrieval_started"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    RETRIEVAL_FAILED = "retrieval_failed"
    MODEL_STARTED = "model_started"
    MODEL_COMPLETED = "model_completed"
    MODEL_FAILED = "model_failed"
    RESPONSE_CHUNK = "response_chunk"


class EventStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class MeasurementAvailability(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class RoutingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_node_ids: tuple[Identifier, ...]
    outcome: ShortText
    reason_category: ShortText


class ToolResultMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_status: EventStatus
    provider: str | None = Field(default=None, max_length=128)
    record_count: int | None = Field(default=None, ge=0)
    freshness: str | None = Field(default=None, max_length=64)
    cache_status: str | None = Field(default=None, max_length=64)
    error_reference: Identifier | None = None


class UsageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    availability: MeasurementAvailability = MeasurementAvailability.UNAVAILABLE
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_amount: float | None = Field(default=None, ge=0)
    cost_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    cost_unavailable_reason: str | None = Field(
        default="Model cost is not available.",
        max_length=256,
    )
    method: str | None = Field(default=None, max_length=128)
    unavailable_reason: str | None = Field(default="Model usage is not available.", max_length=256)

    @model_validator(mode="after")
    def validate_availability(self) -> "UsageMetadata":
        measurements = (
            self.input_tokens,
            self.output_tokens,
            self.total_tokens,
            self.cost_amount,
        )
        if self.availability == MeasurementAvailability.UNAVAILABLE:
            if any(value is not None for value in measurements):
                raise ValueError("unavailable usage cannot contain measurements")
            if not self.unavailable_reason:
                raise ValueError("unavailable usage requires a reason")
        else:
            if not self.method:
                raise ValueError("measured or estimated usage requires a method")
            if self.unavailable_reason is not None:
                raise ValueError("available usage cannot contain an unavailable reason")
        if self.cost_amount is None and not self.cost_unavailable_reason:
            raise ValueError("missing model cost requires an unavailable reason")
        if self.cost_amount is not None:
            if self.cost_currency is None:
                raise ValueError("available model cost requires a currency")
            if self.cost_unavailable_reason is not None:
                raise ValueError("available model cost cannot contain an unavailable reason")
        return self


class RetrievalSourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: str = Field(min_length=1, max_length=64)
    collection_version: Identifier
    source_id: Identifier
    chunk_id: Identifier
    rank: int = Field(ge=1)
    score: float | None = None
    score_type: str | None = Field(default=None, max_length=64)


class RetrievalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str = Field(min_length=1, max_length=64)
    sources: tuple[RetrievalSourceMetadata, ...] = ()


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    event_id: Identifier
    execution_id: Identifier
    trace_id: Identifier | None = None
    trace_unavailable_reason: str | None = Field(default=None, max_length=256)
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    sequence: int = Field(ge=0)
    node_id: Identifier
    agent_id: Identifier | None = None
    tool_call_id: Identifier | None = None
    tool_name: str | None = Field(default=None, max_length=128)
    parent_event_id: Identifier | None = None
    event_type: EventType
    status: EventStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    duration_unavailable_reason: str | None = Field(default=None, max_length=256)
    routing: RoutingMetadata | None = None
    tool_result: ToolResultMetadata | None = None
    error: SafeError | None = None
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    retrieval: RetrievalMetadata | None = None
    summary: ShortText
    safe_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "RunEvent":
        if self.trace_id is None and not self.trace_unavailable_reason:
            raise ValueError("missing trace_id requires an unavailable reason")
        if self.trace_id is not None and self.trace_unavailable_reason is not None:
            raise ValueError("available trace_id cannot contain an unavailable reason")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        if self.duration_ms is None and not self.duration_unavailable_reason:
            raise ValueError("missing duration requires an unavailable reason")
        if self.duration_ms is not None and self.duration_unavailable_reason is not None:
            raise ValueError("measured duration cannot contain an unavailable reason")
        if self.event_type == EventType.ROUTE_SELECTED and self.routing is None:
            raise ValueError("route_selected events require routing metadata")
        if self.event_type in {
            EventType.TOOL_STARTED,
            EventType.TOOL_COMPLETED,
            EventType.TOOL_FAILED,
        } and (self.tool_call_id is None or self.tool_name is None):
            raise ValueError("tool events require a tool_call_id and tool_name")
        if self.status == EventStatus.FAILED and self.error is None:
            raise ValueError("failed events require a safe error")
        return self
