import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event

import httpx
import pytest
from pydantic import ValidationError

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.providers.alpha_vantage import AlphaVantageMarketDataProvider
from ai_finance_assistant.providers.factory import provider_bundle_from_settings
from ai_finance_assistant.providers.fake import FakeMarketDataProvider, FakeNewsProvider
from ai_finance_assistant.providers.massive import MassiveMarketDataProvider
from ai_finance_assistant.providers.models import (
    HistoricalRequest,
    InstrumentSearchRequest,
    NewsSearchRequest,
    ProviderErrorCode,
    ProviderMode,
    ProviderStatus,
    QuoteRequest,
    TimestampQuality,
)
from ai_finance_assistant.providers.ports import ProviderBundle
from ai_finance_assistant.providers.runtime import ProviderRuntime
from ai_finance_assistant.providers.tavily import TavilyNewsProvider

DATA_DIR = Path(__file__).parents[1] / "data" / "providers"
NOW = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)


@dataclass
class MutableClock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def fixture(name: str) -> object:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def test_provider_fixture_manifest_hashes_match() -> None:
    manifest = fixture("fixture_manifest.v1.json")
    assert isinstance(manifest, dict)
    files = manifest["files"]
    assert isinstance(files, list)
    for item in files:
        assert isinstance(item, dict)
        actual = hashlib.sha256((DATA_DIR / item["path"]).read_bytes()).hexdigest()
        assert actual == item["sha256"]


def runtime(
    clock: MutableClock,
    *,
    budget: int = 20,
    requests_per_window: int = 20,
    circuit_threshold: int = 10,
    max_concurrency: int = 2,
) -> ProviderRuntime:
    return ProviderRuntime(
        provider_name="test-provider",
        mode=ProviderMode.LIVE,
        request_budget=budget,
        requests_per_window=requests_per_window,
        max_concurrency=max_concurrency,
        circuit_failure_threshold=circuit_threshold,
        clock=clock,
        sleeper=lambda _: None,
        jitter=lambda cap: cap,
    )


def quote_request(symbol: str = "DEMO") -> QuoteRequest:
    return QuoteRequest(symbol=symbol, currency="USD")


def news_request(query: str = "synthetic company earnings") -> NewsSearchRequest:
    return NewsSearchRequest(
        query=query,
        symbols=("DEMO",),
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 27),
        max_results=5,
    )


def test_credential_free_bundle_uses_exact_ports_and_truthful_labels() -> None:
    bundle = ProviderBundle(market=FakeMarketDataProvider(), news=FakeNewsProvider())

    quote = bundle.market.get_quote(quote_request())
    news = bundle.news.search(news_request())

    assert bundle.mode == ProviderMode.CREDENTIAL_FREE
    assert quote.status == ProviderStatus.SUCCESS
    assert news.status == ProviderStatus.SUCCESS
    assert quote.provenance.is_synthetic is True
    assert news.provenance.is_synthetic is True
    assert quote.provenance.mode == ProviderMode.CREDENTIAL_FREE
    assert bundle.market.readiness(100).ready is True


def test_provider_bundle_rejects_mixed_live_and_synthetic_modes() -> None:
    with pytest.raises(ValueError, match="cannot mix"):
        ProviderBundle(
            market=FakeMarketDataProvider(),
            news=TavilyNewsProvider(api_key=None),
        )


