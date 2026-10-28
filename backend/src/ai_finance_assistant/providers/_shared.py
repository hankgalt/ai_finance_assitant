"""Private helpers shared by provider adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from ai_finance_assistant.providers.models import (
    ProviderEnvelope,
    ProviderError,
    ProviderErrorCode,
    ProviderMode,
    ProviderStatus,
    ProviderWarning,
)
from ai_finance_assistant.providers.runtime import RuntimeOutcome

T = TypeVar("T")


def result_status(error: ProviderError | None, *, has_data: bool) -> ProviderStatus:
    if has_data:
        return ProviderStatus.SUCCESS
    if error is None:
        return ProviderStatus.EMPTY
    return {
        ProviderErrorCode.INVALID_REQUEST: ProviderStatus.INVALID_REQUEST,
        ProviderErrorCode.UNAUTHORIZED: ProviderStatus.UNAUTHORIZED,
        ProviderErrorCode.ENTITLEMENT_REQUIRED: ProviderStatus.ENTITLEMENT_REQUIRED,
        ProviderErrorCode.RATE_LIMITED: ProviderStatus.RATE_LIMITED,
        ProviderErrorCode.TIMEOUT: ProviderStatus.TIMEOUT,
        ProviderErrorCode.MALFORMED_RESPONSE: ProviderStatus.MALFORMED_RESPONSE,
        ProviderErrorCode.UNAVAILABLE: ProviderStatus.UNAVAILABLE,
        ProviderErrorCode.BUDGET_EXHAUSTED: ProviderStatus.BUDGET_EXHAUSTED,
        ProviderErrorCode.CIRCUIT_OPEN: ProviderStatus.CIRCUIT_OPEN,
        ProviderErrorCode.CONCURRENCY_LIMITED: ProviderStatus.CONCURRENCY_LIMITED,
    }[error.code]


def envelope_from_outcome(
    outcome: RuntimeOutcome[T],
    *,
    provider: str,
    mode: ProviderMode,
    entitlement: str,
) -> ProviderEnvelope:
    value = outcome.value
    return ProviderEnvelope(
        provider=provider,
        mode=mode,
        entitlement=entitlement,
        served_at=outcome.served_at,
        retrieved_at=outcome.retrieved_at,
        data_as_of=value.data_as_of if value is not None else None,
        delay_status=value.delay_status if value is not None else "unknown",
        timestamp_quality=value.timestamp_quality if value is not None else "unavailable",
        cache_status=outcome.cache_status,
        cache_age_seconds=outcome.cache_age_seconds,
        is_stale=outcome.is_stale,
        is_synthetic=mode == ProviderMode.CREDENTIAL_FREE,
        request_id=value.request_id if value is not None else None,
        attempts=outcome.attempts,
    )


def warnings_from_outcome(outcome: RuntimeOutcome[T]) -> tuple[ProviderWarning, ...]:
    if not outcome.is_stale or outcome.error is None:
        return ()
    return (
        ProviderWarning(
            code="STALE_CACHE_FALLBACK",
            message=f"Serving stale cached data after {outcome.error.code.value}.",
        ),
    )


def retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return min(max(value, 0), 3600)
