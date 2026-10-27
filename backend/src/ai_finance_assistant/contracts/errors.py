"""Stable, user-safe error contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ai_finance_assistant.contracts.common import ShortText


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    AUTHORIZATION = "authorization"
    NOT_READY = "not_ready"
    NO_EVIDENCE = "no_evidence"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    RATE_LIMITED = "rate_limited"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    PARTIAL = "partial"


class SafeError(BaseModel):
    """An error safe to return to clients and persist in privacy-filtered traces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$")
    category: ErrorCategory
    message: ShortText
    retryable: bool = False
    attempt_count: int = Field(default=1, ge=1)
    safe_details: dict[str, JsonValue] = Field(default_factory=dict)
