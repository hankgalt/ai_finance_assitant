import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.persistence.database import SQLiteDatabase
from ai_finance_assistant.providers.durable_cache import (
    DurableCachingMarketDataProvider,
    HistoricalCacheKey,
    HistoricalCachePolicy,
    HistoricalMemoryCache,
    SQLiteHistoricalCacheRepository,
)
from ai_finance_assistant.providers.models import (
    AdjustmentBasis,
    CacheCoverageStatus,
    CacheLayer,
    HistoricalRequest,
    HistoricalResult,
    HistoricalSeries,
    PriceBar,
    ProviderEnvelope,
    ProviderError,
    ProviderErrorCode,
    ProviderMode,
    ProviderReadiness,
    ProviderStatus,
    TimestampQuality,
)


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.monotonic = 0.0

    def advance(self, delta: timedelta) -> None:
        self.now += delta
        self.monotonic += delta.total_seconds()


class CountingMarketProvider:
    mode = ProviderMode.CREDENTIAL_FREE

    def __init__(
        self,
        clock: MutableClock,
        *,
        provider_name: str = "counting_fixture",
        delay_seconds: float = 0,
    ) -> None:
        self.provider_name = provider_name
        self.clock = clock
        self.delay_seconds = delay_seconds
        self.requests: list[HistoricalRequest] = []
        self.fail = False
        self._lock = Lock()

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        return ProviderReadiness(
            provider=self.provider_name,
            mode=self.mode,
            ready=True,
            credential_configured=False,
            terms_approved=True,
            remaining_request_budget=100,
            reason=f"Ready for {required_requests} requests.",
        )

    def search_instruments(self, request):  # type: ignore[no-untyped-def]
        raise AssertionError(f"unexpected search: {request}")

    def get_quote(self, request):  # type: ignore[no-untyped-def]
        raise AssertionError(f"unexpected quote: {request}")

    def get_history(self, request: HistoricalRequest) -> HistoricalResult:
        with self._lock:
            self.requests.append(request)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        envelope = ProviderEnvelope(
            provider=self.provider_name,
            mode=self.mode,
            entitlement="synthetic cache fixture",
            served_at=self.clock.now,
            retrieved_at=self.clock.now,
            data_as_of=self.clock.now,
            delay_status=DelayStatus.HISTORICAL,
            timestamp_quality=TimestampQuality.DATE_ONLY,
            cache_status=CacheStatus.MISS,
            cache_layer=CacheLayer.PROVIDER,
            cache_coverage=(
                CacheCoverageStatus.UNAVAILABLE if self.fail else CacheCoverageStatus.COMPLETE
            ),
            is_synthetic=self.mode == ProviderMode.CREDENTIAL_FREE,
            attempts=1,
        )
        if self.fail:
            return HistoricalResult(
                status=ProviderStatus.UNAVAILABLE,
                provenance=envelope,
                error=ProviderError(
                    code=ProviderErrorCode.UNAVAILABLE,
                    message="Synthetic provider failure.",
                    retryable=True,
                ),
            )
        bars = tuple(
            PriceBar(
                trading_date=request.start_date + timedelta(days=index),
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal("10.5"),
                volume=Decimal("100"),
            )
            for index in range((request.end_date - request.start_date).days + 1)
        )
        return HistoricalResult(
            status=ProviderStatus.SUCCESS,
            series=HistoricalSeries(
                requested_symbol=request.symbol,
                resolved_symbol=request.symbol.upper(),
                currency=request.currency,
                currency_source="request",
                adjustment_basis=AdjustmentBasis.RAW,
                bars=bars,
            ),
            provenance=envelope,
        )


def _policy(**overrides: object) -> HistoricalCachePolicy:
    values: dict[str, object] = {
        "enabled": True,
        "deployment_audience": "owner_only",
        "retention_permission": "unverified",
        "owner_risk_accepted": True,
        "retention_days": 3650,
        "recent_tail_days": 0,
        "tail_refresh_seconds": 21_600,
        "memory_ttl_seconds": 300,
        "memory_max_entries": 128,
        "schema_version": "1",
        "policy_version": "test-policy-v1",
    }
    values.update(overrides)
    return HistoricalCachePolicy(**values)  # type: ignore[arg-type]


