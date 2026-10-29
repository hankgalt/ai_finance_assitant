"""Two-tier, rights-gated cache for normalized historical daily market bars."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from threading import Lock, RLock
from time import monotonic
from typing import TypeVar

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.persistence.database import SQLiteDatabase
from ai_finance_assistant.providers.models import (
    AdjustmentBasis,
    CacheCoverageStatus,
    CacheLayer,
    HistoricalRequest,
    HistoricalResult,
    HistoricalSeries,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    PriceBar,
    ProviderEnvelope,
    ProviderMode,
    ProviderStatus,
    ProviderWarning,
    QuoteRequest,
    QuoteResult,
    TimestampQuality,
)
from ai_finance_assistant.providers.ports import MarketDataProvider

_MarketResultT = TypeVar(
    "_MarketResultT",
    HistoricalResult,
    InstrumentSearchResult,
    QuoteResult,
)


@dataclass(frozen=True)
class HistoricalCachePolicy:
    enabled: bool
    deployment_audience: str
    retention_permission: str
    owner_risk_accepted: bool
    retention_days: int
    recent_tail_days: int
    tail_refresh_seconds: int
    memory_ttl_seconds: int
    memory_max_entries: int
    schema_version: str
    policy_version: str

    def retention_label(self, mode: ProviderMode) -> str | None:
        if not self.enabled:
            return None
        if mode == ProviderMode.CREDENTIAL_FREE:
            return "synthetic_fixture"
        if self.retention_permission == "verified":
            return "provider_permission_verified"
        if self.deployment_audience == "owner_only" and self.owner_risk_accepted:
            return "owner_only_unverified_rights_risk_accepted"
        return None


@dataclass(frozen=True)
class HistoricalCacheKey:
    provider: str
    instrument: str
    currency: str
    adjustment_basis: AdjustmentBasis
    schema_version: str
    policy_version: str
    interval: str = "1d"


@dataclass(frozen=True)
class StoredHistory:
    bars: tuple[PriceBar, ...]
    coverage: tuple[tuple[date, date, datetime], ...]
    latest_retrieved_at: datetime | None
    entitlement: str | None
    retention_label: str | None


class HistoricalCacheCorruptionError(RuntimeError):
    """A stored row cannot satisfy the normalized historical-bar schema."""


class SQLiteHistoricalCacheRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def read(
        self,
        key: HistoricalCacheKey,
        *,
        start_date: date,
        end_date: date,
        now: datetime,
    ) -> StoredHistory:
        params = _key_params(key)
        with self._database.read() as connection:
            bar_rows = connection.execute(
                "SELECT * FROM market_bars WHERE provider = ? AND instrument = ? "
                "AND interval = ? AND currency = ? AND adjustment_basis = ? "
                "AND schema_version = ? AND policy_version = ? AND trading_date BETWEEN ? AND ? "
                "AND expires_at > ? ORDER BY trading_date",
                (*params, start_date.isoformat(), end_date.isoformat(), now.isoformat()),
            ).fetchall()
            coverage_rows = connection.execute(
                "SELECT * FROM market_coverage WHERE provider = ? AND instrument = ? "
                "AND interval = ? AND currency = ? AND adjustment_basis = ? "
                "AND schema_version = ? AND policy_version = ? AND end_date >= ? "
                "AND start_date <= ? AND expires_at > ? ORDER BY start_date",
                (*params, start_date.isoformat(), end_date.isoformat(), now.isoformat()),
            ).fetchall()
        try:
            bars = tuple(
                PriceBar(
                    trading_date=date.fromisoformat(row["trading_date"]),
                    open=row["open_value"],
                    high=row["high_value"],
                    low=row["low_value"],
                    close=row["close_value"],
                    volume=row["volume_value"],
                )
                for row in bar_rows
            )
            coverage = tuple(
                (
                    max(start_date, date.fromisoformat(row["start_date"])),
                    min(end_date, date.fromisoformat(row["end_date"])),
                    datetime.fromisoformat(row["retrieved_at"]),
                )
                for row in coverage_rows
            )
            retrievals = [datetime.fromisoformat(row["retrieved_at"]) for row in bar_rows]
        except (TypeError, ValueError, OverflowError) as exc:
            raise HistoricalCacheCorruptionError(
                "Stored historical cache rows failed schema validation."
            ) from exc
        retrievals.extend(item[2] for item in coverage)
        source = bar_rows[-1] if bar_rows else (coverage_rows[-1] if coverage_rows else None)
        return StoredHistory(
            bars=bars,
            coverage=coverage,
            latest_retrieved_at=max(retrievals) if retrievals else None,
            entitlement=None if source is None else str(source["entitlement"]),
            retention_label=None if source is None else str(source["retention_label"]),
        )

    def store(
        self,
        key: HistoricalCacheKey,
        *,
        start_date: date,
        end_date: date,
        bars: tuple[PriceBar, ...],
        retrieved_at: datetime,
        entitlement: str,
        retention_label: str,
        retention_days: int,
    ) -> None:
        expires_at = retrieved_at + timedelta(days=retention_days)
        params = _key_params(key)
        with self._database.transaction() as connection:
            for bar in bars:
                connection.execute(
                    "INSERT INTO market_bars(provider, instrument, interval, trading_date, "
                    "currency, adjustment_basis, schema_version, policy_version, open_value, "
                    "high_value, low_value, close_value, volume_value, retrieved_at, entitlement, "
                    "retention_label, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?) ON CONFLICT("
                    "provider, instrument, interval, trading_date, currency, "
                    "adjustment_basis, schema_version, policy_version) DO UPDATE SET open_value = "
                    "excluded.open_value, high_value = excluded.high_value, low_value = "
                    "excluded.low_value, close_value = excluded.close_value, volume_value = "
                    "excluded.volume_value, retrieved_at = excluded.retrieved_at, entitlement = "
                    "excluded.entitlement, retention_label = excluded.retention_label, "
                    "expires_at = "
                    "excluded.expires_at",
                    (
                        *params[:3],
                        bar.trading_date.isoformat(),
                        *params[3:],
                        str(bar.open),
                        str(bar.high),
                        str(bar.low),
                        str(bar.close),
                        str(bar.volume),
                        retrieved_at.isoformat(),
                        entitlement,
                        retention_label,
                        expires_at.isoformat(),
                    ),
                )
            connection.execute(
                "INSERT INTO market_coverage(provider, instrument, interval, start_date, end_date, "
                "currency, adjustment_basis, schema_version, policy_version, retrieved_at, "
                "entitlement, retention_label, expires_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?) ON CONFLICT(provider, instrument, interval, start_date, end_date, currency, "
                "adjustment_basis, schema_version, policy_version) DO UPDATE SET retrieved_at = "
                "excluded.retrieved_at, entitlement = excluded.entitlement, retention_label = "
                "excluded.retention_label, expires_at = excluded.expires_at",
                (
                    *params[:3],
                    start_date.isoformat(),
                    end_date.isoformat(),
                    *params[3:],
                    retrieved_at.isoformat(),
                    entitlement,
                    retention_label,
                    expires_at.isoformat(),
                ),
            )

    def purge(self, *, provider: str | None = None) -> int:
        where = "" if provider is None else " WHERE provider = ?"
        params: tuple[str, ...] = () if provider is None else (provider,)
        with self._database.transaction() as connection:
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM market_bars" + where,
                    params,
                ).fetchone()[0]
            )
            connection.execute("DELETE FROM market_coverage" + where, params)
            connection.execute("DELETE FROM market_bars" + where, params)
        return count

    def purge_key(self, key: HistoricalCacheKey) -> int:
        params = _key_params(key)
        where = (
            " WHERE provider = ? AND instrument = ? AND interval = ? AND currency = ? "
            "AND adjustment_basis = ? AND schema_version = ? AND policy_version = ?"
        )
        with self._database.transaction() as connection:
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM market_bars" + where,
                    params,
                ).fetchone()[0]
            )
            connection.execute("DELETE FROM market_coverage" + where, params)
            connection.execute("DELETE FROM market_bars" + where, params)
        return count

    def purge_expired(self, *, now: datetime) -> int:
        with self._database.transaction() as connection:
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM market_bars WHERE expires_at <= ?",
                    (now.isoformat(),),
                ).fetchone()[0]
            )
            connection.execute(
                "DELETE FROM market_coverage WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            connection.execute(
                "DELETE FROM market_bars WHERE expires_at <= ?",
                (now.isoformat(),),
            )
        return count


@dataclass(frozen=True)
class _MemoryEntry:
    result: HistoricalResult
    stored_monotonic: float


class HistoricalMemoryCache:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_entries: int,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._monotonic = monotonic_clock
        self._entries: OrderedDict[str, _MemoryEntry] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> HistoricalResult | None:
        now = self._monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if now - entry.stored_monotonic > self._ttl_seconds:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry.result

    def put(self, key: str, result: HistoricalResult) -> None:
        with self._lock:
            self._entries[key] = _MemoryEntry(
                result=result,
                stored_monotonic=self._monotonic(),
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class DurableCachingMarketDataProvider:
    """Decorate one selected provider; never switches provider or synthetic/live mode."""

    def __init__(
        self,
        delegate: MarketDataProvider,
        *,
        repository: SQLiteHistoricalCacheRepository,
        policy: HistoricalCachePolicy,
        observability: Observability,
        memory_cache: HistoricalMemoryCache | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._delegate = delegate
        self._repository = repository
        self._policy = policy
        self._observability = observability
        self._clock = clock
        self._monotonic = monotonic_clock
        self._memory_cache = memory_cache or HistoricalMemoryCache(
            ttl_seconds=policy.memory_ttl_seconds,
            max_entries=policy.memory_max_entries,
            monotonic_clock=monotonic_clock,
        )
        self._key_locks: dict[str, Lock] = {}
        self._key_locks_guard = Lock()

    @property
    def mode(self) -> ProviderMode:
        return self._delegate.mode

    @property
    def provider_name(self) -> str:
        return str(getattr(self._delegate, "provider_name", "unknown_provider"))

    def readiness(self, required_requests: int = 1):  # type: ignore[no-untyped-def]
        return self._delegate.readiness(required_requests)

    def search_instruments(self, request: InstrumentSearchRequest) -> InstrumentSearchResult:
        return self._provider_call(
            "instrument_search",
            lambda: self._delegate.search_instruments(request),
        )

    def get_quote(self, request: QuoteRequest) -> QuoteResult:
        return self._provider_call("quote", lambda: self._delegate.get_quote(request))

    def get_history(self, request: HistoricalRequest) -> HistoricalResult:
        retention_label = self._policy.retention_label(self.mode)
        if retention_label is None:
            return self._provider_call("history", lambda: self._delegate.get_history(request))
        exact_key = self._exact_key(request)
        memory = self._memory_get(exact_key)
        if memory is not None:
            self._metric("memory_hit")
            return _with_cache_provenance(
                memory,
                layer=CacheLayer.MEMORY,
                coverage=CacheCoverageStatus.COMPLETE,
                stale=False,
                now=self._clock(),
            )
        storage_key = HistoricalCacheKey(
            provider=self.provider_name,
            instrument=request.symbol.upper(),
            currency=request.currency,
            adjustment_basis=AdjustmentBasis.RAW,
            schema_version=self._policy.schema_version,
            policy_version=self._policy.policy_version,
        )
        lock = self._lock_for(storage_key)
        with lock:
            memory = self._memory_get(exact_key)
            if memory is not None:
                self._metric("memory_hit")
                return _with_cache_provenance(
                    memory,
                    layer=CacheLayer.MEMORY,
                    coverage=CacheCoverageStatus.COMPLETE,
                    stale=False,
                    now=self._clock(),
                )
            result = self._resolve(request, storage_key, retention_label)
            if result.series is not None and result.error is None:
                self._memory_put(exact_key, result)
            return result

    def _resolve(
        self,
        request: HistoricalRequest,
        key: HistoricalCacheKey,
        retention_label: str,
    ) -> HistoricalResult:
        now = self._clock()
        try:
            stored = self._repository.read(
                key,
                start_date=request.start_date,
                end_date=request.end_date,
                now=now,
            )
        except HistoricalCacheCorruptionError:
            self._repository.purge_key(key)
            self._metric("corrupt_row_purged")
            stored = StoredHistory(
                bars=(),
                coverage=(),
                latest_retrieved_at=None,
                entitlement=None,
                retention_label=None,
            )
        gaps = _coverage_gaps(request.start_date, request.end_date, stored.coverage)
        tail = _stale_tail(
            request,
            stored.coverage,
            now=now,
            tail_days=self._policy.recent_tail_days,
            refresh_seconds=self._policy.tail_refresh_seconds,
        )
        gaps = _merge_ranges((*gaps, *((tail,) if tail is not None else ())))
        if not gaps:
            self._metric("durable_hit")
            return _stored_result(
                request,
                key,
                stored,
                now=now,
                mode=self.mode,
                coverage=CacheCoverageStatus.COMPLETE,
            )

        fetch_error: HistoricalResult | None = None
        fetched_any = False
        provider_attempts = 0
        for start_date, end_date in gaps:
            gap_request = HistoricalRequest(
                symbol=request.symbol,
                currency=request.currency,
                start_date=start_date,
                end_date=end_date,
            )
            fetched = self._provider_call(
                "history",
                partial(self._delegate.get_history, gap_request),
            )
            provider_attempts += fetched.provenance.attempts
            if fetched.status not in {ProviderStatus.SUCCESS, ProviderStatus.EMPTY}:
                fetch_error = fetched
                break
            if fetched.series is not None:
                if (
                    fetched.series.currency != request.currency
                    or fetched.series.adjustment_basis != key.adjustment_basis
                ):
                    return fetched.model_copy(
                        update={
                            "warnings": (
                                *fetched.warnings,
                                ProviderWarning(
                                    code="CACHE_KEY_MISMATCH",
                                    message="Provider history did not match the durable cache key.",
                                ),
                            )
                        }
                    )
                bars = fetched.series.bars
            else:
                bars = ()
            retrieved_at = fetched.provenance.retrieved_at or now
            self._repository.store(
                key,
                start_date=start_date,
                end_date=end_date,
                bars=bars,
                retrieved_at=retrieved_at,
                entitlement=fetched.provenance.entitlement,
                retention_label=retention_label,
                retention_days=self._policy.retention_days,
            )
            fetched_any = True

        refreshed = self._repository.read(
            key,
            start_date=request.start_date,
            end_date=request.end_date,
            now=now,
        )
        remaining = _coverage_gaps(request.start_date, request.end_date, refreshed.coverage)
        if fetch_error is not None:
            if refreshed.bars:
                self._metric("stale")
                cached = _stored_result(
                    request,
                    key,
                    refreshed,
                    now=now,
                    mode=self.mode,
                    coverage=CacheCoverageStatus.STALE,
                )
                return cached.model_copy(
                    update={
                        "status": fetch_error.status,
                        "error": fetch_error.error,
                        "provenance": cached.provenance.model_copy(
                            update={
                                "cache_status": CacheStatus.STALE,
                                "cache_coverage": CacheCoverageStatus.STALE,
                                "is_stale": True,
                            }
                        ),
                        "warnings": (
                            *cached.warnings,
                            ProviderWarning(
                                code="STALE_DURABLE_CACHE_FALLBACK",
                                message="Serving stored historical bars after a provider failure.",
                            ),
                        ),
                    }
                )
            self._metric("unavailable")
            return fetch_error.model_copy(
                update={
                    "provenance": fetch_error.provenance.model_copy(
                        update={
                            "cache_layer": CacheLayer.PROVIDER,
                            "cache_coverage": CacheCoverageStatus.UNAVAILABLE,
                        }
                    )
                }
            )

        coverage = CacheCoverageStatus.COMPLETE if not remaining else CacheCoverageStatus.PARTIAL
        self._metric("partial_hit" if stored.coverage else "miss")
        result = _stored_result(
            request,
            key,
            refreshed,
            now=now,
            mode=self.mode,
            coverage=coverage,
        )
        if fetched_any:
            result = result.model_copy(
                update={
                    "provenance": result.provenance.model_copy(
                        update={
                            "cache_status": CacheStatus.MISS,
                            "cache_layer": CacheLayer.PROVIDER,
                            "attempts": provider_attempts,
                        }
                    )
                }
            )
        return result

    def _exact_key(self, request: HistoricalRequest) -> str:
        return (
            f"{self.provider_name}:{request.symbol.upper()}:{request.currency}:raw:"
            f"{self._policy.schema_version}:{self._policy.policy_version}:"
            f"{request.start_date.isoformat()}:{request.end_date.isoformat()}"
        )

    def _memory_get(self, key: str) -> HistoricalResult | None:
        return self._memory_cache.get(key)

    def _memory_put(self, key: str, result: HistoricalResult) -> None:
        self._memory_cache.put(key, result)

    def _lock_for(self, key: HistoricalCacheKey) -> Lock:
        lock_key = ":".join(_key_params(key))
        with self._key_locks_guard:
            return self._key_locks.setdefault(lock_key, Lock())

    def _metric(self, status: str) -> None:
        self._observability.count(
            "provider.cache.requests",
            1,
            {"provider": self.provider_name, "cache_status": status},
        )

    def _provider_call(
        self,
        operation: str,
        call: Callable[[], _MarketResultT],
    ) -> _MarketResultT:
        started = self._monotonic()
        try:
            result = call()
        except Exception:
            attributes = {
                "provider": self.provider_name,
                "operation": operation,
                "result_status": "failed",
            }
            self._observability.count("provider.requests", 1, attributes)
            self._observability.observe(
                "provider.duration_ms",
                (self._monotonic() - started) * 1_000,
                attributes,
            )
            raise
        attributes = {
            "provider": result.provenance.provider,
            "operation": operation,
            "result_status": result.status.value,
        }
        self._observability.count("provider.requests", 1, attributes)
        self._observability.observe(
            "provider.duration_ms",
            (self._monotonic() - started) * 1_000,
            attributes,
        )
        if result.provenance.attempts > 1:
            self._observability.count(
                "provider.retries",
                result.provenance.attempts - 1,
                {"provider": result.provenance.provider, "operation": operation},
            )
        if result.status in {ProviderStatus.RATE_LIMITED, ProviderStatus.BUDGET_EXHAUSTED}:
            self._observability.count(
                "provider.rate_limited",
                1,
                {"provider": result.provenance.provider, "operation": operation},
            )
        return result


def _key_params(key: HistoricalCacheKey) -> tuple[str, ...]:
    return (
        key.provider,
        key.instrument,
        key.interval,
        key.currency,
        key.adjustment_basis.value,
        key.schema_version,
        key.policy_version,
    )


def _coverage_gaps(
    start_date: date,
    end_date: date,
    coverage: tuple[tuple[date, date, datetime], ...],
) -> tuple[tuple[date, date], ...]:
    covered = _merge_ranges(tuple((item[0], item[1]) for item in coverage))
    cursor = start_date
    gaps: list[tuple[date, date]] = []
    one_day = timedelta(days=1)
    for covered_start, covered_end in covered:
        if covered_end < cursor:
            continue
        if covered_start > end_date:
            break
        if covered_start > cursor:
            gaps.append((cursor, min(end_date, covered_start - one_day)))
        cursor = max(cursor, covered_end + one_day)
        if cursor > end_date:
            break
    if cursor <= end_date:
        gaps.append((cursor, end_date))
    return tuple(gaps)


def _merge_ranges(ranges: tuple[tuple[date, date], ...]) -> tuple[tuple[date, date], ...]:
    if not ranges:
        return ()
    one_day = timedelta(days=1)
    merged: list[tuple[date, date]] = []
    for start_date, end_date in sorted(ranges):
        if not merged or start_date > merged[-1][1] + one_day:
            merged.append((start_date, end_date))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end_date))
    return tuple(merged)


def _stale_tail(
    request: HistoricalRequest,
    coverage: tuple[tuple[date, date, datetime], ...],
    *,
    now: datetime,
    tail_days: int,
    refresh_seconds: int,
) -> tuple[date, date] | None:
    if tail_days <= 0:
        return None
    tail_start = max(request.start_date, now.date() - timedelta(days=tail_days - 1))
    if request.end_date < tail_start:
        return None
    intersecting = (
        retrieved_at
        for start_date, end_date, retrieved_at in coverage
        if end_date >= tail_start and start_date <= request.end_date
    )
    retrievals = tuple(intersecting)
    if retrievals and min(retrievals) > now - timedelta(seconds=refresh_seconds):
        return None
    return tail_start, request.end_date


def _stored_result(
    request: HistoricalRequest,
    key: HistoricalCacheKey,
    stored: StoredHistory,
    *,
    now: datetime,
    mode: ProviderMode,
    coverage: CacheCoverageStatus,
) -> HistoricalResult:
    retrieved_at = stored.latest_retrieved_at
    age = None if retrieved_at is None else max(0.0, (now - retrieved_at).total_seconds())
    series = (
        HistoricalSeries(
            requested_symbol=request.symbol,
            resolved_symbol=key.instrument,
            currency=key.currency,
            currency_source="request",
            adjustment_basis=key.adjustment_basis,
            bars=stored.bars,
        )
        if stored.bars
        else None
    )
    return HistoricalResult(
        status=ProviderStatus.SUCCESS if series is not None else ProviderStatus.EMPTY,
        series=series,
        provenance=ProviderEnvelope(
            provider=key.provider,
            mode=mode,
            entitlement=stored.entitlement or "stored historical cache",
            served_at=now,
            retrieved_at=retrieved_at,
            data_as_of=(
                datetime.combine(stored.bars[-1].trading_date, time.min, tzinfo=UTC)
                if stored.bars
                else None
            ),
            delay_status=DelayStatus.HISTORICAL,
            timestamp_quality=(
                TimestampQuality.DATE_ONLY if stored.bars else TimestampQuality.UNAVAILABLE
            ),
            cache_status=CacheStatus.HIT,
            cache_layer=CacheLayer.DURABLE,
            cache_coverage=coverage,
            cache_age_seconds=age,
            is_stale=False,
            is_synthetic=mode == ProviderMode.CREDENTIAL_FREE,
            attempts=0,
        ),
        warnings=(
            ProviderWarning(
                code="UNVERIFIED_RETENTION_RIGHTS",
                message="Stored under the explicit owner-only unverified-rights exception.",
            ),
        )
        if stored.retention_label == "owner_only_unverified_rights_risk_accepted"
        else (),
    )


def _with_cache_provenance(
    result: HistoricalResult,
    *,
    layer: CacheLayer,
    coverage: CacheCoverageStatus,
    stale: bool,
    now: datetime,
) -> HistoricalResult:
    retrieved_at = result.provenance.retrieved_at
    age = None if retrieved_at is None else max(0.0, (now - retrieved_at).total_seconds())
    return result.model_copy(
        update={
            "provenance": result.provenance.model_copy(
                update={
                    "served_at": now,
                    "cache_status": CacheStatus.STALE if stale else CacheStatus.HIT,
                    "cache_layer": layer,
                    "cache_coverage": coverage,
                    "cache_age_seconds": age,
                    "is_stale": stale,
                    "attempts": 0,
                }
            )
        }
    )