def test_settings_select_one_mode_without_silent_fallback() -> None:
    credential_free = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="credential_free",
            market_data_provider="alpha_vantage",
            alpha_vantage_api_key=None,
            massive_api_key=None,
            tavily_api_key=None,
            alpha_vantage_terms_approved=False,
            massive_terms_approved=False,
            tavily_terms_approved=False,
        )
    )
    live_without_credentials = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="live",
            market_data_provider="alpha_vantage",
            alpha_vantage_api_key=None,
            massive_api_key=None,
            tavily_api_key=None,
            alpha_vantage_terms_approved=False,
            massive_terms_approved=False,
            tavily_terms_approved=False,
        )
    )

    assert credential_free.mode == ProviderMode.CREDENTIAL_FREE
    assert credential_free.market.readiness().ready is True
    assert live_without_credentials.mode == ProviderMode.LIVE
    assert live_without_credentials.market.readiness().ready is False
    assert live_without_credentials.news.readiness().ready is False

    configured_but_unapproved = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="live",
            market_data_provider="alpha_vantage",
            alpha_vantage_api_key="configured",
            massive_api_key=None,
            tavily_api_key="configured",
            alpha_vantage_terms_approved=False,
            massive_terms_approved=False,
            tavily_terms_approved=False,
        )
    )
    assert configured_but_unapproved.market.readiness().credential_configured is True
    assert configured_but_unapproved.market.readiness().terms_approved is False
    assert configured_but_unapproved.market.readiness().ready is False
    assert (
        configured_but_unapproved.market.get_quote(quote_request()).status
        == ProviderStatus.ENTITLEMENT_REQUIRED
    )
    assert (
        configured_but_unapproved.news.search(news_request()).status
        == ProviderStatus.ENTITLEMENT_REQUIRED
    )

    approved = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="live",
            market_data_provider="alpha_vantage",
            alpha_vantage_api_key="configured",
            massive_api_key=None,
            tavily_api_key="configured",
            alpha_vantage_terms_approved=True,
            massive_terms_approved=False,
            tavily_terms_approved=True,
        )
    )
    assert approved.market.readiness(5).ready is True
    assert approved.news.readiness(3).ready is True


def test_settings_explicitly_select_massive_without_falling_back_to_alpha() -> None:
    selected = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="live",
            market_data_provider="massive",
            alpha_vantage_api_key="configured-alpha",
            alpha_vantage_terms_approved=True,
            massive_api_key="configured-massive",
            massive_terms_approved=True,
            tavily_api_key="configured-tavily",
            tavily_terms_approved=True,
        )
    )

    assert selected.market.readiness(3).provider == "massive"
    assert selected.market.readiness(3).ready is True
    assert selected.news.readiness(1).provider == "tavily"

    unavailable_selected = provider_bundle_from_settings(
        Settings(
            mode="test",
            provider_mode="live",
            market_data_provider="massive",
            alpha_vantage_api_key="configured-alpha",
            alpha_vantage_terms_approved=True,
            massive_api_key=None,
            massive_terms_approved=False,
            tavily_api_key="configured-tavily",
            tavily_terms_approved=True,
        )
    )

    assert unavailable_selected.market.readiness().provider == "massive"
    assert unavailable_selected.market.readiness().ready is False


def test_fake_history_empty_window_is_observable() -> None:
    result = FakeMarketDataProvider().get_history(
        HistoricalRequest(
            symbol="DEMO",
            currency="USD",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
    )

    assert result.status == ProviderStatus.EMPTY
    assert result.series is None
    assert result.provenance.timestamp_quality == TimestampQuality.UNAVAILABLE


def test_missing_live_credentials_fail_readiness_without_http_calls() -> None:
    market_calls = 0
    news_calls = 0

    def market_handler(request: httpx.Request) -> httpx.Response:
        nonlocal market_calls
        market_calls += 1
        return httpx.Response(500)

    def news_handler(request: httpx.Request) -> httpx.Response:
        nonlocal news_calls
        news_calls += 1
        return httpx.Response(500)

    market = AlphaVantageMarketDataProvider(
        api_key=None,
        client=httpx.Client(transport=httpx.MockTransport(market_handler)),
    )
    news = TavilyNewsProvider(
        api_key=None,
        client=httpx.Client(transport=httpx.MockTransport(news_handler)),
    )

    assert market.readiness().ready is False
    assert news.readiness().ready is False
    assert market.get_quote(quote_request()).status == ProviderStatus.UNAUTHORIZED
    assert news.search(news_request()).status == ProviderStatus.UNAUTHORIZED
    assert market_calls == news_calls == 0


def test_alpha_quote_is_normalized_and_repeated_view_reuses_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["function"] == "GLOBAL_QUOTE"
        assert request.url.params["apikey"] == "secret-test-key"
        return httpx.Response(
            200,
            json=fixture("alpha_vantage.quote.synthetic.v1.json"),
        )

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="secret-test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, budget=1),
    )

    first = provider.get_quote(quote_request())
    clock.advance(60)
    second = provider.get_quote(quote_request())

    assert calls == 1
    assert first.quote is not None
    assert first.quote.price.as_tuple().exponent == -4
    assert first.provenance.delay_status == DelayStatus.END_OF_DAY
    assert first.provenance.timestamp_quality == TimestampQuality.DATE_ONLY
    assert first.provenance.cache_status == CacheStatus.MISS
    assert second.provenance.cache_status == CacheStatus.HIT
    assert second.provenance.cache_age_seconds == 60
    assert provider.readiness().remaining_request_budget == 0