def _database(path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(path)
    database.migrate()
    return database


def _wrapper(
    provider: CountingMarketProvider,
    database: SQLiteDatabase,
    clock: MutableClock,
    *,
    policy: HistoricalCachePolicy | None = None,
    memory: HistoricalMemoryCache | None = None,
) -> DurableCachingMarketDataProvider:
    selected_policy = policy or _policy()
    return DurableCachingMarketDataProvider(
        provider,
        repository=SQLiteHistoricalCacheRepository(database),
        policy=selected_policy,
        observability=InMemoryObservability(),
        memory_cache=memory,
        clock=lambda: clock.now,
        monotonic_clock=lambda: clock.monotonic,
    )


def _request(start: date, end: date, *, currency: str = "USD") -> HistoricalRequest:
    return HistoricalRequest(
        symbol="DEMO",
        currency=currency,
        start_date=start,
        end_date=end,
    )


def test_restart_reuses_complete_range_and_overlap_fetches_only_gap(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    first = _wrapper(provider, database, clock)

    first.get_history(_request(date(2026, 1, 1), date(2026, 1, 5)))
    restarted = _wrapper(provider, database, clock)
    durable = restarted.get_history(_request(date(2026, 1, 1), date(2026, 1, 5)))
    overlap = restarted.get_history(_request(date(2026, 1, 3), date(2026, 1, 8)))

    assert len(provider.requests) == 2
    assert provider.requests[1].start_date == date(2026, 1, 6)
    assert provider.requests[1].end_date == date(2026, 1, 8)
    assert durable.provenance.cache_layer == CacheLayer.DURABLE
    assert overlap.provenance.cache_coverage == CacheCoverageStatus.COMPLETE
    database.close()


def test_concurrent_exact_requests_are_coalesced(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock, delay_seconds=0.05)
    memory = HistoricalMemoryCache(ttl_seconds=300, max_entries=128)
    cached = _wrapper(provider, database, clock, memory=memory)
    request = _request(date(2026, 1, 1), date(2026, 1, 5))

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = tuple(pool.map(lambda _: cached.get_history(request), range(5)))

    assert len(provider.requests) == 1
    assert all(result.series is not None for result in results)
    assert sum(result.provenance.cache_layer == CacheLayer.MEMORY for result in results) == 4
    database.close()


def test_recent_tail_refresh_and_stale_fallback_preserve_stored_bars(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, 12, 0, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    policy = _policy(recent_tail_days=7, tail_refresh_seconds=21_600, memory_ttl_seconds=1)
    memory = HistoricalMemoryCache(
        ttl_seconds=1,
        max_entries=128,
        monotonic_clock=lambda: clock.monotonic,
    )
    cached = _wrapper(provider, database, clock, policy=policy, memory=memory)
    request = _request(date(2026, 1, 18), date(2026, 1, 20))

    cached.get_history(request)
    clock.advance(timedelta(hours=7))
    provider.fail = True
    stale = cached.get_history(request)

    assert len(provider.requests) == 2
    assert stale.series is not None
    assert stale.error is not None
    assert stale.provenance.is_stale is True
    assert stale.provenance.cache_coverage == CacheCoverageStatus.STALE
    database.close()


def test_cache_keys_isolate_provider_currency_and_policy_and_purge(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    first_provider = CountingMarketProvider(clock, provider_name="provider-a")
    second_provider = CountingMarketProvider(clock, provider_name="provider-b")
    request = _request(date(2026, 1, 1), date(2026, 1, 2))

    _wrapper(first_provider, database, clock).get_history(request)
    _wrapper(second_provider, database, clock).get_history(request)
    _wrapper(first_provider, database, clock).get_history(
        _request(date(2026, 1, 1), date(2026, 1, 2), currency="CAD")
    )
    _wrapper(first_provider, database, clock, policy=_policy(policy_version="v2")).get_history(
        request
    )
    repository = SQLiteHistoricalCacheRepository(database)
    deleted = repository.purge(provider="provider-a")

    assert len(first_provider.requests) == 3
    assert len(second_provider.requests) == 1
    assert deleted == 6
    database.close()


def test_live_unverified_rights_without_owner_acceptance_bypasses_durable_store(
    tmp_path: Path,
) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    provider.mode = ProviderMode.LIVE
    policy = _policy(owner_risk_accepted=False)
    request = _request(date(2026, 1, 1), date(2026, 1, 2))

    _wrapper(provider, database, clock, policy=policy).get_history(request)
    _wrapper(provider, database, clock, policy=policy).get_history(request)

    assert len(provider.requests) == 2
    assert SQLiteHistoricalCacheRepository(database).purge() == 0
    database.close()


def test_malformed_durable_row_is_purged_and_refetched(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    request = _request(date(2026, 1, 1), date(2026, 1, 2))

    _wrapper(provider, database, clock).get_history(request)
    with database.transaction() as connection:
        connection.execute("UPDATE market_bars SET open_value = 'not-a-decimal'")
    recovered = _wrapper(provider, database, clock).get_history(request)

    assert len(provider.requests) == 2
    assert recovered.series is not None
    assert recovered.provenance.cache_layer == CacheLayer.PROVIDER
    database.close()


def test_expired_rows_are_not_reused(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    policy = _policy(retention_days=1)
    request = _request(date(2026, 1, 1), date(2026, 1, 2))

    _wrapper(provider, database, clock, policy=policy).get_history(request)
    clock.advance(timedelta(days=2))
    refreshed = _wrapper(provider, database, clock, policy=policy).get_history(request)

    assert len(provider.requests) == 2
    assert refreshed.provenance.cache_layer == CacheLayer.PROVIDER
    database.close()


def test_adjustment_basis_is_part_of_durable_key(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 1, 20, tzinfo=UTC))
    database = _database(tmp_path / "cache.sqlite3")
    provider = CountingMarketProvider(clock)
    repository = SQLiteHistoricalCacheRepository(database)
    adjusted_key = HistoricalCacheKey(
        provider=provider.provider_name,
        instrument="DEMO",
        currency="USD",
        adjustment_basis=AdjustmentBasis.ADJUSTED,
        schema_version="1",
        policy_version="test-policy-v1",
    )
    repository.store(
        adjusted_key,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
        bars=(
            PriceBar(
                trading_date=date(2026, 1, 1),
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal("10.5"),
                volume=Decimal("100"),
            ),
        ),
        retrieved_at=clock.now,
        entitlement="synthetic cache fixture",
        retention_label="synthetic_fixture",
        retention_days=30,
    )

    result = _wrapper(provider, database, clock).get_history(
        _request(date(2026, 1, 1), date(2026, 1, 1))
    )

    assert len(provider.requests) == 1
    assert result.series is not None
    assert result.series.adjustment_basis == AdjustmentBasis.RAW
    database.close()
