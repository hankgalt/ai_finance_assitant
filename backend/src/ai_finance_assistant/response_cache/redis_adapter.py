"""Redis 8/RedisVL adapter for the private-demo response cache."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from redis import Redis
from redisvl.extensions.cache.llm import SemanticCache
from redisvl.query.filter import Tag
from redisvl.utils.vectorize import CustomVectorizer

from ai_finance_assistant.knowledge.representations import RepresentationEncoder
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheLookupRequest,
    CacheLookupResult,
    CacheMatchKind,
    CacheReadiness,
    CacheRecord,
    CacheRecordKind,
    entry_age,
)


class _DropByFilterResult(Protocol):
    processed: int


class RedisVLModelResponseCache:
    """Exact route reuse plus filtered semantic generation reuse in Redis."""

    def __init__(
        self,
        *,
        redis_url: str,
        index_name: str,
        encoder: RepresentationEncoder,
        ttl_seconds: int,
        minimum_similarity: float,
        timeout_seconds: float,
    ) -> None:
        if ttl_seconds < 1 or ttl_seconds > 86_400:
            raise ValueError("response-cache TTL must be between 1 second and 24 hours")
        self._ttl_seconds = ttl_seconds
        self._index_name = index_name
        self._route_prefix = f"{index_name}:route"
        self._client: Redis = Redis.from_url(
            redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            health_check_interval=30,
            decode_responses=False,
        )
        self._client.ping()

        def embed(text: str, **_: object) -> list[float]:
            return [float(value) for value in encoder.embed_dense([text])[0]]

        def embed_many(texts: list[str], **_: object) -> list[list[float]]:
            return [[float(value) for value in vector] for vector in encoder.embed_dense(texts)]

        vectorizer = CustomVectorizer(embed=embed, embed_many=embed_many)
        self._semantic = SemanticCache(
            name=index_name,
            distance_threshold=1.0 - minimum_similarity,
            ttl=ttl_seconds,
            vectorizer=vectorizer,
            filterable_fields=[
                {"name": "session_scope", "type": "tag"},
                {"name": "record_kind", "type": "tag"},
                {"name": "filter_fingerprint", "type": "tag"},
            ],
            redis_client=self._client,
            create_index=True,
        )

    def lookup(self, request: CacheLookupRequest) -> CacheLookupResult:
        if request.kind == CacheRecordKind.ROUTE:
            return self._lookup_route(request)
        hits = self._semantic.check(
            vector=list(request.vector),
            num_results=1,
            filter_expression=cast(
                Any,
                (Tag("session_scope") == request.session_scope)
                & (Tag("record_kind") == request.kind.value)
                & (Tag("filter_fingerprint") == request.filter_fingerprint),
            ),
            distance_threshold=(
                1.0 - request.minimum_similarity if request.allow_semantic else 0.0
            ),
        )
        if not hits:
            return CacheLookupResult(outcome=CacheLookupOutcome.MISS, reason="no_candidate")
        hit = hits[0]
        prompt = _text(hit.get("prompt"))
        payload = _text(hit.get("response"))
        inserted_at = datetime.fromtimestamp(float(hit["inserted_at"]), tz=UTC)
        distance = float(hit.get("vector_distance", 0.0))
        similarity = max(-1.0, min(1.0, 1.0 - distance))
        match_kind = (
            CacheMatchKind.EXACT if prompt == request.normalized_query else CacheMatchKind.SEMANTIC
        )
        record = CacheRecord(
            kind=request.kind,
            session_scope=request.session_scope,
            normalized_query=prompt,
            filter_fingerprint=request.filter_fingerprint,
            payload_json=payload,
            vector=request.vector,
            created_at=inserted_at,
            expires_at=inserted_at + timedelta(seconds=self._ttl_seconds),
        )
        return CacheLookupResult(
            outcome=CacheLookupOutcome.HIT,
            record=record,
            match_kind=match_kind,
            similarity=similarity,
            entry_age_seconds=entry_age(record, request.observed_at),
        )

    def store(self, record: CacheRecord) -> None:
        if record.kind == CacheRecordKind.ROUTE:
            self._client.setex(
                self._route_key(record),
                self._ttl_seconds,
                record.model_dump_json(),
            )
            return
        self._semantic.store(
            prompt=record.normalized_query,
            response=record.payload_json,
            vector=list(record.vector),
            filters={
                "session_scope": record.session_scope,
                "record_kind": record.kind.value,
                "filter_fingerprint": record.filter_fingerprint,
            },
            ttl=self._ttl_seconds,
        )

    def purge_session(self, session_scope: str) -> int:
        raw_route_keys = list(
            cast(
                Any,
                self._client.scan_iter(
                    match=f"{self._route_prefix}:{session_scope}:*",
                    count=100,
                ),
            )
        )
        route_keys = tuple(key for key in raw_route_keys if isinstance(key, (str, bytes)))
        route_count = int(self._client.unlink(*route_keys)) if route_keys else 0
        result = cast(
            _DropByFilterResult,
            self._semantic.index.drop_by_filter(
                cast(Any, Tag("session_scope") == session_scope),
                batch_size=100,
            ),
        )
        return route_count + int(result.processed)

    def purge_all(self) -> int:
        raw_route_keys = list(
            cast(
                Any,
                self._client.scan_iter(match=f"{self._route_prefix}:*", count=100),
            )
        )
        route_keys = tuple(key for key in raw_route_keys if isinstance(key, (str, bytes)))
        route_count = int(self._client.unlink(*route_keys)) if route_keys else 0
        result = cast(
            _DropByFilterResult,
            self._semantic.index.drop_by_filter(
                "*",
                batch_size=100,
                allow_all=True,
            ),
        )
        return route_count + int(result.processed)

    def readiness(self) -> CacheReadiness:
        try:
            ready = bool(self._client.ping())
        except Exception:
            ready = False
        return CacheReadiness(
            configured=True,
            available=ready,
            adapter="redisvl",
            detail=(
                "The optional loopback Redis response cache is ready."
                if ready
                else "The optional loopback Redis response cache is unavailable."
            ),
        )

    def close(self) -> None:
        self._semantic.disconnect()
        self._client.close()

    def _lookup_route(self, request: CacheLookupRequest) -> CacheLookupResult:
        raw = self._client.get(self._route_lookup_key(request))
        if raw is None:
            return CacheLookupResult(outcome=CacheLookupOutcome.MISS, reason="no_exact_match")
        try:
            record = CacheRecord.model_validate_json(raw)
        except Exception:
            self._client.unlink(self._route_lookup_key(request))
            return CacheLookupResult(
                outcome=CacheLookupOutcome.ERROR,
                reason="cached_schema_invalid",
            )
        if record.expires_at <= request.observed_at:
            self._client.unlink(self._route_lookup_key(request))
            return CacheLookupResult(outcome=CacheLookupOutcome.MISS, reason="expired")
        return CacheLookupResult(
            outcome=CacheLookupOutcome.HIT,
            record=record,
            match_kind=CacheMatchKind.EXACT,
            entry_age_seconds=entry_age(record, request.observed_at),
        )

    def _route_key(self, record: CacheRecord) -> str:
        suffix = hashlib.sha256(
            f"{record.filter_fingerprint}\0{record.normalized_query}".encode()
        ).hexdigest()
        return f"{self._route_prefix}:{record.session_scope}:{suffix}"

    def _route_lookup_key(self, request: CacheLookupRequest) -> str:
        suffix = hashlib.sha256(
            f"{request.filter_fingerprint}\0{request.normalized_query}".encode()
        ).hexdigest()
        return f"{self._route_prefix}:{request.session_scope}:{suffix}"


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise ValueError("RedisVL cache returned a malformed text field")
