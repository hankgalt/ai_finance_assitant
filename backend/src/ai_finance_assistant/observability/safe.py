"""Privacy filtering and failure isolation for observability adapters."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress

from pydantic import JsonValue

from ai_finance_assistant.core.redaction import sanitize_metadata
from ai_finance_assistant.observability.ports import Observability, TraceContext

SAFE_OBSERVABILITY_ATTRIBUTE_KEYS = frozenset(
    {
        "agent_id",
        "cache_status",
        "collection_version",
        "failure_category",
        "http_method",
        "metric_name",
        "model_id",
        "operation",
        "page",
        "prompt_version",
        "provider",
        "rating",
        "result_status",
        "route",
        "status_class",
        "strategy",
        "workflow_version",
    }
)


def safe_attributes(
    attributes: Mapping[str, JsonValue] | None,
) -> dict[str, JsonValue]:
    return sanitize_metadata(
        attributes or {},
        allowed_keys=SAFE_OBSERVABILITY_ATTRIBUTE_KEYS,
    )


class SafeObservability:
    """Keep telemetry failures and unsafe attributes outside product behavior."""

    def __init__(self, delegate: Observability) -> None:
        self._delegate = delegate

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> Iterator[TraceContext]:
        try:
            manager = self._delegate.span(name, safe_attributes(attributes))
            trace = manager.__enter__()
        except Exception:
            yield TraceContext(trace_id=None)
            return
        try:
            yield trace
        except BaseException as exc:
            with suppress(Exception):
                manager.__exit__(type(exc), exc, exc.__traceback__)
            raise
        else:
            with suppress(Exception):
                manager.__exit__(None, None, None)

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        try:
            self._delegate.count(name, value, safe_attributes(attributes))
        except Exception:
            return

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        try:
            self._delegate.observe(name, value, safe_attributes(attributes))
        except Exception:
            return

    def current_trace_id(self) -> str | None:
        try:
            return self._delegate.current_trace_id()
        except Exception:
            return None