def test_massive_previous_close_is_normalized_and_repeated_view_reuses_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/v2/aggs/ticker/DEMO/prev"
        assert request.url.params["adjusted"] == "false"
        assert request.headers["Authorization"] == "Bearer secret-test-key"
        assert "secret-test-key" not in str(request.url)
        return httpx.Response(
            200,
            json=fixture("massive.previous_close.synthetic.v1.json"),
        )

    clock = MutableClock()
    provider = MassiveMarketDataProvider(
        api_key="secret-test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, budget=1),
    )

    first = provider.get_quote(quote_request())
    clock.advance(60)
    second = provider.get_quote(quote_request())

    assert calls == 1
    assert first.status == ProviderStatus.SUCCESS
    assert first.quote is not None
    assert first.quote.resolved_symbol == "DEMO"
    assert first.quote.price == Decimal("123.45")
    assert first.provenance.provider == "massive"
    assert first.provenance.delay_status == DelayStatus.END_OF_DAY
    assert first.provenance.timestamp_quality == TimestampQuality.DATE_ONLY
    assert first.provenance.request_id == "massive-synthetic-request-v1"
    assert first.provenance.cache_status == CacheStatus.MISS
    assert second.provenance.cache_status == CacheStatus.HIT
    assert second.provenance.cache_age_seconds == 60


def test_alpha_search_and_history_are_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        function = request.url.params["function"]
        payload = {
            "SYMBOL_SEARCH": "alpha_vantage.search.synthetic.v1.json",
            "TIME_SERIES_DAILY": "alpha_vantage.history.synthetic.v1.json",
        }[function]
        return httpx.Response(200, json=fixture(payload))

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )

    search = provider.search_instruments(InstrumentSearchRequest(query="demo"))
    history = provider.get_history(
        HistoricalRequest(
            symbol="DEMO",
            currency="USD",
            start_date=date(2026, 10, 24),
            end_date=date(2026, 10, 27),
        )
    )

    assert search.matches[0].currency == "USD"
    assert history.series is not None
    assert [bar.trading_date for bar in history.series.bars] == [date(2026, 10, 26)]
    assert history.series.adjustment_basis == "raw"
    assert history.provenance.delay_status == DelayStatus.HISTORICAL


