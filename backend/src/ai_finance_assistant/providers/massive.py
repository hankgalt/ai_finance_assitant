"""Conditional live Massive end-of-day market-data adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

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

MASSIVE_BASE_URL = "https://api.massive.com"
DEFAULT_ENTITLEMENT = (
    "conditional-owner-only-demo; verify business/display rights before sharing data"
)
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


class MassiveMarketDataProvider:
    provider_name = "massive"
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
        base_url: str = MASSIVE_BASE_URL,
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
        self._base_url = base_url.rstrip("/")

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
        market_quote = outcome.value.data if outcome.value is not None else None
        return QuoteResult(
            status=result_status(outcome.error, has_data=market_quote is not None),
            quote=market_quote,
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
            return _gated_outcome(
                ProviderErrorCode.UNAUTHORIZED,
                "Massive credential is not configured.",
            )
        if not self._terms_approved:
            return _gated_outcome(
                ProviderErrorCode.ENTITLEMENT_REQUIRED,
                "Massive account terms and entitlements are not approved.",
            )
        return self._runtime.execute(cache_key=cache_key, policy=policy, fetch=fetch)

    def _fetch_search(
        self, request: InstrumentSearchRequest, timeout: float
    ) -> RuntimeValue[tuple[InstrumentMatch, ...]]:
        payload = self._request_json(
            "/v3/reference/tickers",
            {
                "market": "stocks",
                "active": "true",
                "search": request.query,
                "limit": str(request.limit),
            },
            timeout,
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise _malformed("Massive ticker-search response omitted results.")
        matches: list[InstrumentMatch] = []
        try:
            for raw in raw_results[: request.limit]:
                if not isinstance(raw, Mapping):
                    raise ValueError
                currency_value = raw.get("currency_name")
                locale_value = raw.get("locale")
                matches.append(
                    InstrumentMatch(
                        symbol=str(raw["ticker"]),
                        name=str(raw["name"]),
                        region=str(locale_value).upper() if locale_value else None,
                        currency=str(currency_value).upper() if currency_value else None,
                        match_score=None,
                    )
                )
        except (KeyError, ValidationError, TypeError, ValueError) as exc:
            raise _malformed("Massive ticker-search result was malformed.") from exc
        return RuntimeValue(
            data=tuple(matches),
            data_as_of=None,
            delay_status=DelayStatus.UNKNOWN,
            timestamp_quality=TimestampQuality.UNAVAILABLE,
            request_id=_request_id(payload),
        )

    def _fetch_quote(self, request: QuoteRequest, timeout: float) -> RuntimeValue[MarketQuote]:
        symbol = quote(request.symbol.upper(), safe="")
        payload = self._request_json(
            f"/v2/aggs/ticker/{symbol}/prev",
            {"adjusted": "false"},
            timeout,
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise _malformed("Massive previous-day response omitted results.")
        if not raw_results:
            raise ProviderCallError(
                ProviderErrorCode.INVALID_REQUEST,
                "Massive returned no previous-day bar for the requested symbol.",
                retryable=False,
            )
        raw = raw_results[0]
        if not isinstance(raw, Mapping):
            raise _malformed("Massive previous-day result was malformed.")
        try:
            market_quote = MarketQuote(
                requested_symbol=request.symbol,
                resolved_symbol=str(raw.get("T") or payload["ticker"]),
                price=Decimal(str(raw["c"])),
                currency=request.currency,
                currency_source="request",
            )
            bar_started_at = datetime.fromtimestamp(int(str(raw["t"])) / 1000, tz=UTC)
        except (KeyError, InvalidOperation, ValidationError, TypeError, ValueError) as exc:
            raise _malformed("Massive previous-day fields were malformed.") from exc
        return RuntimeValue(
            data=market_quote,
            data_as_of=bar_started_at,
            delay_status=DelayStatus.END_OF_DAY,
            timestamp_quality=TimestampQuality.DATE_ONLY,
            request_id=_request_id(payload),
        )

    def _fetch_history(
        self, request: HistoricalRequest, timeout: float
    ) -> RuntimeValue[HistoricalSeries]:
        symbol = quote(request.symbol.upper(), safe="")
        payload = self._request_json(
            (
                f"/v2/aggs/ticker/{symbol}/range/1/day/"
                f"{request.start_date.isoformat()}/{request.end_date.isoformat()}"
            ),
            {"adjusted": "false", "sort": "asc", "limit": "5000"},
            timeout,
        )
        if payload.get("next_url"):
            raise _malformed("Massive daily-history response was unexpectedly paginated.")
        if payload.get("adjusted") is not False:
            raise _malformed("Massive daily-history response did not confirm raw prices.")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise _malformed("Massive daily-history response omitted results.")
        bars: list[PriceBar] = []
        try:
            for raw in raw_results:
                if not isinstance(raw, Mapping):
                    raise ValueError
                trading_date = datetime.fromtimestamp(
                    int(str(raw["t"])) / 1000,
                    tz=UTC,
                ).date()
                if not request.start_date <= trading_date <= request.end_date:
                    continue
                bars.append(
                    PriceBar(
                        trading_date=trading_date,
                        open=Decimal(str(raw["o"])),
                        high=Decimal(str(raw["h"])),
                        low=Decimal(str(raw["l"])),
                        close=Decimal(str(raw["c"])),
                        volume=Decimal(str(raw["v"])),
                    )
                )
        except (
            KeyError,
            InvalidOperation,
            ValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise _malformed("Massive daily-history fields were malformed.") from exc
        bars.sort(key=lambda item: item.trading_date)
        latest = bars[-1].trading_date if bars else None
        return RuntimeValue(
            data=HistoricalSeries(
                requested_symbol=request.symbol,
                resolved_symbol=str(payload.get("ticker") or request.symbol.upper()),
                currency=request.currency,
                currency_source="request",
                adjustment_basis=AdjustmentBasis.RAW,
                bars=tuple(bars),
            ),
            data_as_of=(
                datetime.combine(latest, datetime.min.time(), tzinfo=UTC) if latest else None
            ),
            delay_status=DelayStatus.HISTORICAL,
            timestamp_quality=(
                TimestampQuality.DATE_ONLY if bars else TimestampQuality.UNAVAILABLE
            ),
            request_id=_request_id(payload),
        )

    def _request_json(
        self,
        path: str,
        params: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        assert self._api_key is not None
        try:
            response = self._client.get(
                f"{self._base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                ProviderErrorCode.TIMEOUT,
                "Massive request timed out.",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderCallError(
                ProviderErrorCode.UNAVAILABLE,
                "Massive request was unavailable.",
                retryable=True,
            ) from exc
        _raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise _malformed("Massive returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise _malformed("Massive returned a non-object payload.")
        if "status" not in payload:
            raise _malformed("Massive response omitted status.")
        status = payload.get("status")
        if status is not None and str(status).upper() != "OK":
            raise ProviderCallError(
                ProviderErrorCode.INVALID_REQUEST,
                "Massive returned a non-success response.",
                retryable=False,
            )
        return payload


def _gated_outcome(code: ProviderErrorCode, message: str) -> RuntimeOutcome[Any]:
    now = datetime.now(UTC)
    return RuntimeOutcome(
        value=None,
        served_at=now,
        retrieved_at=None,
        cache_status=CacheStatus.NOT_APPLICABLE,
        cache_age_seconds=None,
        is_stale=False,
        attempts=0,
        error=ProviderError(code=code, message=message, retryable=False),
    )


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise ProviderCallError(
            ProviderErrorCode.UNAUTHORIZED,
            "Massive rejected the configured credential.",
            retryable=False,
        )
    if response.status_code == 403:
        raise ProviderCallError(
            ProviderErrorCode.ENTITLEMENT_REQUIRED,
            "Massive rejected the endpoint, recency, or account entitlement.",
            retryable=False,
        )
    if response.status_code == 429:
        raise ProviderCallError(
            ProviderErrorCode.RATE_LIMITED,
            "Massive request limit was reached.",
            retryable=False,
            retry_after_seconds=retry_after_seconds(response.headers),
        )
    if response.status_code >= 500:
        raise ProviderCallError(
            ProviderErrorCode.UNAVAILABLE,
            "Massive service returned an unavailable response.",
            retryable=True,
        )
    if response.status_code >= 400:
        raise ProviderCallError(
            ProviderErrorCode.INVALID_REQUEST,
            "Massive rejected the request.",
            retryable=False,
        )


def _request_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("request_id")
    return str(value)[:256] if value else None


def _malformed(message: str) -> ProviderCallError:
    return ProviderCallError(
        ProviderErrorCode.MALFORMED_RESPONSE,
        message,
        retryable=False,
    )
