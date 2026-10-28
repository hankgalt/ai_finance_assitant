"""Provider provenance and quote contracts shared by enrichment consumers."""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier, ShortText


class DelayStatus(StrEnum):
    REAL_TIME = "real_time"
    DELAYED = "delayed"
    END_OF_DAY = "end_of_day"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class CacheStatus(StrEnum):
    MISS = "miss"
    HIT = "hit"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class ProviderProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ShortText
    data_as_of: AwareDatetime
    retrieved_at: AwareDatetime
    delay_status: DelayStatus = DelayStatus.UNKNOWN
    cache_status: CacheStatus = CacheStatus.NOT_APPLICABLE
    is_stale: bool = False


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    instrument_id: Identifier
    price: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    currency: CurrencyCode
    provenance: ProviderProvenance