def test_massive_search_and_history_are_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.url.path == "/v3/reference/tickers":
            assert request.url.params["market"] == "stocks"
            assert request.url.params["active"] == "true"
            assert request.url.params["search"] == "demo"
            assert request.url.params["limit"] == "2"
            return httpx.Response(200, json=fixture("massive.search.synthetic.v1.json"))
        assert request.url.path == ("/v2/aggs/ticker/DEMO/range/1/day/2026-10-24/2026-10-27")
        assert request.url.params["adjusted"] == "false"
        assert request.url.params["sort"] == "asc"
        assert request.url.params["limit"] == "5000"
        return httpx.Response(200, json=fixture("massive.history.synthetic.v1.json"))

    clock = MutableClock()
    provider = MassiveMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )

    search = provider.search_instruments(InstrumentSearchRequest(query="demo", limit=2))
    history = provider.get_history(
        HistoricalRequest(
            symbol="DEMO",
            currency="USD",
            start_date=date(2026, 10, 24),
            end_date=date(2026, 10, 27),
        )
    )

    assert search.status == ProviderStatus.SUCCESS
    assert search.matches[0].symbol == "DEMO"
    assert search.matches[0].region == "US"
    assert search.matches[0].currency == "USD"
    assert search.matches[0].match_score is None
    assert search.provenance.request_id == "massive-synthetic-search-v1"
    assert history.status == ProviderStatus.SUCCESS
    assert history.series is not None
    assert history.series.adjustment_basis == "raw"
    assert [bar.trading_date for bar in history.series.bars] == [date(2026, 10, 26)]
    assert history.provenance.delay_status == DelayStatus.HISTORICAL
    assert history.provenance.request_id == "massive-synthetic-history-v1"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ProviderStatus.UNAUTHORIZED),
        (403, ProviderStatus.UNAUTHORIZED),
        (429, ProviderStatus.RATE_LIMITED),
        (503, ProviderStatus.UNAVAILABLE),
        (400, ProviderStatus.INVALID_REQUEST),
    ],
)
def test_alpha_http_failure_matrix(status_code: int, expected: ProviderStatus) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"Retry-After": "0"})

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )

    result = provider.get_quote(quote_request())

    assert result.status == expected
    assert result.quote is None
    assert result.error is not None
    assert result.provenance.is_synthetic is False


@pytest.mark.parametrize(
    ("status_code", "expected", "expected_calls"),
    [
        (401, ProviderStatus.UNAUTHORIZED, 1),
        (403, ProviderStatus.ENTITLEMENT_REQUIRED, 1),
        (429, ProviderStatus.RATE_LIMITED, 1),
        (503, ProviderStatus.UNAVAILABLE, 2),
        (400, ProviderStatus.INVALID_REQUEST, 1),
    ],
)
def test_massive_http_failure_matrix(
    status_code: int,
    expected: ProviderStatus,
    expected_calls: int,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status_code,
            json={"status": "ERROR", "error": "SECRET provider detail"},
        )

    clock = MutableClock()
    result = MassiveMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    assert calls == expected_calls
    assert result.status == expected
    assert result.quote is None
    assert result.error is not None
    assert "SECRET" not in result.error.message
    assert result.provenance.is_synthetic is False


def test_massive_non_ok_payload_is_rejected_without_leaking_provider_detail() -> None:
    payload = fixture("massive.previous_close.synthetic.v1.json")
    assert isinstance(payload, dict)
    payload["status"] = "ERROR"
    payload["error"] = "SECRET provider detail"

    clock = MutableClock()
    result = MassiveMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    assert result.status == ProviderStatus.INVALID_REQUEST
    assert result.quote is None
    assert result.error is not None
    assert "SECRET" not in result.error.message


def test_massive_timeout_is_typed_and_fractional_volume_is_preserved() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    clock = MutableClock()
    timed_out = MassiveMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(timeout_handler)),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    fractional_volume_payload = fixture("massive.history.synthetic.v1.json")
    assert isinstance(fractional_volume_payload, dict)
    raw_results = fractional_volume_payload["results"]
    assert isinstance(raw_results, list)
    assert isinstance(raw_results[0], dict)
    raw_results[0]["v"] = 1.5
    history = MassiveMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=fractional_volume_payload)
            )
        ),
        runtime=runtime(clock),
    ).get_history(
        HistoricalRequest(
            symbol="DEMO",
            currency="USD",
            start_date=date(2026, 10, 20),
            end_date=date(2026, 10, 27),
        )
    )

    assert timed_out.status == ProviderStatus.TIMEOUT
    assert history.status == ProviderStatus.SUCCESS
    assert history.series is not None
    assert history.series.bars[0].volume == Decimal("1.5")


