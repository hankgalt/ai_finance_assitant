"""Application-owned market and news provider contracts."""

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier, ShortText
from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus

PublicQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=200),
]


class ProviderMode(StrEnum):
    LIVE = "live"
    CREDENTIAL_FREE = "credential_free"


class ProviderStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED = "unauthorized"
    ENTITLEMENT_REQUIRED = "entitlement_required"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    UNAVAILABLE = "unavailable"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CIRCUIT_OPEN = "circuit_open"
    CONCURRENCY_LIMITED = "concurrency_limited"


class ProviderErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED = "unauthorized"
    ENTITLEMENT_REQUIRED = "entitlement_required"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    UNAVAILABLE = "unavailable"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CIRCUIT_OPEN = "circuit_open"
    CONCURRENCY_LIMITED = "concurrency_limited"


class TimestampQuality(StrEnum):
    EXACT = "exact"
    DATE_ONLY = "date_only"
    PROVIDER_ESTIMATED = "provider_estimated"
    UNAVAILABLE = "unavailable"


class AdjustmentBasis(StrEnum):
    RAW = "raw"
    ADJUSTED = "adjusted"
    UNKNOWN = "unknown"


class CacheLayer(StrEnum):
    MEMORY = "memory"
    DURABLE = "durable"
    PROVIDER = "provider"
    NOT_APPLICABLE = "not_applicable"


class CacheCoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class ProviderError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ProviderErrorCode
    message: ShortText
    retryable: bool
    retry_after_seconds: float | None = Field(default=None, ge=0, le=3600)


class ProviderWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=80)
    message: ShortText


class ProviderEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ShortText
    mode: ProviderMode
    entitlement: ShortText
    served_at: AwareDatetime
    retrieved_at: AwareDatetime | None = None
    data_as_of: AwareDatetime | None = None
    delay_status: DelayStatus = DelayStatus.UNKNOWN
    timestamp_quality: TimestampQuality = TimestampQuality.UNAVAILABLE
    cache_status: CacheStatus = CacheStatus.NOT_APPLICABLE
    cache_layer: CacheLayer = CacheLayer.NOT_APPLICABLE
    cache_coverage: CacheCoverageStatus = CacheCoverageStatus.NOT_APPLICABLE
    cache_age_seconds: float | None = Field(default=None, ge=0)
    is_stale: bool = False
    is_synthetic: bool = False
    request_id: str | None = Field(default=None, max_length=256)
    attempts: int = Field(default=0, ge=0, le=20)

    @model_validator(mode="after")
    def validate_truthful_labels(self) -> "ProviderEnvelope":
        if self.is_synthetic != (self.mode == ProviderMode.CREDENTIAL_FREE):
            raise ValueError(
                "credential-free provenance must be synthetic and live provenance must not"
            )
        if self.is_stale != (self.cache_status == CacheStatus.STALE):
            raise ValueError("stale state and cache status must agree")
        if (
            self.cache_status in {CacheStatus.HIT, CacheStatus.STALE}
            and self.cache_age_seconds is None
        ):
            raise ValueError("cached results require cache age")
        return self


class ProviderReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ShortText
    mode: ProviderMode
    ready: bool
    credential_configured: bool
    terms_approved: bool
    remaining_request_budget: int = Field(ge=0)
    reason: ShortText


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Identifier
    currency: CurrencyCode


class HistoricalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Identifier
    currency: CurrencyCode
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "HistoricalRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if (self.end_date - self.start_date).days > 3660:
            raise ValueError("historical ranges are limited to ten years")
        return self


class InstrumentSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: PublicQuery
    limit: int = Field(default=5, ge=1, le=10)


class NewsSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: PublicQuery
    symbols: tuple[Identifier, ...] = Field(default=(), max_length=10)
    start_date: date
    end_date: date
    max_results: int = Field(default=5, ge=1, le=10)
    contains_sensitive_context: Literal[False] = False

    @model_validator(mode="after")
    def validate_window(self) -> "NewsSearchRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if (self.end_date - self.start_date).days > 31:
            raise ValueError("news windows are limited to 31 days")
        if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", self.query):
            raise ValueError("news queries cannot contain an email address")
        if re.search(r"(?:\d[ -]?){9,19}", self.query):
            raise ValueError("news queries cannot contain long account-like numbers")
        if re.search(
            r"(?i)\b(?:account|routing|card|ssn|social security)\s*(?:number|no\.?|#|:)",
            self.query,
        ):
            raise ValueError("news queries cannot contain account credential fields")
        return self


class MarketQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_symbol: Identifier
    resolved_symbol: Identifier
    price: Decimal = Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=8)
    currency: CurrencyCode
    currency_source: Literal["request", "provider"]


class PriceBar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trading_date: date
    open: Decimal = Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=8)
    high: Decimal = Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=8)
    low: Decimal = Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=8)
    close: Decimal = Field(gt=0, allow_inf_nan=False, max_digits=24, decimal_places=8)
    volume: Decimal = Field(
        ge=0,
        allow_inf_nan=False,
        max_digits=28,
        decimal_places=8,
    )

    @model_validator(mode="after")
    def validate_ohlc(self) -> "PriceBar":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the greatest OHLC value")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the least OHLC value")
        return self


class HistoricalSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_symbol: Identifier
    resolved_symbol: Identifier
    currency: CurrencyCode
    currency_source: Literal["request", "provider"]
    adjustment_basis: AdjustmentBasis
    bars: tuple[PriceBar, ...]


class InstrumentMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Identifier
    name: ShortText
    region: str | None = Field(default=None, max_length=128)
    currency: CurrencyCode | None = None
    match_score: Decimal | None = Field(default=None, ge=0, le=1)


class NewsItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: Identifier
    publisher: ShortText
    url: HttpUrl
    title: str = Field(min_length=1, max_length=512)
    excerpt: str | None = Field(default=None, max_length=2000)
    published_at: AwareDatetime | None = None
    published_at_quality: TimestampQuality
    matched_symbols: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_publication_time(self) -> "NewsItem":
        unavailable = self.published_at_quality == TimestampQuality.UNAVAILABLE
        if unavailable != (self.published_at is None):
            raise ValueError("publication timestamp and quality must agree")
        return self


class QuoteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderStatus
    quote: MarketQuote | None = None
    provenance: ProviderEnvelope
    error: ProviderError | None = None
    warnings: tuple[ProviderWarning, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "QuoteResult":
        _validate_result_shape(self.status, self.quote, self.error, self.provenance)
        return self


class HistoricalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderStatus
    series: HistoricalSeries | None = None
    provenance: ProviderEnvelope
    error: ProviderError | None = None
    warnings: tuple[ProviderWarning, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "HistoricalResult":
        _validate_result_shape(self.status, self.series, self.error, self.provenance)
        return self


class InstrumentSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderStatus
    matches: tuple[InstrumentMatch, ...] = ()
    provenance: ProviderEnvelope
    error: ProviderError | None = None
    warnings: tuple[ProviderWarning, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "InstrumentSearchResult":
        data: object | None = self.matches if self.matches else None
        _validate_result_shape(self.status, data, self.error, self.provenance)
        return self


class NewsSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderStatus
    items: tuple[NewsItem, ...] = ()
    provenance: ProviderEnvelope
    error: ProviderError | None = None
    warnings: tuple[ProviderWarning, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> "NewsSearchResult":
        data: object | None = self.items if self.items else None
        _validate_result_shape(self.status, data, self.error, self.provenance)
        return self


def _validate_result_shape(
    status: ProviderStatus,
    data: object | None,
    error: ProviderError | None,
    provenance: ProviderEnvelope,
) -> None:
    if status == ProviderStatus.SUCCESS and data is None:
        raise ValueError("success requires data")
    if status == ProviderStatus.EMPTY and data is not None:
        raise ValueError("empty status cannot contain data")
    if status not in {ProviderStatus.SUCCESS, ProviderStatus.EMPTY} and error is None:
        raise ValueError("failure status requires a typed error")
    if data is not None and error is not None and not provenance.is_stale:
        raise ValueError("data and an error may coexist only for a stale-cache fallback")
