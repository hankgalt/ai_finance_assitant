"""Privacy-safe structured logging and request correlation."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from ai_finance_assistant.core.redaction import redact_text

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "correlation_id": correlation_id.get(),
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
