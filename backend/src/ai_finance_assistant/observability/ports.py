"""Small vendor-neutral tracing and metrics interface."""

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Protocol

from pydantic import JsonValue


@dataclass(frozen=True)
class TraceContext:
    trace_id: str | None


class Observability(Protocol):
    def span(
        self, name: str, attributes: Mapping[str, JsonValue] | None = None
    ) -> AbstractContextManager[TraceContext]: ...

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None: ...

    def current_trace_id(self) -> str | None: ...


class NoOpObservability:
    @contextmanager
    def span(
        self, name: str, attributes: Mapping[str, JsonValue] | None = None
    ) -> Iterator[TraceContext]:
        del name, attributes
        yield TraceContext(trace_id=None)

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        del name, value, attributes

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        del name, value, attributes

    def current_trace_id(self) -> str | None:
        return None
