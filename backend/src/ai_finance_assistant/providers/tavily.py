"""Conditional live Tavily attributed-news discovery adapter."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

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
    NewsItem,
    NewsSearchRequest,
    NewsSearchResult,
    ProviderError,
    ProviderErrorCode,
    ProviderMode,
    ProviderReadiness,
    TimestampQuality,
)
from ai_finance_assistant.providers.runtime import (
    EndpointPolicy,
    ProviderCallError,
    ProviderRuntime,
    RuntimeOutcome,
    RuntimeValue,
)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_ENTITLEMENT = "conditional-private-demo; third-party source rights remain separate"
NEWS_POLICY = EndpointPolicy(
    timeout_seconds=8,
    max_attempts=2,
    base_backoff_seconds=0.25,
    max_backoff_seconds=2,
    cache_ttl_seconds=900,
    stale_if_error_seconds=3600,
)


class TavilyNewsProvider:
    provider_name = "tavily"
    mode = ProviderMode.LIVE

    def __init__(
        self,
        *,
        api_key: str | None,
        request_budget: int = 3,
        requests_per_minute: int = 10,
        entitlement: str = DEFAULT_ENTITLEMENT,
        terms_approved: bool = False,
        client: httpx.Client | None = None,
        runtime: ProviderRuntime | None = None,
        search_url: str = TAVILY_SEARCH_URL,
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
        self._search_url = search_url

    def readiness(self, required_requests: int = 1) -> ProviderReadiness:
        return self._runtime.readiness(
            credential_configured=self._api_key is not None,
            terms_approved=self._terms_approved,
            required_requests=required_requests,
        )

    def search(self, request: NewsSearchRequest) -> NewsSearchResult:
        cache_key = (
            f"news:{request.query.casefold()}:{','.join(request.symbols)}:"
            f"{request.start_date.isoformat()}:{request.end_date.isoformat()}:"
            f"{request.max_results}"
        )
        if self._api_key is None:
            now = datetime.now(UTC)
            outcome: RuntimeOutcome[tuple[NewsItem, ...]] = RuntimeOutcome(
                value=None,
                served_at=now,
                retrieved_at=None,
                cache_status=CacheStatus.NOT_APPLICABLE,
                cache_age_seconds=None,
                is_stale=False,
                attempts=0,
                error=ProviderError(
                    code=ProviderErrorCode.UNAUTHORIZED,
                    message="Tavily credential is not configured.",
                    retryable=False,
                ),
            )
        elif not self._terms_approved:
            now = datetime.now(UTC)
            outcome = RuntimeOutcome(
                value=None,
                served_at=now,
                retrieved_at=None,
                cache_status=CacheStatus.NOT_APPLICABLE,
                cache_age_seconds=None,
                is_stale=False,
                attempts=0,
                error=ProviderError(
                    code=ProviderErrorCode.ENTITLEMENT_REQUIRED,
                    message="Tavily account terms and entitlements are not approved.",
                    retryable=False,
                ),
            )
        else:
            outcome = self._runtime.execute(
                cache_key=cache_key,
                policy=NEWS_POLICY,
                fetch=lambda timeout: self._fetch_news(request, timeout),
            )
        items = outcome.value.data if outcome.value is not None else ()
        return NewsSearchResult(
            status=result_status(outcome.error, has_data=bool(items)),
            items=items,
            provenance=envelope_from_outcome(
                outcome,
                provider=self.provider_name,
                mode=self.mode,
                entitlement=self._entitlement,
            ),
            error=outcome.error,
            warnings=warnings_from_outcome(outcome),
        )

    def _fetch_news(
        self, request: NewsSearchRequest, timeout: float
    ) -> RuntimeValue[tuple[NewsItem, ...]]:
        assert self._api_key is not None
        body: dict[str, object] = {
            "query": request.query,
            "topic": "finance",
            "search_depth": "basic",
            "max_results": request.max_results,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "include_answer": False,
            "include_raw_content": False,
            "include_published_date": True,
        }
        try:
            response = self._client.post(
                self._search_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                ProviderErrorCode.TIMEOUT,
                "Tavily request timed out.",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderCallError(
                ProviderErrorCode.UNAVAILABLE,
                "Tavily request was unavailable.",
                retryable=True,
            ) from exc
        _raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise _malformed("Tavily returned invalid JSON.") from exc
        if not isinstance(payload, Mapping):
            raise _malformed("Tavily returned a non-object payload.")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise _malformed("Tavily response omitted results.")

        items: list[NewsItem] = []
        try:
            for raw in raw_results:
                if not isinstance(raw, Mapping):
                    raise ValueError
                url = str(raw["url"])
                published_at, timestamp_quality = _parse_published_date(raw.get("published_date"))
                hostname = urlparse(url).hostname
                if not hostname:
                    raise ValueError
                item_id = "news-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
                excerpt_value = raw.get("content")
                excerpt = str(excerpt_value)[:2000] if excerpt_value else None
                items.append(
                    NewsItem(
                        item_id=item_id,
                        publisher=hostname.removeprefix("www."),
                        url=url,
                        title=str(raw["title"]),
                        excerpt=excerpt,
                        published_at=published_at,
                        published_at_quality=timestamp_quality,
                        matched_symbols=request.symbols,
                    )
                )
        except (KeyError, TypeError, ValidationError, ValueError) as exc:
            raise _malformed("Tavily result fields were malformed.") from exc

        published = [item.published_at for item in items if item.published_at is not None]
        request_id = payload.get("request_id")
        return RuntimeValue(
            data=tuple(items),
            data_as_of=max(published) if published else None,
            delay_status=DelayStatus.UNKNOWN,
            timestamp_quality=(
                TimestampQuality.PROVIDER_ESTIMATED if published else TimestampQuality.UNAVAILABLE
            ),
            request_id=str(request_id)[:256] if request_id else None,
        )


def _parse_published_date(value: object) -> tuple[datetime | None, TimestampQuality]:
    if value is None or not str(value).strip():
        return None, TimestampQuality.UNAVAILABLE
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None, TimestampQuality.UNAVAILABLE
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed, TimestampQuality.PROVIDER_ESTIMATED


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise ProviderCallError(
            ProviderErrorCode.UNAUTHORIZED,
            "Tavily rejected the configured credential or entitlement.",
            retryable=False,
        )
    if response.status_code in {429, 432, 433}:
        raise ProviderCallError(
            ProviderErrorCode.RATE_LIMITED,
            "Tavily request or plan limit was reached.",
            retryable=response.status_code == 429,
            retry_after_seconds=retry_after_seconds(response.headers),
        )
    if response.status_code >= 500:
        raise ProviderCallError(
            ProviderErrorCode.UNAVAILABLE,
            "Tavily service returned an unavailable response.",
            retryable=True,
        )
    if response.status_code >= 400:
        raise ProviderCallError(
            ProviderErrorCode.INVALID_REQUEST,
            "Tavily rejected the public news query.",
            retryable=False,
        )


def _malformed(message: str) -> ProviderCallError:
    return ProviderCallError(
        ProviderErrorCode.MALFORMED_RESPONSE,
        message,
        retryable=False,
    )
