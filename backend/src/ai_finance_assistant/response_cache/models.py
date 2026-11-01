"""Versioned storage-neutral response-cache contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class CacheRecordKind(StrEnum):
    ROUTE = "route"
    GENERATION = "generation"


class CacheLookupOutcome(StrEnum):
    HIT = "hit"
    SHADOW_HIT = "shadow_hit"
    MISS = "miss"
    BYPASS = "bypass"
    ERROR = "error"


class CacheWriteOutcome(StrEnum):
    STORED = "stored"
    BYPASS = "bypass"
    ERROR = "error"


class CacheMatchKind(StrEnum):
    EXACT = "exact"
    SEMANTIC = "semantic"


class CacheReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    configured: bool
    available: bool
    adapter: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=256)


class CacheRecord(BaseModel):
    """Minimized value stored by a ModelResponseCache adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    kind: CacheRecordKind
    session_scope: str = Field(pattern=r"^[a-f0-9]{64}$")
    normalized_query: str = Field(min_length=1, max_length=20_000)
    filter_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload_json: str = Field(min_length=2, max_length=100_000)
    vector: tuple[float, ...] = Field(default=(), max_length=4096)
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def validate_lifecycle(self) -> CacheRecord:
        if self.expires_at <= self.created_at:
            raise ValueError("cache records must expire after creation")
        if self.kind == CacheRecordKind.GENERATION and not self.vector:
            raise ValueError("generation cache records require a semantic vector")
        if self.kind == CacheRecordKind.ROUTE and self.vector:
            raise ValueError("route cache records cannot contain a semantic vector")
        return self


class CacheLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CacheRecordKind
    session_scope: str = Field(pattern=r"^[a-f0-9]{64}$")
    normalized_query: str = Field(min_length=1, max_length=20_000)
    filter_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    vector: tuple[float, ...] = Field(default=(), max_length=4096)
    allow_semantic: bool = False
    minimum_similarity: float = Field(default=1.0, ge=0.0, le=1.0)
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_lookup(self) -> CacheLookupRequest:
        if self.kind == CacheRecordKind.GENERATION and not self.vector:
            raise ValueError("generation cache lookups require a semantic vector")
        if self.kind == CacheRecordKind.ROUTE and (self.vector or self.allow_semantic):
            raise ValueError("route cache lookups are exact-only")
        return self


class CacheLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: CacheLookupOutcome
    record: CacheRecord | None = None
    match_kind: CacheMatchKind | None = None
    similarity: float | None = Field(default=None, ge=-1.0, le=1.0)
    entry_age_seconds: float | None = Field(default=None, ge=0.0)
    reason: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_outcome(self) -> CacheLookupResult:
        if self.outcome == CacheLookupOutcome.HIT:
            if self.record is None or self.match_kind is None:
                raise ValueError("cache hits require a record and match kind")
        elif self.record is not None:
            raise ValueError("non-serving cache outcomes cannot expose a record")
        return self


class CacheWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: CacheWriteOutcome
    reason: str | None = Field(default=None, max_length=128)


class CacheOperationResult(BaseModel):
    """Validated application-level lookup result without storage details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: CacheLookupOutcome
    payload: dict[str, object] | None = None
    match_kind: CacheMatchKind | None = None
    similarity: float | None = Field(default=None, ge=-1.0, le=1.0)
    entry_age_seconds: float | None = Field(default=None, ge=0.0)
    reason: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_payload(self) -> CacheOperationResult:
        if self.outcome == CacheLookupOutcome.HIT and self.payload is None:
            raise ValueError("application cache hits require a validated payload")
        if self.outcome != CacheLookupOutcome.HIT and self.payload is not None:
            raise ValueError("non-serving outcomes cannot expose a payload")
        return self


def entry_age(record: CacheRecord, observed_at: datetime) -> float:
    return max(0.0, (observed_at - record.created_at).total_seconds())
