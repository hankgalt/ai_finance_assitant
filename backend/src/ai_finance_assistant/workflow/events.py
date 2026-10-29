"""Privacy-filtered RunEvent recording and in-memory persistence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol

from pydantic import JsonValue

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.errors import SafeError
from ai_finance_assistant.contracts.events import (
    EventStatus,
    EventType,
    RetrievalMetadata,
    RoutingMetadata,
    RunEvent,
    ToolResultMetadata,
    UsageMetadata,
)
from ai_finance_assistant.core.redaction import redact_text, sanitize_metadata
from ai_finance_assistant.observability.ports import Observability


@dataclass(frozen=True)
class EventIdentity:
    execution_id: str
    session_id: str
    workflow_id: str
    workflow_version: str


class RunEventRepository(Protocol):
    def append(self, event: RunEvent) -> None: ...

    def list_for_run(self, execution_id: str, *, session_id: str) -> tuple[RunEvent, ...]: ...


class InMemoryRunEventRepository:
    def __init__(self) -> None:
        self._events: dict[str, list[RunEvent]] = defaultdict(list)
        self._lock = Lock()

    def append(self, event: RunEvent) -> None:
        with self._lock:
            existing = self._events[event.execution_id]
            if existing and existing[0].session_id != event.session_id:
                raise ValueError("an execution cannot cross Session scope")
            expected = len(existing) + 1
            if event.sequence != expected:
                raise ValueError(f"expected RunEvent sequence {expected}")
            existing.append(event)

    def list_for_run(self, execution_id: str, *, session_id: str) -> tuple[RunEvent, ...]:
        with self._lock:
            events = tuple(self._events.get(execution_id, ()))
        if events and events[0].session_id != session_id:
            raise PermissionError("RunEvents do not belong to this Session")
        return events


class RunEventRecorder:
    def __init__(
        self,
        *,
        repository: RunEventRepository,
        observability: Observability,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._observability = observability
        self._clock = clock
        self._sequence: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def record(
        self,
        identity: EventIdentity,
        *,
        event_type: EventType,
        status: EventStatus,
        node_id: str,
        summary: str,
        agent_id: AgentId | None = None,
        routing: RoutingMetadata | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_result: ToolResultMetadata | None = None,
        retrieval: RetrievalMetadata | None = None,
        usage: UsageMetadata | None = None,
        error: SafeError | None = None,
        safe_metadata: Mapping[str, JsonValue] | None = None,
        started_at: datetime | None = None,
        completed: bool = False,
        parent_event_id: str | None = None,
    ) -> RunEvent:
        observed_at = self._clock()
        started = started_at or observed_at
        completed_at = observed_at if completed else None
        duration_ms = (
            max(0, int((completed_at - started).total_seconds() * 1000))
            if completed_at is not None
            else None
        )
        with self._lock:
            self._sequence[identity.execution_id] += 1
            sequence = self._sequence[identity.execution_id]
            trace_id = self._observability.current_trace_id()
            event = RunEvent(
                event_id=f"evt:{identity.execution_id}:{sequence}",
                execution_id=identity.execution_id,
                trace_id=trace_id,
                trace_unavailable_reason=(
                    None if trace_id is not None else "Observability trace is unavailable."
                ),
                session_id=identity.session_id,
                workflow_id=identity.workflow_id,
                workflow_version=identity.workflow_version,
                sequence=sequence,
                node_id=node_id,
                agent_id=agent_id.value if agent_id is not None else None,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                parent_event_id=parent_event_id,
                event_type=event_type,
                status=status,
                started_at=started,
                completed_at=completed_at,
                duration_ms=duration_ms,
                duration_unavailable_reason=(
                    None if duration_ms is not None else "The operation has not completed."
                ),
                routing=routing,
                tool_result=tool_result,
                error=error,
                usage=usage or UsageMetadata(),
                retrieval=retrieval,
                summary=redact_text(summary)[:512],
                safe_metadata=sanitize_metadata(safe_metadata or {}),
            )
            self._repository.append(event)
            return event
