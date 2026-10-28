"""External-provider ports and adapters for M3."""

from ai_finance_assistant.providers.alpha_vantage import AlphaVantageMarketDataProvider
from ai_finance_assistant.providers.factory import (
    credential_free_bundle,
    live_demo_bundle,
    provider_bundle_from_settings,
)
from ai_finance_assistant.providers.fake import FakeMarketDataProvider, FakeNewsProvider
from ai_finance_assistant.providers.massive import MassiveMarketDataProvider
from ai_finance_assistant.providers.ports import MarketDataProvider, NewsProvider, ProviderBundle
from ai_finance_assistant.providers.tavily import TavilyNewsProvider

__all__ = [
    "AlphaVantageMarketDataProvider",
    "FakeMarketDataProvider",
    "FakeNewsProvider",
    "MarketDataProvider",
    "MassiveMarketDataProvider",
    "NewsProvider",
    "ProviderBundle",
    "TavilyNewsProvider",
    "credential_free_bundle",
    "live_demo_bundle",
    "provider_bundle_from_settings",
]
