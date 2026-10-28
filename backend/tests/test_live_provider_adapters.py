"""Explicit, quota-bounded smoke tests against approved live provider accounts."""

import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.providers.factory import provider_bundle_from_settings
from ai_finance_assistant.providers.models import (
    HistoricalRequest,
    InstrumentSearchRequest,
    NewsSearchRequest,
    ProviderMode,
    ProviderStatus,
    QuoteRequest,
)
from ai_finance_assistant.providers.ports import ProviderBundle

pytestmark = pytest.mark.live_provider


def _live_tests_enabled() -> bool:
    return os.environ.get("AIFA_RUN_LIVE_PROVIDER_TESTS", "").casefold() in {
        "1",
        "true",
        "yes",
    }


@pytest.fixture(scope="module")
def live_providers() -> ProviderBundle:
    if not _live_tests_enabled():
        pytest.skip("set AIFA_RUN_LIVE_PROVIDER_TESTS=true to permit external provider calls")

    settings = Settings()
    if settings.provider_mode != "live":
        pytest.fail("live-provider tests require AIFA_PROVIDER_MODE=live")

    missing_credentials = []
    if settings.market_data_provider == "alpha_vantage":
        if settings.alpha_vantage_api_key is None:
            missing_credentials.append("AIFA_ALPHA_VANTAGE_API_KEY")
    elif settings.massive_api_key is None:
        missing_credentials.append("AIFA_MASSIVE_API_KEY")
    if settings.tavily_api_key is None:
        missing_credentials.append("AIFA_TAVILY_API_KEY")
    if missing_credentials:
        pytest.fail("missing live-provider credentials: " + ", ".join(missing_credentials))

    unapproved_terms = []
    if settings.market_data_provider == "alpha_vantage":
        if not settings.alpha_vantage_terms_approved:
            unapproved_terms.append("AIFA_ALPHA_VANTAGE_TERMS_APPROVED")
    elif not settings.massive_terms_approved:
        unapproved_terms.append("AIFA_MASSIVE_TERMS_APPROVED")
    if not settings.tavily_terms_approved:
        unapproved_terms.append("AIFA_TAVILY_TERMS_APPROVED")
    if unapproved_terms:
        pytest.fail("provider terms are not approved: " + ", ".join(unapproved_terms))

    providers = provider_bundle_from_settings(settings)
    assert providers.mode == ProviderMode.LIVE

    market_readiness = providers.market.readiness(required_requests=3)
    news_readiness = providers.news.readiness(required_requests=1)
    assert market_readiness.ready, market_readiness.reason
    assert news_readiness.ready, news_readiness.reason
    return providers


def test_selected_live_market_account_supports_market_contract(
    live_providers: ProviderBundle,
) -> None:
    expected_provider = live_providers.market.readiness().provider
    end_date = datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
    search = live_providers.market.search_instruments(InstrumentSearchRequest(query="IBM", limit=3))
    assert search.status == ProviderStatus.SUCCESS, search.error
    assert search.matches
    assert search.provenance.mode == ProviderMode.LIVE
    assert search.provenance.provider == expected_provider
    assert not search.provenance.is_synthetic

    quote = live_providers.market.get_quote(QuoteRequest(symbol="IBM", currency="USD"))
    assert quote.status == ProviderStatus.SUCCESS, quote.error
    assert quote.quote is not None
    assert quote.quote.price > 0
    assert quote.provenance.mode == ProviderMode.LIVE
    assert quote.provenance.provider == expected_provider
    assert not quote.provenance.is_synthetic

    history = live_providers.market.get_history(
        HistoricalRequest(
            symbol="IBM",
            currency="USD",
            start_date=end_date - timedelta(days=30),
            end_date=end_date,
        )
    )
    assert history.status == ProviderStatus.SUCCESS, history.error
    assert history.series is not None
    assert history.series.bars
    assert history.provenance.mode == ProviderMode.LIVE
    assert history.provenance.provider == expected_provider
    assert not history.provenance.is_synthetic


def test_tavily_live_account_supports_selected_news_contract(
    live_providers: ProviderBundle,
) -> None:
    today = datetime.now(UTC).date()
    result = live_providers.news.search(
        NewsSearchRequest(
            query="IBM company financial news",
            symbols=("IBM",),
            start_date=today - timedelta(days=7),
            end_date=today,
            max_results=3,
        )
    )

    assert result.status in {ProviderStatus.SUCCESS, ProviderStatus.EMPTY}, result.error
    assert result.error is None
    assert result.provenance.mode == ProviderMode.LIVE
    assert result.provenance.provider == "tavily"
    assert not result.provenance.is_synthetic
    assert len(result.items) <= 3
    assert all(item.publisher and item.url for item in result.items)
