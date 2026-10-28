"""Deterministic credential-free adapters for CI and private demonstrations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.providers._shared import result_status
from ai_finance_assistant.providers.models import (
    AdjustmentBasis,
    HistoricalRequest,
    HistoricalResult,
    HistoricalSeries,
    InstrumentMatch,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    MarketQuote,
    NewsItem,
    NewsSearchRequest,
    NewsSearchResult,
    PriceBar,
    ProviderEnvelope,
    ProviderError,
    ProviderMode,
    ProviderReadiness,
    QuoteRequest,
    QuoteResult,
    TimestampQuality,
)

DEFAULT_SYNTHETIC_NOW = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)


class FakeMarketDataProvider:
    provider_name = "fake_market_data_v1"
    mode = ProviderMode.CREDENTIAL_FREE

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: DEFAULT_SYNTHETIC_NOW,
        failures: Mapping[str, ProviderError] | None = None,
        cache_status: CacheStatus = CacheStatus.MISS,
        is_stale: bool = False,
    ) -> None:
        self._clock = clock
        self._failures = dict(failures or {})
        self._cache_status = cache_status
        self._is_stale = is_stale
        if is_stale != (cache_status == CacheStatus.STALE):
            raise ValueError("fake stale state and cache status must agree")

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        if required_requests < 0:
            raise ValueError("required_requests cannot be negative")
        return ProviderReadiness(
            provider=self.provider_name,
            mode=self.mode,
            ready=True,
            credential_configured=False,
            terms_approved=True,
            remaining_request_budget=1000,
            reason="Credential-free synthetic provider is ready.",
        )

    def search_instruments(self, request: InstrumentSearchRequest) -> InstrumentSearchResult:
        error = self._failures.get("search")
        matches = (
            InstrumentMatch(
                symbol="DEMO",
                name="Synthetic Demonstration Equity",
                region="United States",
                currency="USD",
                match_score=Decimal("1"),
            ),
        )[: request.limit]
        if error is not None:
            matches = ()
        return InstrumentSearchResult(
            status=result_status(error, has_data=bool(matches)),
            matches=matches,
            provenance=self._envelope(data_as_of=None, delay=DelayStatus.UNKNOWN),
            error=error,
        )

    def get_quote(self, request: QuoteRequest) -> QuoteResult:
        error = self._failures.get("quote")
        quote = None
        if error is None:
            quote = MarketQuote(
                requested_symbol=request.symbol,
                resolved_symbol=request.symbol.upper(),
                price=Decimal("123.45"),
                currency=request.currency,
                currency_source="request",
            )
        return QuoteResult(
            status=result_status(error, has_data=quote is not None),
            quote=quote,
            provenance=self._envelope(
                data_as_of=datetime.combine(date(2026, 10, 26), time.min, tzinfo=UTC),
                delay=DelayStatus.END_OF_DAY,
                timestamp_quality=TimestampQuality.DATE_ONLY,
            ),
            error=error,
        )

    def get_history(self, request: HistoricalRequest) -> HistoricalResult:
        error = self._failures.get("history")
        available_bars = tuple(
            bar
            for bar in (
                PriceBar(
                    trading_date=date(2026, 10, 23),
                    open=Decimal("120"),
                    high=Decimal("124"),
                    low=Decimal("119"),
                    close=Decimal("123"),
                    volume=1000000,
                ),
                PriceBar(
                    trading_date=date(2026, 10, 26),
                    open=Decimal("123"),
                    high=Decimal("125"),
                    low=Decimal("122"),
                    close=Decimal("123.45"),
                    volume=1100000,
                ),
            )
            if request.start_date <= bar.trading_date <= request.end_date
        )
        bars = available_bars if error is None else ()
        series = None
        if error is None and bars:
            series = HistoricalSeries(
                requested_symbol=request.symbol,
                resolved_symbol=request.symbol.upper(),
                currency=request.currency,
                currency_source="request",
                adjustment_basis=AdjustmentBasis.RAW,
                bars=bars,
            )
        status = result_status(error, has_data=series is not None)
        return HistoricalResult(
            status=status,
            series=series,
            provenance=self._envelope(
                data_as_of=(
                    datetime.combine(bars[-1].trading_date, time.min, tzinfo=UTC) if bars else None
                ),
                delay=DelayStatus.HISTORICAL,
                timestamp_quality=(
                    TimestampQuality.DATE_ONLY if bars else TimestampQuality.UNAVAILABLE
                ),
            ),
            error=error,
        )

    def _envelope(
        self,
        *,
        data_as_of: datetime | None,
        delay: DelayStatus,
        timestamp_quality: TimestampQuality = TimestampQuality.UNAVAILABLE,
    ) -> ProviderEnvelope:
        now = self._clock()
        return ProviderEnvelope(
            provider=self.provider_name,
            mode=self.mode,
            entitlement="synthetic fixture v1; not provider data",
            served_at=now,
            retrieved_at=now,
            data_as_of=data_as_of,
            delay_status=delay,
            timestamp_quality=timestamp_quality,
            cache_status=self._cache_status,
            cache_age_seconds=(
                60 if self._cache_status in {CacheStatus.HIT, CacheStatus.STALE} else 0
            ),
            is_stale=self._is_stale,
            is_synthetic=True,
            attempts=0,
        )


class FakeNewsProvider:
    provider_name = "fake_news_v1"
    mode = ProviderMode.CREDENTIAL_FREE

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: DEFAULT_SYNTHETIC_NOW,
        failure: ProviderError | None = None,
    ) -> None:
        self._clock = clock
        self._failure = failure

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        if required_requests < 0:
            raise ValueError("required_requests cannot be negative")
        return ProviderReadiness(
            provider=self.provider_name,
            mode=self.mode,
            ready=True,
            credential_configured=False,
            terms_approved=True,
            remaining_request_budget=1000,
            reason="Credential-free synthetic provider is ready.",
        )

    def search(self, request: NewsSearchRequest) -> NewsSearchResult:
        now = self._clock()
        items: tuple[NewsItem, ...] = ()
        if self._failure is None:
            items = (
                NewsItem(
                    item_id="news-synthetic-demo-v1",
                    publisher="example.invalid",
                    url="https://example.invalid/synthetic-market-update",
                    title="Synthetic company reports a demonstration update",
                    excerpt="Synthetic fixture content for the credential-free demo.",
                    published_at=datetime(2026, 10, 26, 14, 0, tzinfo=UTC),
                    published_at_quality=TimestampQuality.EXACT,
                    matched_symbols=request.symbols,
                ),
            )[: request.max_results]
        return NewsSearchResult(
            status=result_status(self._failure, has_data=bool(items)),
            items=items,
            provenance=ProviderEnvelope(
                provider=self.provider_name,
                mode=self.mode,
                entitlement="synthetic fixture v1; not publisher content",
                served_at=now,
                retrieved_at=now,
                data_as_of=items[0].published_at if items else None,
                timestamp_quality=(
                    TimestampQuality.EXACT if items else TimestampQuality.UNAVAILABLE
                ),
                cache_status=CacheStatus.MISS,
                cache_age_seconds=0,
                is_synthetic=True,
                attempts=0,
            ),
            error=self._failure,
        )
