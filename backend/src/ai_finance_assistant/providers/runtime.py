"""Bounded provider execution: budget, rate, retry, circuit, and in-memory cache."""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from random import uniform
from threading import BoundedSemaphore, RLock
from typing import Generic, TypeVar, cast

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.providers.models import (
    ProviderError,
    ProviderErrorCode,
    ProviderMode,
    ProviderReadiness,
    TimestampQuality,
)

T = TypeVar("T")


@dataclass(frozen=True)
class EndpointPolicy:
    timeout_seconds: float
    max_attempts: int
    base_backoff_seconds: float
    max_backoff_seconds: float
    cache_ttl_seconds: float
    stale_if_error_seconds: float

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between one and five")
        if (
            min(
                self.base_backoff_seconds,
                self.max_backoff_seconds,
                self.cache_ttl_seconds,
                self.stale_if_error_seconds,
            )
            < 0
        ):
            raise ValueError("provider timing values cannot be negative")


@dataclass(frozen=True)
class RuntimeValue(Generic[T]):
    data: T
    data_as_of: datetime | None
    delay_status: DelayStatus
    timestamp_quality: TimestampQuality
    request_id: str | None = None


@dataclass(frozen=True)
class RuntimeOutcome(Generic[T]):
    value: RuntimeValue[T] | None
    served_at: datetime
    retrieved_at: datetime | None
    cache_status: CacheStatus
    cache_age_seconds: float | None
    is_stale: bool
    attempts: int
    error: ProviderError | None = None


