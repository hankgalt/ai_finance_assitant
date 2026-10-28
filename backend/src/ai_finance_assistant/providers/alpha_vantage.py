"""Conditional live Alpha Vantage market-data adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import ValidationError

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus
from ai_finance_assistant.providers._shared import (
    envelope_from_outcome,
    result_status,
    retry_after_seconds,
    warnings_from_outcome,
)
from ai_finance_assistant.providers.models import (
    AdjustmentBasis,
    HistoricalRequest,
    HistoricalResult,
    HistoricalSeries,
    InstrumentMatch,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    MarketQuote,
    PriceBar,
    ProviderError,
    ProviderErrorCode,
    ProviderMode,
    ProviderReadiness,
    QuoteRequest,
    QuoteResult,
    TimestampQuality,
)
from ai_finance_assistant.providers.runtime import (
    EndpointPolicy,
    ProviderCallError,
    ProviderRuntime,
    RuntimeOutcome,
    RuntimeValue,
)

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
DEFAULT_ENTITLEMENT = "conditional-private-demo; verify account terms before live use"
QUOTE_POLICY = EndpointPolicy(
    timeout_seconds=5,
    max_attempts=2,
    base_backoff_seconds=0.25,
    max_backoff_seconds=2,
    cache_ttl_seconds=300,
    stale_if_error_seconds=3600,
)
HISTORY_POLICY = EndpointPolicy(
    timeout_seconds=8,
    max_attempts=2,
    base_backoff_seconds=0.25,
    max_backoff_seconds=2,
    cache_ttl_seconds=21600,
    stale_if_error_seconds=86400,
)
SEARCH_POLICY = EndpointPolicy(
    timeout_seconds=5,
    max_attempts=2,
    base_backoff_seconds=0.25,
    max_backoff_seconds=2,
    cache_ttl_seconds=86400,
    stale_if_error_seconds=604800,
)


class AlphaVantageMarketDataProvider:
    provider_name = "alpha_vantage"
    mode = ProviderMode.LIVE

    def __init__(
        self,
        *,
        api_key: str | None,
        request_budget: int = 5,
        requests_per_minute: int = 5,
        entitlement: str = DEFAULT_ENTITLEMENT,
        terms_approved: bool = False,
        client: httpx.Client | None = None,
        runtime: ProviderRuntime | None = None,
        base_url: str = ALPHA_VANTAGE_URL,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._entitlement = entitlement
        self._terms_approved = terms_approved
        self._client = client or httpx.Client()
        self._runtime = runtime or ProviderRuntime(
            provider_name=self.provider_name,
            mode=self.mode,
            request_budget=request_budget,
            requests_per_window=requests_per_minute,
            max_concurrency=2,
        )
        self._base_url = base_url

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        return self._runtime.readiness(
            credential_configured=self._api_key is not None,
            terms_approved=self._terms_approved,
            required_requests=required_requests,
        )

    def search_instruments(self, request: InstrumentSearchRequest) -> InstrumentSearchResult:
        outcome = self._execute(
            cache_key=f"search:{request.query.casefold()}:{request.limit}",
            policy=SEARCH_POLICY,
            fetch=lambda timeout: self._fetch_search(request, timeout),
        )
        matches = outcome.value.data if outcome.value is not None else ()
        return InstrumentSearchResult(
            status=result_status(outcome.error, has_data=bool(matches)),
            matches=matches,
            provenance=envelope_from_outcome(
                outcome,
                provider=self.provider_name,
                mode=self.mode,
                entitlement=self._entitlement,
            ),
            error=outcome.error,
            warnings=warnings_from_outcome(outcome),
        )

    def get_quote(self, request: QuoteRequest) -> QuoteResult:
        outcome = self._execute(
            cache_key=f"quote:{request.symbol.upper()}:{request.currency}",
            policy=QUOTE_POLICY,
            fetch=lambda timeout: self._fetch_quote(request, timeout),
        )
        quote = outcome.value.data if outcome.value is not None else None
        return QuoteResult(
            status=result_status(outcome.error, has_data=quote is not None),
            quote=quote,
            provenance=envelope_from_outcome(
                outcome,
                provider=self.provider_name,
                mode=self.mode,
                entitlement=self._entitlement,
            ),
            error=outcome.error,
            warnings=warnings_from_outcome(outcome),
        )

    def get_history(self, request: HistoricalRequest) -> HistoricalResult:
        outcome = self._execute(
            cache_key=(
                f"history:{request.symbol.upper()}:{request.currency}:"
                f"{request.start_date.isoformat()}:{request.end_date.isoformat()}"
            ),
            policy=HISTORY_POLICY,
            fetch=lambda timeout: self._fetch_history(request, timeout),
        )
        series = outcome.value.data if outcome.value is not None else None
        has_data = series is not None and bool(series.bars)
        return HistoricalResult(
            status=result_status(outcome.error, has_data=has_data),
            series=series if has_data else None,
            provenance=envelope_from_outcome(
                outcome,
                provider=self.provider_name,
                mode=self.mode,
                entitlement=self._entitlement,
            ),
            error=outcome.error,
            warnings=warnings_from_outcome(outcome),
        )

    def _execute(
        self,
        *,
        cache_key: str,
        policy: EndpointPolicy,
        fetch: Callable[[float], RuntimeValue[Any]],
    ) -> RuntimeOutcome[Any]:
        if self._api_key is None:
            now = datetime.now(UTC)
            return RuntimeOutcome(
                value=None,
                served_at=now,
                retrieved_at=None,
                cache_status=CacheStatus.NOT_APPLICABLE,
                cache_age_seconds=None,
                is_stale=False,
                attempts=0,
                error=ProviderError(
                    code=ProviderErrorCode.UNAUTHORIZED,
                    message="Alpha Vantage credential is not configured.",
                    retryable=False,
                ),
            )
        if not self._terms_approved:
            now = datetime.now(UTC)
            return RuntimeOutcome(
                value=None,
                served_at=now,
                retrieved_at=None,
                cache_status=CacheStatus.NOT_APPLICABLE,
                cache_age_seconds=None,
                is_stale=False,
                attempts=0,
                error=ProviderError(
                    code=ProviderErrorCode.ENTITLEMENT_REQUIRED,
                    message="Alpha Vantage account terms and entitlements are not approved.",
                    retryable=False,
                ),
            )
        return self._runtime.execute(cache_key=cache_key, policy=policy, fetch=fetch)

    def _fetch_search(
        self, request: InstrumentSearchRequest, timeout: float
    ) -> RuntimeValue[tuple[InstrumentMatch, ...]]:
        payload = self._request_json(
            {"function": "SYMBOL_SEARCH", "keywords": request.query}, timeout
        )
        raw_matches = payload.get("bestMatches")
        if not isinstance(raw_matches, list):
            raise _malformed("Alpha Vantage search response omitted bestMatches.")
        matches: list[InstrumentMatch] = []
        try:
            for item in raw_matches[: request.limit]:
                if not isinstance(item, Mapping):
                    raise ValueError
                currency_value = item.get("8. currency")
                matches.append(
                    InstrumentMatch(
                        symbol=str(item["1. symbol"]),
                        name=str(item["2. name"]),
                        region=str(item["4. region"]) if item.get("4. region") else None,
                        currency=str(currency_value) if currency_value else None,
                        match_score=Decimal(str(item["9. matchScore"])),
                    )
                )
        except (KeyError, InvalidOperation, ValidationError, TypeError, ValueError) as exc:
            raise _malformed("Alpha Vantage search result was malformed.") from exc
        return RuntimeValue(
            data=tuple(matches),
            data_as_of=None,
            delay_status=DelayStatus.UNKNOWN,
            timestamp_quality=TimestampQuality.UNAVAILABLE,
        )

    def _fetch_quote(self, request: QuoteRequest, timeout: float) -> RuntimeValue[MarketQuote]:
        payload = self._request_json(
            {"function": "GLOBAL_QUOTE", "symbol": request.symbol}, timeout
        )
        raw = payload.get("Global Quote")
        if not isinstance(raw, Mapping):
            raise _malformed("Alpha Vantage quote response omitted Global Quote.")
        if not raw:
            raise ProviderCallError(
                ProviderErrorCode.INVALID_REQUEST,
                "Alpha Vantage returned no quote for the requested symbol.",
                retryable=False,
            )
        try:
            market_date = date.fromisoformat(str(raw["07. latest trading day"]))
            quote = MarketQuote(
                requested_symbol=request.symbol,
                resolved_symbol=str(raw["01. symbol"]),
                price=Decimal(str(raw["05. price"])),
                currency=request.currency,
                currency_source="request",
            )
        except (KeyError, InvalidOperation, ValidationError, ValueError) as exc:
            raise _malformed("Alpha Vantage quote fields were malformed.") from exc
        return RuntimeValue(
            data=quote,
            data_as_of=datetime.combine(market_date, time.min, tzinfo=UTC),
            delay_status=DelayStatus.END_OF_DAY,
            timestamp_quality=TimestampQuality.DATE_ONLY,
        )

    def _fetch_history(
        self, request: HistoricalRequest, timeout: float
    ) -> RuntimeValue[HistoricalSeries]:
        payload = self._request_json(
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": request.symbol,
                "outputsize": "compact",
            },
            timeout,
        )
        raw_series = payload.get("Time Series (Daily)")
        if not isinstance(raw_series, Mapping):
            raise _malformed("Alpha Vantage history response omitted the daily series.")
        bars: list[PriceBar] = []
        try:
            for raw_date, raw_bar in raw_series.items():
                trading_date = date.fromisoformat(str(raw_date))
                if not request.start_date <= trading_date <= request.end_date:
                    continue
                if not isinstance(raw_bar, Mapping):
                    raise ValueError
                bars.append(
                    PriceBar(
                        trading_date=trading_date,
                        open=Decimal(str(raw_bar["1. open"])),
                        high=Decimal(str(raw_bar["2. high"])),
                        low=Decimal(str(raw_bar["3. low"])),
                        close=Decimal(str(raw_bar["4. close"])),
                        volume=Decimal(str(raw_bar["5. volume"])),
                    )
                )
        except (KeyError, InvalidOperation, ValidationError, TypeError, ValueError) as exc:
            raise _malformed("Alpha Vantage daily price fields were malformed.") from exc
        bars.sort(key=lambda item: item.trading_date)
        latest = bars[-1].trading_date if bars else request.end_date
        return RuntimeValue(
            data=HistoricalSeries(
                requested_symbol=request.symbol,
                resolved_symbol=request.symbol.upper(),
                currency=request.currency,
                currency_source="request",
                adjustment_basis=AdjustmentBasis.RAW,
                bars=tuple(bars),
            ),
            data_as_of=datetime.combine(latest, time.min, tzinfo=UTC) if bars else None,
            delay_status=DelayStatus.HISTORICAL,
            timestamp_quality=(
                TimestampQuality.DATE_ONLY if bars else TimestampQuality.UNAVAILABLE
            ),
        )

    def _request_json(self, params: dict[str, str], timeout: float) -> dict[str, Any]:
        assert self._api_key is not None
        safe_params = {**params, "apikey": self._api_key}
        try:
            response = self._client.get(self._base_url, params=safe_params, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                ProviderErrorCode.TIMEOUT,
                "Alpha Vantage request timed out.",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderCallError(
                ProviderErrorCode.UNAVAILABLE,
                "Alpha Vantage request was unavailable.",
                retryable=True,
            ) from exc
        _raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise _malformed("Alpha Vantage returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise _malformed("Alpha Vantage returned a non-object payload.")
        if "Error Message" in payload:
            raise ProviderCallError(
                ProviderErrorCode.INVALID_REQUEST,
                "Alpha Vantage rejected the symbol or request.",
                retryable=False,
            )
        message = str(payload.get("Note") or payload.get("Information") or "")
        if message:
            lower = message.casefold()
            if "rate" in lower or "frequency" in lower or "limit" in lower:
                raise ProviderCallError(
                    ProviderErrorCode.RATE_LIMITED,
                    "Alpha Vantage reported a request or plan limit.",
                    retryable=False,
                )
            raise ProviderCallError(
                ProviderErrorCode.UNAVAILABLE,
                "Alpha Vantage reported that the endpoint is unavailable for this entitlement.",
                retryable=False,
            )
        return payload


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise ProviderCallError(
            ProviderErrorCode.UNAUTHORIZED,
            "Alpha Vantage rejected the configured credential or entitlement.",
            retryable=False,
        )
    if response.status_code == 429:
        raise ProviderCallError(
            ProviderErrorCode.RATE_LIMITED,
            "Alpha Vantage rate limit was reached.",
            retryable=True,
            retry_after_seconds=retry_after_seconds(response.headers),
        )
    if response.status_code >= 500:
        raise ProviderCallError(
            ProviderErrorCode.UNAVAILABLE,
            "Alpha Vantage service returned an unavailable response.",
            retryable=True,
        )
    if response.status_code >= 400:
        raise ProviderCallError(
            ProviderErrorCode.INVALID_REQUEST,
            "Alpha Vantage rejected the request.",
            retryable=False,
        )


def _malformed(message: str) -> ProviderCallError:
    return ProviderCallError(
        ProviderErrorCode.MALFORMED_RESPONSE,
        message,
        retryable=False,
    )
