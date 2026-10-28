"""Stable application ports for external market and news data."""

from dataclasses import dataclass
from typing import Protocol

from ai_finance_assistant.providers.models import (
    HistoricalRequest,
    HistoricalResult,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    NewsSearchRequest,
    NewsSearchResult,
    ProviderMode,
    ProviderReadiness,
    QuoteRequest,
    QuoteResult,
)


class MarketDataProvider(Protocol):
    @property
    def mode(self) -> ProviderMode: ...

    def readiness(self, required_requests: int = 1) -> ProviderReadiness: ...

    def search_instruments(self, request: InstrumentSearchRequest) -> InstrumentSearchResult: ...

    def get_quote(self, request: QuoteRequest) -> QuoteResult: ...

    def get_history(self, request: HistoricalRequest) -> HistoricalResult: ...


class NewsProvider(Protocol):
    @property
    def mode(self) -> ProviderMode: ...

    def readiness(self, required_requests: int = 1) -> ProviderReadiness: ...

    def search(self, request: NewsSearchRequest) -> NewsSearchResult: ...


@dataclass(frozen=True)
class ProviderBundle:
    """One workflow's provider selection; mixed live/synthetic modes are invalid."""

    market: MarketDataProvider
    news: NewsProvider

    def __post_init__(self) -> None:
        if self.market.mode != self.news.mode:
            raise ValueError("a provider bundle cannot mix live and credential-free adapters")

    @property
    def mode(self) -> ProviderMode:
        return self.market.mode