class ProviderCallError(Exception):
    """A safe, categorized provider failure; raw payloads and credentials stay outside it."""

    def __init__(
        self,
        code: ProviderErrorCode,
        message: str,
        *,
        retryable: bool,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.detail = ProviderError(
            code=code,
            message=message,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
        )


@dataclass(frozen=True)
class _CacheEntry:
    value: RuntimeValue[object]
    retrieved_at: datetime


class ProviderRuntime:
    """State scoped to one provider in one workflow/demo session."""

    def __init__(
        self,
        *,
        provider_name: str,
        mode: ProviderMode,
        request_budget: int,
        requests_per_window: int,
        rate_window_seconds: float = 60,
        max_concurrency: int = 2,
        max_cache_entries: int = 128,
        circuit_failure_threshold: int = 3,
        circuit_cooldown_seconds: float = 30,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float], float] = lambda cap: uniform(0, cap),
    ) -> None:
        if request_budget < 0 or requests_per_window <= 0:
            raise ValueError("provider budgets must be non-negative and rate limit positive")
        if min(rate_window_seconds, circuit_cooldown_seconds) <= 0:
            raise ValueError("provider windows must be positive")
        if max_concurrency <= 0 or max_cache_entries <= 0 or circuit_failure_threshold <= 0:
            raise ValueError("provider bounds must be positive")
        self.provider_name = provider_name
        self.mode = mode
        self._request_budget = request_budget
        self._requests_per_window = requests_per_window
        self._rate_window_seconds = rate_window_seconds
        self._max_cache_entries = max_cache_entries
        self._failure_threshold = circuit_failure_threshold
        self._circuit_cooldown_seconds = circuit_cooldown_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleeper = sleeper
        self._jitter = jitter
        self._calls_used = 0
        self._recent_calls: deque[datetime] = deque()
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._consecutive_failures = 0
        self._circuit_opened_at: datetime | None = None
        self._lock = RLock()
        self._semaphore = BoundedSemaphore(max_concurrency)

    @property
    def calls_used(self) -> int:
        with self._lock:
            return self._calls_used

    @property
    def remaining_budget(self) -> int:
        with self._lock:
            return max(0, self._request_budget - self._calls_used)

    def readiness(
        self,
        *,
        credential_configured: bool,
        terms_approved: bool,
        required_requests: int = 1,
    ) -> ProviderReadiness:
        if required_requests < 0:
            raise ValueError("required_requests cannot be negative")
        with self._lock:
            circuit_open = self._is_circuit_open(self._now())
            remaining = max(0, self._request_budget - self._calls_used)
        if not credential_configured:
            reason = "Provider credential is not configured."
        elif not terms_approved:
            reason = "Provider account terms and entitlements are not approved."
        elif circuit_open:
            reason = "Provider circuit is open."
        elif remaining < required_requests:
            reason = "Configured workflow request budget is insufficient."
        else:
            reason = "Provider is ready for the declared request budget."
        return ProviderReadiness(
            provider=self.provider_name,
            mode=self.mode,
            ready=(
                credential_configured
                and terms_approved
                and not circuit_open
                and remaining >= required_requests
            ),
            credential_configured=credential_configured,
            terms_approved=terms_approved,
            remaining_request_budget=remaining,
            reason=reason,
        )

    def execute(
        self,
        *,
        cache_key: str,
        policy: EndpointPolicy,
        fetch: Callable[[float], RuntimeValue[T]],
    ) -> RuntimeOutcome[T]:
        served_at = self._now()
        cached = self._cached(cache_key)
        if cached is not None:
            age = (served_at - cached.retrieved_at).total_seconds()
            if age <= policy.cache_ttl_seconds:
                return RuntimeOutcome(
                    value=cast(RuntimeValue[T], cached.value),
                    served_at=served_at,
                    retrieved_at=cached.retrieved_at,
                    cache_status=CacheStatus.HIT,
                    cache_age_seconds=max(0, age),
                    is_stale=False,
                    attempts=0,
                )

        if not self._semaphore.acquire(blocking=False):
            return self._failed_or_stale(
                served_at=served_at,
                cached=cached,
                policy=policy,
                attempts=0,
                error=ProviderError(
                    code=ProviderErrorCode.CONCURRENCY_LIMITED,
                    message="Provider concurrency limit is active.",
                    retryable=True,
                ),
            )

        attempts = 0
        last_error: ProviderError | None = None
        try:
            for attempt_index in range(policy.max_attempts):
                try:
                    self._reserve_call()
                    attempts += 1
                    value = fetch(policy.timeout_seconds)
                except ProviderCallError as exc:
                    last_error = exc.detail
                    self._record_failure(exc.detail)
                    if not exc.detail.retryable or attempt_index + 1 >= policy.max_attempts:
                        break
                    delay = exc.detail.retry_after_seconds
                    if delay is None:
                        cap = min(
                            policy.base_backoff_seconds * (2**attempt_index),
                            policy.max_backoff_seconds,
                        )
                        delay = min(max(self._jitter(cap), 0), cap)
                    self._sleeper(min(delay, policy.max_backoff_seconds))
                    continue
                except Exception:
                    last_error = ProviderError(
                        code=ProviderErrorCode.UNAVAILABLE,
                        message="Provider call failed without a safe response.",
                        retryable=True,
                    )
                    self._record_failure(last_error)
                    break
                self._record_success()
                retrieved_at = self._now()
                self._put_cache(cache_key, value, retrieved_at)
                return RuntimeOutcome(
                    value=value,
                    served_at=retrieved_at,
                    retrieved_at=retrieved_at,
                    cache_status=CacheStatus.MISS,
                    cache_age_seconds=0,
                    is_stale=False,
                    attempts=attempts,
                )
        finally:
            self._semaphore.release()

        if last_error is None:
            last_error = ProviderError(
                code=ProviderErrorCode.UNAVAILABLE,
                message="Provider call did not return a result.",
                retryable=True,
            )
        return self._failed_or_stale(
            served_at=self._now(),
            cached=cached,
            policy=policy,
            attempts=attempts,
            error=last_error,
        )

    def _reserve_call(self) -> None:
        now = self._now()
        with self._lock:
            if self._is_circuit_open(now):
                raise ProviderCallError(
                    ProviderErrorCode.CIRCUIT_OPEN,
                    "Provider circuit is open.",
                    retryable=True,
                )
            if self._calls_used >= self._request_budget:
                raise ProviderCallError(
                    ProviderErrorCode.BUDGET_EXHAUSTED,
                    "Configured workflow request budget is exhausted.",
                    retryable=False,
                )
            cutoff = now - timedelta(seconds=self._rate_window_seconds)
            while self._recent_calls and self._recent_calls[0] <= cutoff:
                self._recent_calls.popleft()
            if len(self._recent_calls) >= self._requests_per_window:
                retry_after = (
                    self._recent_calls[0] + timedelta(seconds=self._rate_window_seconds) - now
                ).total_seconds()
                raise ProviderCallError(
                    ProviderErrorCode.RATE_LIMITED,
                    "Local provider rate limit is active.",
                    retryable=False,
                    retry_after_seconds=max(0, retry_after),
                )
            self._calls_used += 1
            self._recent_calls.append(now)

    def _record_failure(self, error: ProviderError) -> None:
        if not error.retryable:
            return
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._circuit_opened_at = self._now()

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def _is_circuit_open(self, now: datetime) -> bool:
        if self._circuit_opened_at is None:
            return False
        elapsed = (now - self._circuit_opened_at).total_seconds()
        if elapsed >= self._circuit_cooldown_seconds:
            self._circuit_opened_at = None
            self._consecutive_failures = 0
            return False
        return True

    def _cached(self, cache_key: str) -> _CacheEntry | None:
        with self._lock:
            entry = self._cache.get(cache_key)
            if entry is not None:
                self._cache.move_to_end(cache_key)
            return entry

    def _put_cache(self, cache_key: str, value: RuntimeValue[T], retrieved_at: datetime) -> None:
        entry = _CacheEntry(value=cast(RuntimeValue[object], value), retrieved_at=retrieved_at)
        with self._lock:
            self._cache[cache_key] = entry
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._max_cache_entries:
                self._cache.popitem(last=False)

    def _failed_or_stale(
        self,
        *,
        served_at: datetime,
        cached: _CacheEntry | None,
        policy: EndpointPolicy,
        attempts: int,
        error: ProviderError,
    ) -> RuntimeOutcome[T]:
        stale_eligible = error.code in {
            ProviderErrorCode.RATE_LIMITED,
            ProviderErrorCode.TIMEOUT,
            ProviderErrorCode.UNAVAILABLE,
            ProviderErrorCode.BUDGET_EXHAUSTED,
            ProviderErrorCode.CIRCUIT_OPEN,
            ProviderErrorCode.CONCURRENCY_LIMITED,
        }
        if cached is not None and stale_eligible:
            age = max(0, (served_at - cached.retrieved_at).total_seconds())
            if age <= policy.cache_ttl_seconds + policy.stale_if_error_seconds:
                return RuntimeOutcome(
                    value=cast(RuntimeValue[T], cached.value),
                    served_at=served_at,
                    retrieved_at=cached.retrieved_at,
                    cache_status=CacheStatus.STALE,
                    cache_age_seconds=age,
                    is_stale=True,
                    attempts=attempts,
                    error=error,
                )
        return RuntimeOutcome(
            value=None,
            served_at=served_at,
            retrieved_at=None,
            cache_status=CacheStatus.NOT_APPLICABLE,
            cache_age_seconds=None,
            is_stale=False,
            attempts=attempts,
            error=error,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider clock must return a timezone-aware datetime")
        return value
