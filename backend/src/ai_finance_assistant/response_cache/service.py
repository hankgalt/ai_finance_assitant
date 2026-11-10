"""Deep application service for evidence-bound route and generation reuse."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Generator
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.knowledge.models import Evidence
from ai_finance_assistant.knowledge.representations import RepresentationEncoder
from ai_finance_assistant.llm.models import (
    ModelOutput,
    PublicRagCacheEligibility,
    RoutingModelOutput,
    RoutingReason,
)
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheLookupRequest,
    CacheLookupResult,
    CacheMatchKind,
    CacheOperationResult,
    CacheReadiness,
    CacheRecord,
    CacheRecordKind,
    CacheWriteOutcome,
    CacheWriteResult,
)
from ai_finance_assistant.response_cache.ports import ModelResponseCache

SemanticServingMode = Literal["disabled", "shadow", "serving"]
_ELIGIBLE_AGENTS = frozenset({AgentId.FINANCE_QA, AgentId.TAX_EDUCATION})
_WHITESPACE = re.compile(r"\s+")


class RouteCacheContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: str | None = Field(default=None, min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    message: str = Field(min_length=1, max_length=20_000)
    locale: str = Field(min_length=2, max_length=35)
    jurisdiction: str = Field(min_length=2, max_length=32)
    workflow_version: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=128)
    has_context_references: bool = False
    checkpoint_dependent: bool = False


class GenerationCacheContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    principal_id: str | None = Field(default=None, min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    agent_id: AgentId
    message: str = Field(min_length=1, max_length=20_000)
    locale: str = Field(min_length=2, max_length=35)
    jurisdiction: str = Field(min_length=2, max_length=32)
    workflow_version: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=128)
    instructions: str = Field(min_length=1, max_length=4_000)
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=10)
    tax_year: int | None = Field(default=None, ge=2000, le=2200)
    public_rag_eligible: bool = False
    has_context_references: bool = False
    checkpoint_dependent: bool = False


class ResponseCacheService:
    """Own policy, versioning, validation, and fail-open behavior around the cache port."""

    def __init__(
        self,
        *,
        adapter: ModelResponseCache,
        encoder: RepresentationEncoder,
        policy_version: str,
        schema_version: str,
        ttl_seconds: int,
        minimum_semantic_similarity: float,
        semantic_mode: SemanticServingMode,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if ttl_seconds < 1 or ttl_seconds > 86_400:
            raise ValueError("response-cache TTL must be between 1 second and 24 hours")
        if not 0.0 <= minimum_semantic_similarity <= 1.0:
            raise ValueError("minimum semantic similarity must be between zero and one")
        self._adapter = adapter
        self._encoder = encoder
        self.policy_version = policy_version
        self.schema_version = schema_version
        self.ttl_seconds = ttl_seconds
        self.minimum_semantic_similarity = minimum_semantic_similarity
        self.semantic_mode = semantic_mode
        self._clock = clock
        self._coalescer = _KeyedRequestCoalescer()
        readiness = adapter.readiness()
        self._configured = readiness.configured
        self.adapter_name = readiness.adapter

    @property
    def configured(self) -> bool:
        return self._configured

    @property
    def encoder_identity(self) -> str:
        return f"{self._encoder.dense_model_id}@{self._encoder.dense_model_revision}"

    def readiness(self) -> CacheReadiness:
        return self._adapter.readiness()

    def lookup_route(self, context: RouteCacheContext) -> CacheOperationResult:
        bypass = self._route_shape_bypass(context)
        if bypass is not None:
            return bypass
        try:
            result = self._adapter.lookup(self._route_lookup_request(context))
        except Exception:
            return _error("cache_lookup_failed")
        if result.outcome != CacheLookupOutcome.HIT or result.record is None:
            return _operation_from_lookup(result)
        try:
            output = RoutingModelOutput.model_validate_json(result.record.payload_json)
        except Exception:
            return _error("cached_schema_invalid")
        if not _qualified_route(output):
            return _error("cached_route_ineligible")
        return CacheOperationResult(
            outcome=CacheLookupOutcome.HIT,
            payload=cast(dict[str, object], output.model_dump(mode="json")),
            match_kind=CacheMatchKind.EXACT,
            entry_age_seconds=result.entry_age_seconds,
        )

    def store_route(
        self,
        context: RouteCacheContext,
        output: RoutingModelOutput,
    ) -> CacheWriteResult:
        bypass = self._route_shape_bypass(context)
        if bypass is not None:
            return CacheWriteResult(
                outcome=CacheWriteOutcome.BYPASS,
                reason=bypass.reason,
            )
        if not _qualified_route(output):
            return CacheWriteResult(
                outcome=CacheWriteOutcome.BYPASS,
                reason="route_not_public_rag",
            )
        observed_at = self._clock()
        lookup = self._route_lookup_request(context, observed_at=observed_at)
        record = CacheRecord(
            kind=CacheRecordKind.ROUTE,
            session_scope=lookup.session_scope,
            normalized_query=lookup.normalized_query,
            filter_fingerprint=lookup.filter_fingerprint,
            payload_json=output.model_dump_json(),
            created_at=observed_at,
            expires_at=observed_at + timedelta(seconds=self.ttl_seconds),
        )
        return self._store(record)

    def lookup_generation(self, context: GenerationCacheContext) -> CacheOperationResult:
        bypass = self._generation_bypass(context)
        if bypass is not None:
            return bypass
        try:
            result = self._adapter.lookup(self._generation_lookup_request(context))
        except Exception:
            return _error("cache_lookup_failed")
        if result.outcome != CacheLookupOutcome.HIT or result.record is None:
            return _operation_from_lookup(result)
        if result.match_kind == CacheMatchKind.SEMANTIC:
            if result.similarity is None or result.similarity < self.minimum_semantic_similarity:
                return CacheOperationResult(
                    outcome=CacheLookupOutcome.MISS,
                    similarity=result.similarity,
                    reason="below_minimum_similarity",
                )
            if self.semantic_mode != "serving":
                return CacheOperationResult(
                    outcome=CacheLookupOutcome.SHADOW_HIT,
                    match_kind=CacheMatchKind.SEMANTIC,
                    similarity=result.similarity,
                    entry_age_seconds=result.entry_age_seconds,
                    reason=(
                        "semantic_shadow_mode"
                        if self.semantic_mode == "shadow"
                        else "semantic_serving_disabled"
                    ),
                )
        try:
            output = ModelOutput.model_validate_json(result.record.payload_json)
        except Exception:
            return _error("cached_schema_invalid")
        return CacheOperationResult(
            outcome=CacheLookupOutcome.HIT,
            payload=cast(dict[str, object], output.model_dump(mode="json")),
            match_kind=result.match_kind,
            similarity=result.similarity,
            entry_age_seconds=result.entry_age_seconds,
        )

    def store_generation(
        self,
        context: GenerationCacheContext,
        output: ModelOutput,
    ) -> CacheWriteResult:
        bypass = self._generation_bypass(context)
        if bypass is not None:
            return CacheWriteResult(
                outcome=CacheWriteOutcome.BYPASS,
                reason=bypass.reason,
            )
        observed_at = self._clock()
        try:
            lookup = self._generation_lookup_request(context, observed_at=observed_at)
        except Exception:
            return CacheWriteResult(
                outcome=CacheWriteOutcome.ERROR,
                reason="cache_embedding_failed",
            )
        record = CacheRecord(
            kind=CacheRecordKind.GENERATION,
            session_scope=lookup.session_scope,
            normalized_query=lookup.normalized_query,
            filter_fingerprint=lookup.filter_fingerprint,
            payload_json=output.model_dump_json(),
            vector=lookup.vector,
            created_at=observed_at,
            expires_at=observed_at + timedelta(seconds=self.ttl_seconds),
        )
        return self._store(record)

    @contextmanager
    def route_guard(self, context: RouteCacheContext) -> Generator[None, None, None]:
        if not self.configured:
            with nullcontext():
                yield
            return
        key = self._coalescing_key(
            CacheRecordKind.ROUTE,
            self._session_scope(context.session_id, principal_id=context.principal_id),
            normalize_query(context.message),
            self._route_filter_fingerprint(context),
        )
        with self._coalescer.guard(key):
            yield

    @contextmanager
    def generation_guard(self, context: GenerationCacheContext) -> Generator[None, None, None]:
        if not self.configured or self._generation_bypass(context) is not None:
            with nullcontext():
                yield
            return
        key = self._coalescing_key(
            CacheRecordKind.GENERATION,
            self._session_scope(context.session_id, principal_id=context.principal_id),
            normalize_query(context.message),
            self._generation_filter_fingerprint(context),
        )
        with self._coalescer.guard(key):
            yield

    def purge_session(self, session_id: str, *, principal_id: str | None = None) -> int:
        try:
            return self._adapter.purge_session(
                self._session_scope(session_id, principal_id=principal_id)
            )
        except Exception:
            return 0

    def purge_all(self) -> int:
        try:
            return self._adapter.purge_all()
        except Exception:
            return 0

    def close(self) -> None:
        try:
            self._adapter.close()
        except Exception:
            return None

    def _route_lookup_request(
        self,
        context: RouteCacheContext,
        *,
        observed_at: datetime | None = None,
    ) -> CacheLookupRequest:
        return CacheLookupRequest(
            kind=CacheRecordKind.ROUTE,
            session_scope=self._session_scope(
                context.session_id,
                principal_id=context.principal_id,
            ),
            normalized_query=normalize_query(context.message),
            filter_fingerprint=self._route_filter_fingerprint(context),
            observed_at=observed_at or self._clock(),
        )

    def _generation_lookup_request(
        self,
        context: GenerationCacheContext,
        *,
        observed_at: datetime | None = None,
    ) -> CacheLookupRequest:
        vector = tuple(float(value) for value in self._encoder.embed_dense([context.message])[0])
        return CacheLookupRequest(
            kind=CacheRecordKind.GENERATION,
            session_scope=self._session_scope(
                context.session_id,
                principal_id=context.principal_id,
            ),
            normalized_query=normalize_query(context.message),
            filter_fingerprint=self._generation_filter_fingerprint(context),
            vector=vector,
            allow_semantic=self.semantic_mode in {"shadow", "serving"},
            minimum_similarity=self.minimum_semantic_similarity,
            observed_at=observed_at or self._clock(),
        )

    def _route_filter_fingerprint(self, context: RouteCacheContext) -> str:
        return _fingerprint(
            {
                "cache_policy_version": self.policy_version,
                "cache_schema_version": self.schema_version,
                "jurisdiction": context.jurisdiction,
                "locale": context.locale,
                "model_id": context.model_id,
                "prompt_version": context.prompt_version,
                "provider_id": context.provider_id,
                "response_schema": "routing-model-output-v1",
                "workflow_version": context.workflow_version,
            }
        )

    def _generation_filter_fingerprint(self, context: GenerationCacheContext) -> str:
        evidence_fingerprint = _evidence_fingerprint(context.evidence)
        jurisdiction = (
            "US-Federal" if context.agent_id == AgentId.TAX_EDUCATION else context.jurisdiction
        )
        return _fingerprint(
            {
                "agent_id": context.agent_id.value,
                "cache_policy_version": self.policy_version,
                "cache_schema_version": self.schema_version,
                "encoder_artifact_sha256": self._encoder.dense_artifact_sha256,
                "encoder_model_id": self._encoder.dense_model_id,
                "encoder_revision": self._encoder.dense_model_revision,
                "evidence_fingerprint": evidence_fingerprint,
                "instruction_fingerprint": hashlib.sha256(
                    context.instructions.encode()
                ).hexdigest(),
                "jurisdiction": jurisdiction,
                "locale": context.locale,
                "model_id": context.model_id,
                "prompt_version": context.prompt_version,
                "provider_id": context.provider_id,
                "response_schema": "model-output-v1",
                "tax_year": context.tax_year,
                "workflow_version": context.workflow_version,
            }
        )

    def _route_shape_bypass(self, context: RouteCacheContext) -> CacheOperationResult | None:
        if not self.configured:
            return _bypass("cache_disabled")
        if context.has_context_references:
            return _bypass("context_bearing_request")
        if context.checkpoint_dependent:
            return _bypass("checkpoint_dependent_request")
        return None

    def _generation_bypass(
        self,
        context: GenerationCacheContext,
    ) -> CacheOperationResult | None:
        if not self.configured:
            return _bypass("cache_disabled")
        if not context.public_rag_eligible:
            return _bypass("route_not_public_rag")
        if context.agent_id not in _ELIGIBLE_AGENTS:
            return _bypass("agent_ineligible")
        if context.has_context_references:
            return _bypass("context_bearing_request")
        if context.checkpoint_dependent:
            return _bypass("checkpoint_dependent_request")
        if context.agent_id == AgentId.TAX_EDUCATION:
            if context.jurisdiction != "US" or context.tax_year is None:
                return _bypass("tax_scope_incomplete")
        elif context.tax_year is not None:
            return _bypass("unexpected_tax_scope")
        return None

    def _store(self, record: CacheRecord) -> CacheWriteResult:
        try:
            self._adapter.store(record)
        except Exception:
            return CacheWriteResult(
                outcome=CacheWriteOutcome.ERROR,
                reason="cache_store_failed",
            )
        return CacheWriteResult(outcome=CacheWriteOutcome.STORED)

    @staticmethod
    def _session_scope(session_id: str, *, principal_id: str | None = None) -> str:
        if principal_id is None:
            material = f"response-cache-scope-v1\0{session_id}"
        else:
            material = f"response-cache-scope-v2\0{principal_id}\0{session_id}"
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _coalescing_key(
        kind: CacheRecordKind,
        session_scope: str,
        normalized_query: str,
        filter_fingerprint: str,
    ) -> str:
        return hashlib.sha256(
            "\0".join((kind.value, session_scope, normalized_query, filter_fingerprint)).encode()
        ).hexdigest()


class _KeyedRequestCoalescer:
    def __init__(self) -> None:
        self._registry_lock = Lock()
        self._locks: dict[str, tuple[Lock, int]] = {}

    @contextmanager
    def guard(self, key: str) -> Generator[None, None, None]:
        with self._registry_lock:
            lock, count = self._locks.get(key, (Lock(), 0))
            self._locks[key] = (lock, count + 1)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._registry_lock:
                current_lock, current_count = self._locks[key]
                if current_count == 1:
                    del self._locks[key]
                else:
                    self._locks[key] = (current_lock, current_count - 1)


def normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _WHITESPACE.sub(" ", normalized).strip()


def _evidence_fingerprint(evidence: tuple[Evidence, ...]) -> str:
    chunk_fingerprints: list[dict[str, object]] = [
        {
            "chunk_id": item.chunk_id,
            "collection_version": item.collection_version,
            "content_hash": item.content_hash,
            "document_version": item.document_version,
            "rank": item.rank,
        }
        for item in evidence
    ]
    return _fingerprint(
        {
            "collections": sorted({item.collection_version for item in evidence}),
            "chunks": chunk_fingerprints,
        }
    )


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _qualified_route(output: RoutingModelOutput) -> bool:
    return (
        output.cache_eligibility == PublicRagCacheEligibility.PUBLIC_RAG
        and output.reason_category == RoutingReason.SINGLE_DOMAIN
        and len(output.selected_agent_ids) == 1
        and output.selected_agent_ids[0] in _ELIGIBLE_AGENTS
    )


def _operation_from_lookup(lookup: CacheLookupResult) -> CacheOperationResult:
    return CacheOperationResult(
        outcome=lookup.outcome,
        match_kind=lookup.match_kind,
        similarity=lookup.similarity,
        entry_age_seconds=lookup.entry_age_seconds,
        reason=lookup.reason,
    )


def _bypass(reason: str) -> CacheOperationResult:
    return CacheOperationResult(outcome=CacheLookupOutcome.BYPASS, reason=reason)


def _error(reason: str) -> CacheOperationResult:
    return CacheOperationResult(outcome=CacheLookupOutcome.ERROR, reason=reason)
