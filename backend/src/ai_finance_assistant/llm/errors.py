"""Stable model-adapter failures that never contain provider payloads."""

from dataclasses import dataclass
from enum import StrEnum


class ModelErrorCode(StrEnum):
    NOT_READY = "not_ready"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    MALFORMED_OUTPUT = "malformed_output"
    REQUEST_BUDGET_EXHAUSTED = "request_budget_exhausted"
    INPUT_BUDGET_EXCEEDED = "input_budget_exceeded"
    DEADLINE_EXCEEDED = "deadline_exceeded"


@dataclass
class ModelProviderError(Exception):
    code: ModelErrorCode
    message: str
    retryable: bool = False
    attempt_count: int = 1
    retry_after_seconds: float | None = None

    def __str__(self) -> str:
        return self.message
