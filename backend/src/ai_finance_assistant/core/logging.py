"""Privacy-safe structured logging and request correlation."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from ai_finance_assistant.core.redaction import redact_text

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
execution_id: ContextVar[str | None] = ContextVar("execution_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "request_id": correlation_id.get(),
            "trace_id": format(span_context.trace_id, "032x") if span_context.is_valid else None,
            "span_id": format(span_context.span_id, "016x") if span_context.is_valid else None,
            "session_id": session_id.get(),
            "execution_id": execution_id.get(),
            "run_id": execution_id.get(),
        }
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def set_correlation_id(value: str) -> Token[str | None]:
    return correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    correlation_id.reset(token)


def set_session_id(value: str) -> Token[str | None]:
    return session_id.set(value)


def reset_session_id(token: Token[str | None]) -> None:
    session_id.reset(token)


def set_execution_id(value: str) -> Token[str | None]:
    return execution_id.set(value)


def reset_execution_id(token: Token[str | None]) -> None:
    execution_id.reset(token)