def test_alpha_timeout_and_malformed_payload_are_typed() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    clock = MutableClock()
    timed_out = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(timeout_handler)),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    malformed = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"Global Quote": {"05. price": "NaN"}})
            )
        ),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    assert timed_out.status == ProviderStatus.TIMEOUT
    assert malformed.status == ProviderStatus.MALFORMED_RESPONSE


def test_alpha_provider_payload_errors_are_typed_without_leaking_payload() -> None:
    payloads = (
        ({"Error Message": "bad symbol SECRET"}, ProviderErrorCode.INVALID_REQUEST),
        ({"Note": "API rate limit SECRET"}, ProviderErrorCode.RATE_LIMITED),
        ({"Information": "premium endpoint SECRET"}, ProviderErrorCode.UNAVAILABLE),
    )
    for payload, expected in payloads:
        clock = MutableClock()
        provider = AlphaVantageMarketDataProvider(
            api_key="test-key",
            terms_approved=True,
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _, data=payload: httpx.Response(200, json=data)
                )
            ),
            runtime=runtime(clock),
        )
        result = provider.get_quote(quote_request())
        assert result.error is not None
        assert result.error.code == expected
        assert "SECRET" not in result.error.message


def test_alpha_body_level_plan_limit_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"Note": "The standard API request limit has been reached."},
        )

    clock = MutableClock()
    result = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    ).get_quote(quote_request())

    assert calls == 1
    assert result.status == ProviderStatus.RATE_LIMITED
    assert result.error is not None
    assert result.error.retryable is False
    assert result.provenance.attempts == 1


def test_stale_cache_fallback_preserves_original_retrieval_time() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=fixture("alpha_vantage.quote.synthetic.v1.json"))
        raise httpx.ReadTimeout("fixture timeout", request=request)

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )
    first = provider.get_quote(quote_request())
    clock.advance(301)
    stale = provider.get_quote(quote_request())

    assert stale.status == ProviderStatus.SUCCESS
    assert stale.quote == first.quote
    assert stale.error is not None and stale.error.code == ProviderErrorCode.TIMEOUT
    assert stale.provenance.cache_status == CacheStatus.STALE
    assert stale.provenance.retrieved_at == first.provenance.retrieved_at
    assert stale.provenance.retrieved_at is not None
    assert stale.provenance.served_at > stale.provenance.retrieved_at
    assert stale.warnings[0].code == "STALE_CACHE_FALLBACK"


def test_invalid_or_authorization_failures_do_not_serve_stale_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=fixture("alpha_vantage.quote.synthetic.v1.json"))
        return httpx.Response(403)

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )
    assert provider.get_quote(quote_request()).status == ProviderStatus.SUCCESS
    clock.advance(301)

    result = provider.get_quote(quote_request())

    assert result.status == ProviderStatus.UNAUTHORIZED
    assert result.quote is None
    assert result.provenance.cache_status == CacheStatus.NOT_APPLICABLE


def test_budget_exhaustion_happens_before_an_additional_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=fixture("alpha_vantage.quote.synthetic.v1.json"))

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, budget=1),
    )

    assert provider.get_quote(quote_request()).status == ProviderStatus.SUCCESS
    exhausted = provider.get_quote(quote_request("OTHER"))

    assert calls == 1
    assert exhausted.status == ProviderStatus.BUDGET_EXHAUSTED
    assert exhausted.provenance.attempts == 0


def test_local_rate_limit_prevents_an_additional_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=fixture("alpha_vantage.quote.synthetic.v1.json"))

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, requests_per_window=1),
    )

    provider.get_quote(quote_request())
    limited = provider.get_quote(quote_request("OTHER"))

    assert calls == 1
    assert limited.status == ProviderStatus.RATE_LIMITED


