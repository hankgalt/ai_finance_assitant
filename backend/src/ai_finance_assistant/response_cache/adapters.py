"""Disabled, unavailable, and deterministic response-cache adapters."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheLookupRequest,
    CacheLookupResult,
    CacheMatchKind,
    CacheReadiness,
    CacheRecord,
    entry_age,
)


class DisabledModelResponseCache:
    def lookup(self, request: CacheLookupRequest) -> CacheLookupResult:
        del request
        return CacheLookupResult(
            outcome=CacheLookupOutcome.BYPASS,
            reason="cache_disabled",
        )

    def store(self, record: CacheRecord) -> None:
        del record

    def purge_session(self, session_scope: str) -> int:
        del session_scope
        return 0

    def purge_all(self) -> int:
        return 0

    def readiness(self) -> CacheReadiness:
        return CacheReadiness(
            configured=False,
            available=True,
            adapter="disabled",
            detail="The optional model response cache is disabled.",
        )

    def close(self) -> None:
        return None


class UnavailableModelResponseCache(DisabledModelResponseCache):
    def __init__(self, *, adapter: str, detail: str) -> None:
        self._adapter = adapter
        self._detail = detail

    def lookup(self, request: CacheLookupRequest) -> CacheLookupResult:
        del request
        return CacheLookupResult(
            outcome=CacheLookupOutcome.ERROR,
            reason="cache_unavailable",
        )

    def store(self, record: CacheRecord) -> None:
        del record
        raise ConnectionError("optional response cache is unavailable")

    def readiness(self) -> CacheReadiness:
        return CacheReadiness(
            configured=True,
            available=False,
            adapter=self._adapter,
            detail=self._detail,
        )


class InMemoryModelResponseCache:
    """Deterministic process-local adapter for contracts and calibration tests."""

    def __init__(
        self,
        *,
        maximum_entries: int = 1_000,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if maximum_entries < 1:
            raise ValueError("maximum_entries must be positive")
        self._maximum_entries = maximum_entries
        self._clock = clock
        self._records: dict[str, CacheRecord] = {}
        self._lock = Lock()

    def lookup(self, request: CacheLookupRequest) -> CacheLookupResult:
        with self._lock:
            self._purge_expired(request.observed_at)
            candidates = tuple(
                record
                for record in self._records.values()
                if record.kind == request.kind
                and record.session_scope == request.session_scope
                and record.filter_fingerprint == request.filter_fingerprint
            )
        exact = next(
            (
                record
                for record in candidates
                if record.normalized_query == request.normalized_query
            ),
            None,
        )
        if exact is not None:
            return CacheLookupResult(
                outcome=CacheLookupOutcome.HIT,
                record=exact,
                match_kind=CacheMatchKind.EXACT,
                similarity=1.0 if request.vector else None,
                entry_age_seconds=entry_age(exact, request.observed_at),
            )
        if not request.allow_semantic or not request.vector:
            return CacheLookupResult(outcome=CacheLookupOutcome.MISS, reason="no_exact_match")
        scored = tuple(
            (record, _cosine_similarity(request.vector, record.vector))
            for record in candidates
            if record.vector
        )
        if not scored:
            return CacheLookupResult(outcome=CacheLookupOutcome.MISS, reason="no_candidate")
        record, similarity = max(scored, key=lambda item: item[1])
        if similarity < request.minimum_similarity:
            return CacheLookupResult(
                outcome=CacheLookupOutcome.MISS,
                similarity=similarity,
                reason="below_minimum_similarity",
            )
        return CacheLookupResult(
            outcome=CacheLookupOutcome.HIT,
            record=record,
            match_kind=CacheMatchKind.SEMANTIC,
            similarity=similarity,
            entry_age_seconds=entry_age(record, request.observed_at),
        )

    def store(self, record: CacheRecord) -> None:
        key = _record_key(record)
        with self._lock:
            self._purge_expired(self._clock())
            if key not in self._records and len(self._records) >= self._maximum_entries:
                oldest_key = min(
                    self._records,
                    key=lambda item: self._records[item].created_at,
                )
                del self._records[oldest_key]
            self._records[key] = record

    def purge_session(self, session_scope: str) -> int:
        with self._lock:
            keys = tuple(
                key
                for key, record in self._records.items()
                if record.session_scope == session_scope
            )
            for key in keys:
                del self._records[key]
        return len(keys)

    def purge_all(self) -> int:
        with self._lock:
            count = len(self._records)
            self._records.clear()
        return count

    def readiness(self) -> CacheReadiness:
        return CacheReadiness(
            configured=True,
            available=True,
            adapter="in_memory",
            detail="The deterministic process-local response cache is ready.",
        )

    def close(self) -> None:
        return None

    def _purge_expired(self, observed_at: datetime) -> None:
        expired = tuple(
            key for key, record in self._records.items() if record.expires_at <= observed_at
        )
        for key in expired:
            del self._records[key]


def _record_key(record: CacheRecord) -> str:
    material = "\0".join(
        (
            record.kind.value,
            record.session_scope,
            record.filter_fingerprint,
            record.normalized_query,
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(first * second for first, second in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))
