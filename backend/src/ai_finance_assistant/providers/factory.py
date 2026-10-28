"""Explicit provider-mode selection for one workflow."""

from typing import Literal

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.providers.alpha_vantage import AlphaVantageMarketDataProvider
from ai_finance_assistant.providers.fake import FakeMarketDataProvider, FakeNewsProvider
from ai_finance_assistant.providers.massive import MassiveMarketDataProvider
from ai_finance_assistant.providers.ports import MarketDataProvider, ProviderBundle
from ai_finance_assistant.providers.tavily import TavilyNewsProvider


def credential_free_bundle() -> ProviderBundle:
    return ProviderBundle(market=FakeMarketDataProvider(), news=FakeNewsProvider())


def live_demo_bundle(
    *,
    market_data_provider: Literal["alpha_vantage", "massive"] = "alpha_vantage",
    alpha_vantage_api_key: str | None,
    massive_api_key: str | None = None,
    tavily_api_key: str | None,
    market_request_budget: int = 5,
    news_request_budget: int = 3,
    alpha_vantage_entitlement: str = (
        "conditional-private-demo; verify account terms before live use"
    ),
    massive_entitlement: str = (
        "conditional-owner-only-demo; verify business/display rights before sharing data"
    ),
    tavily_entitlement: str = (
        "conditional-private-demo; third-party source rights remain separate"
    ),
    alpha_vantage_terms_approved: bool = False,
    massive_terms_approved: bool = False,
    tavily_terms_approved: bool = False,
) -> ProviderBundle:
    """Build live adapters without falling back when a credential or readiness check fails."""

    market: MarketDataProvider
    if market_data_provider == "massive":
        market = MassiveMarketDataProvider(
            api_key=massive_api_key,
            request_budget=market_request_budget,
            entitlement=massive_entitlement,
            terms_approved=massive_terms_approved,
        )
    else:
        market = AlphaVantageMarketDataProvider(
            api_key=alpha_vantage_api_key,
            request_budget=market_request_budget,
            entitlement=alpha_vantage_entitlement,
            terms_approved=alpha_vantage_terms_approved,
        )
    return ProviderBundle(
        market=market,
        news=TavilyNewsProvider(
            api_key=tavily_api_key,
            request_budget=news_request_budget,
            entitlement=tavily_entitlement,
            terms_approved=tavily_terms_approved,
        ),
    )


def provider_bundle_from_settings(settings: Settings) -> ProviderBundle:
    """Select one mode before a workflow; readiness failure never changes the selection."""

    if settings.provider_mode == "credential_free":
        return credential_free_bundle()
    return live_demo_bundle(
        market_data_provider=settings.market_data_provider,
        alpha_vantage_api_key=(
            settings.alpha_vantage_api_key.get_secret_value()
            if settings.alpha_vantage_api_key is not None
            else None
        ),
        massive_api_key=(
            settings.massive_api_key.get_secret_value()
            if settings.massive_api_key is not None
            else None
        ),
        tavily_api_key=(
            settings.tavily_api_key.get_secret_value()
            if settings.tavily_api_key is not None
            else None
        ),
        market_request_budget=settings.market_provider_request_budget,
        news_request_budget=settings.news_provider_request_budget,
        alpha_vantage_entitlement=settings.alpha_vantage_entitlement,
        massive_entitlement=settings.massive_entitlement,
        tavily_entitlement=settings.tavily_entitlement,
        alpha_vantage_terms_approved=settings.alpha_vantage_terms_approved,
        massive_terms_approved=settings.massive_terms_approved,
        tavily_terms_approved=settings.tavily_terms_approved,
    )