def test_open_circuit_prevents_a_follow_up_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("fixture timeout", request=request)

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, circuit_threshold=2),
    )

    first = provider.get_quote(quote_request("FIRST"))
    second = provider.get_quote(quote_request("SECOND"))

    assert first.status == ProviderStatus.TIMEOUT
    assert second.status == ProviderStatus.CIRCUIT_OPEN
    assert calls == 2


def test_concurrency_limit_is_observable_without_a_second_call() -> None:
    entered = Event()
    release = Event()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=2)
        return httpx.Response(200, json=fixture("alpha_vantage.quote.synthetic.v1.json"))

    clock = MutableClock()
    provider = AlphaVantageMarketDataProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock, max_concurrency=1),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(provider.get_quote, quote_request("FIRST"))
        assert entered.wait(timeout=2)
        second = provider.get_quote(quote_request("SECOND"))
        release.set()
        first = first_future.result(timeout=2)

    assert first.status == ProviderStatus.SUCCESS
    assert second.status == ProviderStatus.CONCURRENCY_LIMITED
    assert calls == 1


def test_tavily_news_is_attributed_and_request_minimizes_content() -> None:
    observed_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed_body.update(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json=fixture("tavily.news.synthetic.v1.json"))

    clock = MutableClock()
    provider = TavilyNewsProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        runtime=runtime(clock),
    )

    result = provider.search(news_request())

    assert result.status == ProviderStatus.SUCCESS
    assert [item.publisher for item in result.items] == [
        "news.example.invalid",
        "briefing.example.invalid",
    ]
    assert result.items[0].published_at_quality == TimestampQuality.PROVIDER_ESTIMATED
    assert result.items[1].published_at_quality == TimestampQuality.UNAVAILABLE
    assert result.provenance.request_id == "synthetic-request-v1"
    assert observed_body["topic"] == "finance"
    assert observed_body["include_answer"] is False
    assert observed_body["include_raw_content"] is False
    assert "symbols" not in observed_body


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ProviderStatus.UNAUTHORIZED),
        (403, ProviderStatus.UNAUTHORIZED),
        (429, ProviderStatus.RATE_LIMITED),
        (432, ProviderStatus.RATE_LIMITED),
        (433, ProviderStatus.RATE_LIMITED),
        (500, ProviderStatus.UNAVAILABLE),
        (422, ProviderStatus.INVALID_REQUEST),
    ],
)
def test_tavily_failure_matrix(status_code: int, expected: ProviderStatus) -> None:
    clock = MutableClock()
    provider = TavilyNewsProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status_code))),
        runtime=runtime(clock),
    )

    result = provider.search(news_request())

    assert result.status == expected
    assert result.items == ()


def test_tavily_empty_and_malformed_results_are_distinct() -> None:
    clock = MutableClock()
    empty = TavilyNewsProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": []}))
        ),
        runtime=runtime(clock),
    ).search(news_request())
    malformed = TavilyNewsProvider(
        api_key="test-key",
        terms_approved=True,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"wrong": []}))
        ),
        runtime=runtime(clock),
    ).search(news_request("another public query"))

    assert empty.status == ProviderStatus.EMPTY
    assert malformed.status == ProviderStatus.MALFORMED_RESPONSE


def test_news_query_rejects_excessive_windows_and_sensitive_flag() -> None:
    with pytest.raises(ValidationError):
        NewsSearchRequest(
            query="public company news",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
        )
    with pytest.raises(ValidationError):
        NewsSearchRequest(
            query="private portfolio news",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            contains_sensitive_context=True,
        )
    with pytest.raises(ValidationError, match="account-like"):
        NewsSearchRequest(
            query="news for account 4111 1111 1111 1111",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )
