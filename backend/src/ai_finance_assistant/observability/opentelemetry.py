"""OpenTelemetry runtime adapter with bounded, privacy-filtered attributes."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import cast

from opentelemetry import metrics, trace
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.trace import Status, StatusCode, Tracer
from pydantic import JsonValue

from ai_finance_assistant.observability.ports import TraceContext
from ai_finance_assistant.observability.safe import safe_attributes

AttributeValue = str | bool | int | float | tuple[str, ...]


class OpenTelemetryObservability:
    def __init__(
        self,
        *,
        tracer: Tracer | None = None,
        meter: Meter | None = None,
    ) -> None:
        self._tracer = tracer or trace.get_tracer("ai_finance_assistant.workflow")
        self._meter = meter or metrics.get_meter("ai_finance_assistant.workflow")
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> Iterator[TraceContext]:
        with self._tracer.start_as_current_span(
            name,
            attributes=_otel_attributes(attributes),
        ) as current:
            context = current.get_span_context()
            trace_id = format(context.trace_id, "032x") if context.is_valid else None
            try:
                yield TraceContext(trace_id=trace_id)
            except BaseException:
                current.set_status(Status(StatusCode.ERROR))
                raise

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        instrument = self._counters.setdefault(name, self._meter.create_counter(name))
        instrument.add(value, _otel_attributes(attributes))

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        instrument = self._histograms.setdefault(
            name,
            self._meter.create_histogram(name),
        )
        instrument.record(value, _otel_attributes(attributes))

    def current_trace_id(self) -> str | None:
        context = trace.get_current_span().get_span_context()
        return format(context.trace_id, "032x") if context.is_valid else None


def _otel_attributes(
    attributes: Mapping[str, JsonValue] | None,
) -> dict[str, AttributeValue]:
    filtered = safe_attributes(attributes)
    return {
        key: cast(AttributeValue, tuple(value) if isinstance(value, list) else value)
        for key, value in filtered.items()
        if isinstance(value, (str, bool, int, float, list))
    }
