"""Stable model-adapter failures that never contain provider payloads."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import JsonValue

from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError


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


def model_failure_to_safe_error(failure: ModelProviderError) -> SafeError:
    """Map provider failures once for agents, routing, and graph synthesis."""

    code_and_category = {
        ModelErrorCode.NOT_READY: ("MODEL_NOT_READY", ErrorCategory.NOT_READY),
        ModelErrorCode.AUTHENTICATION_FAILED: (
            "MODEL_AUTHENTICATION_FAILED",
            ErrorCategory.AUTHORIZATION,
        ),
        ModelErrorCode.RATE_LIMITED: ("MODEL_RATE_LIMITED", ErrorCategory.RATE_LIMITED),
        ModelErrorCode.TIMEOUT: ("MODEL_TIMEOUT", ErrorCategory.TIMEOUT),
        ModelErrorCode.UNAVAILABLE: (
            "MODEL_PROVIDER_UNAVAILABLE",
            ErrorCategory.UPSTREAM_UNAVAILABLE,
        ),
        ModelErrorCode.REFUSED: ("MODEL_REFUSED", ErrorCategory.UPSTREAM_UNAVAILABLE),
        ModelErrorCode.INCOMPLETE: ("MODEL_INCOMPLETE", ErrorCategory.UPSTREAM_UNAVAILABLE),
        ModelErrorCode.MALFORMED_OUTPUT: (
            "MODEL_OUTPUT_INVALID",
            ErrorCategory.UPSTREAM_UNAVAILABLE,
        ),
        ModelErrorCode.REQUEST_BUDGET_EXHAUSTED: (
            "MODEL_REQUEST_BUDGET_EXHAUSTED",
            ErrorCategory.RATE_LIMITED,
        ),
        ModelErrorCode.INPUT_BUDGET_EXCEEDED: (
            "MODEL_INPUT_BUDGET_EXCEEDED",
            ErrorCategory.VALIDATION,
        ),
        ModelErrorCode.DEADLINE_EXCEEDED: (
            "MODEL_DEADLINE_EXCEEDED",
            ErrorCategory.TIMEOUT,
        ),
    }
    code, category = code_and_category[failure.code]
    safe_details: dict[str, JsonValue] = {}
    if failure.retry_after_seconds is not None:
        safe_details["retry_after_seconds"] = failure.retry_after_seconds
    return SafeError(
        code=code,
        category=category,
        message=failure.message,
        retryable=failure.retryable,
        attempt_count=failure.attempt_count,
        safe_details=safe_details,
    )
