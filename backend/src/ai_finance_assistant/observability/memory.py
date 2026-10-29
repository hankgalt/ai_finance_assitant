"""In-memory observability adapter for behavior tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Literal
from uuid import uuid4

from pydantic import JsonValue

from ai_finance_assistant.observability.ports import TraceContext
from ai_finance_assistant.observability.safe import safe_attributes


@dataclass(frozen=True)
class SpanRecord:
    name: str
    trace_id: str
    parent_span_id: str | None
    span_id: str
    status: Literal["completed", "failed"]
    attributes: dict[str, JsonValue]


@dataclass(frozen=True)
class MetricRecord:
    kind: Literal["counter", "histogram"]
    name: str
    value: int | float
    attributes: dict[str, JsonValue]


_TRACE_ID: ContextVar[str | None] = ContextVar("aifa_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("aifa_span_id", default=None)


class InMemoryObservability:
    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []
        self.metrics: list[MetricRecord] = []
        self._lock = Lock()

    @contextmanager
    def span(
        self, name: str, attributes: Mapping[str, JsonValue] | None = None
    ) -> Iterator[TraceContext]:
        parent_span_id = _SPAN_ID.get()
        trace_id = _TRACE_ID.get() or uuid4().hex
        span_id = uuid4().hex[:16]
        trace_token = _TRACE_ID.set(trace_id)
        span_token = _SPAN_ID.set(span_id)
        status: Literal["completed", "failed"] = "completed"
        try:
            yield TraceContext(trace_id=trace_id)
        except BaseException:
            status = "failed"
            raise
        finally:
            _SPAN_ID.reset(span_token)
            _TRACE_ID.reset(trace_token)
            with self._lock:
                self.spans.append(
                    SpanRecord(
                        name=name,
                        trace_id=trace_id,
                        parent_span_id=parent_span_id,
                        span_id=span_id,
                        status=status,
                        attributes=safe_attributes(attributes),
                    )
                )

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self._record_metric("counter", name, value, attributes)

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self._record_metric("histogram", name, value, attributes)

    def current_trace_id(self) -> str | None:
        return _TRACE_ID.get()

    def _record_metric(
        self,
        kind: Literal["counter", "histogram"],
        name: str,
        value: int | float,
        attributes: Mapping[str, JsonValue] | None,
    ) -> None:
        with self._lock:
            self.metrics.append(
                MetricRecord(
                    kind=kind,
                    name=name,
                    value=value,
                    attributes=safe_attributes(attributes),
                )
            )
