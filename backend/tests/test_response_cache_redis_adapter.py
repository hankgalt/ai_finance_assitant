"""Deterministic RedisVLModelResponseCache behavior with in-memory Redis and RedisVL fakes.

The opt-in ``test_response_cache_redis.py`` test remains the authority for real Redis Search
behavior. These fakes reproduce only the calls the adapter makes so its route expiry, schema
recovery, scope filtering, similarity mapping, purge, and readiness logic run in CI.
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import pytest

from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.response_cache import redis_adapter
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheLookupRequest,
    CacheMatchKind,
    CacheRecord,
    CacheRecordKind,
)
from ai_finance_assistant.response_cache.redis_adapter import RedisVLModelResponseCache

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
SCOPE = "a" * 64
OTHER_SCOPE = "c" * 64
FINGERPRINT = "b" * 64


class _FakeRedis:
    instances: ClassVar[list[_FakeRedis]] = []

    def __init__(self, url: str, options: dict[str, Any]) -> None:
        self.url = url
        self.options = options
        self.values: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.ping_error = False
        self.closed = False

    @classmethod
    def from_url(cls, url: str, **options: Any) -> _FakeRedis:
        instance = cls(url, options)
        cls.instances.append(instance)
        return instance

    def ping(self) -> bool:
        if self.ping_error:
            raise ConnectionError("redis unavailable")
        return True

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value.encode()
        self.ttls[key] = ttl

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    def unlink(self, *keys: str | bytes) -> int:
        removed = 0
        for key in keys:
            name = key.decode() if isinstance(key, bytes) else key
            removed += int(self.values.pop(name, None) is not None)
        return removed

    def scan_iter(self, *, match: str, count: int) -> list[bytes]:
        assert count == 100
        return [key.encode() for key in self.values if fnmatch.fnmatchcase(key, match)]

    def close(self) -> None:
        self.closed = True


@dataclass
class _DropResult:
    processed: int


@dataclass
class _Entry:
    prompt: str
    response: str
    vector: list[float]
    filters: dict[str, str]
    inserted_at: float


@dataclass
class _FakeIndex:
    entries: list[_Entry]
    drops: list[tuple[str, bool]] = field(default_factory=list)

    def drop_by_filter(
        self, expression: Any, *, batch_size: int, allow_all: bool = False
    ) -> _DropResult:
        assert batch_size == 100
        text = str(expression)
        self.drops.append((text, allow_all))
        kept = [entry for entry in self.entries if not (allow_all or _matches(entry, text))]
        processed = len(self.entries) - len(kept)
        self.entries[:] = kept
        return _DropResult(processed)


class _FakeSemanticCache:
    instances: ClassVar[list[_FakeSemanticCache]] = []

    def __init__(self, **options: Any) -> None:
        self.options = options
        self.entries: list[_Entry] = []
        self.index = _FakeIndex(self.entries)
        self.disconnected = False
        self.raw_hit_override: dict[str, Any] | None = None
        _FakeSemanticCache.instances.append(self)

    def store(
        self,
        *,
        prompt: str,
        response: str,
        vector: list[float],
        filters: dict[str, str],
        ttl: int,
    ) -> None:
        assert ttl == self.options["ttl"]
        self.entries.append(_Entry(prompt, response, vector, filters, NOW.timestamp()))

    def check(
        self,
        *,
        vector: list[float],
        num_results: int,
        filter_expression: Any,
        distance_threshold: float,
    ) -> list[dict[str, Any]]:
        assert num_results == 1
        if self.raw_hit_override is not None:
            return [self.raw_hit_override]
        text = str(filter_expression)
        for entry in self.entries:
            distance = 1.0 - _cosine(entry.vector, vector)
            if _matches(entry, text) and distance <= distance_threshold + 1e-9:
                return [
                    {
                        "prompt": entry.prompt.encode(),
                        "response": entry.response,
                        "inserted_at": str(entry.inserted_at),
                        "vector_distance": str(distance),
                    }
                ]
        return []

    def disconnect(self) -> None:
        self.disconnected = True


def _matches(entry: _Entry, filter_text: str) -> bool:
    return all(
        f"@{name}:{{{value}}}" in filter_text
        for name, value in entry.filters.items()
        if f"@{name}:" in filter_text
    )


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> RedisVLModelResponseCache:
    _FakeRedis.instances.clear()
    _FakeSemanticCache.instances.clear()
    monkeypatch.setattr(redis_adapter, "Redis", _FakeRedis)
    monkeypatch.setattr(redis_adapter, "SemanticCache", _FakeSemanticCache)
    return RedisVLModelResponseCache(
        redis_url="redis://127.0.0.1:6379/0",
        index_name="aifa_unit_cache",
        encoder=DeterministicTestEncoder(),
        ttl_seconds=300,
        minimum_similarity=0.8,
        timeout_seconds=1.5,
    )


def _vector(text: str) -> tuple[float, ...]:
    return tuple(DeterministicTestEncoder().embed_dense([text])[0])


def _route(
    scope: str = SCOPE, query: str = "what is an etf?", *, expires: timedelta = timedelta(minutes=5)
) -> CacheRecord:
    return CacheRecord(
        kind=CacheRecordKind.ROUTE,
        session_scope=scope,
        normalized_query=query,
        filter_fingerprint=FINGERPRINT,
        payload_json='{"selected_agent_ids":["finance_qa"]}',
        created_at=NOW - timedelta(seconds=30),
        expires_at=NOW - timedelta(seconds=30) + expires,
    )


def _route_lookup(scope: str = SCOPE, query: str = "what is an etf?") -> CacheLookupRequest:
    return CacheLookupRequest(
        kind=CacheRecordKind.ROUTE,
        session_scope=scope,
        normalized_query=query,
        filter_fingerprint=FINGERPRINT,
        observed_at=NOW,
    )


def _generation(scope: str = SCOPE, query: str = "what is an etf?") -> CacheRecord:
    return CacheRecord(
        kind=CacheRecordKind.GENERATION,
        session_scope=scope,
        normalized_query=query,
        filter_fingerprint=FINGERPRINT,
        payload_json='{"schema_version":"1","summary":"Public answer.","warnings":[]}',
        vector=_vector(query),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def _generation_lookup(
    query: str, *, scope: str = SCOPE, allow_semantic: bool = True, vector_text: str | None = None
) -> CacheLookupRequest:
    return CacheLookupRequest(
        kind=CacheRecordKind.GENERATION,
        session_scope=scope,
        normalized_query=query,
        filter_fingerprint=FINGERPRINT,
        vector=_vector(vector_text or query),
        allow_semantic=allow_semantic,
        minimum_similarity=0.8,
        observed_at=NOW + timedelta(seconds=10),
    )


def test_construction_configures_bounded_redis_and_filtered_semantic_index(
    adapter: RedisVLModelResponseCache,
) -> None:
    client = _FakeRedis.instances[0]
    semantic = _FakeSemanticCache.instances[0]

    assert client.options["socket_timeout"] == 1.5
    assert client.options["decode_responses"] is False
    assert semantic.options["distance_threshold"] == pytest.approx(0.2)
    assert semantic.options["ttl"] == 300
    assert {item["name"] for item in semantic.options["filterable_fields"]} == {
        "session_scope",
        "record_kind",
        "filter_fingerprint",
    }
    vectorizer = semantic.options["vectorizer"]
    assert vectorizer.embed("etf") == list(_vector("etf"))
    assert vectorizer.embed_many(["etf", "bond"]) == [list(_vector("etf")), list(_vector("bond"))]


@pytest.mark.parametrize("ttl", [0, 86_401])
def test_construction_rejects_unbounded_ttl(monkeypatch: pytest.MonkeyPatch, ttl: int) -> None:
    monkeypatch.setattr(redis_adapter, "Redis", _FakeRedis)
    monkeypatch.setattr(redis_adapter, "SemanticCache", _FakeSemanticCache)
    with pytest.raises(ValueError, match="between 1 second and 24 hours"):
        RedisVLModelResponseCache(
            redis_url="redis://127.0.0.1:6379/0",
            index_name="aifa_unit_cache",
            encoder=DeterministicTestEncoder(),
            ttl_seconds=ttl,
            minimum_similarity=0.8,
            timeout_seconds=1.0,
        )


def test_route_records_are_exact_scoped_and_ttl_bounded(adapter: RedisVLModelResponseCache) -> None:
    client = _FakeRedis.instances[0]
    adapter.store(_route())

    hit = adapter.lookup(_route_lookup())
    other_scope = adapter.lookup(_route_lookup(scope=OTHER_SCOPE))
    other_query = adapter.lookup(_route_lookup(query="what is a bond?"))

    assert hit.outcome == CacheLookupOutcome.HIT
    assert hit.match_kind == CacheMatchKind.EXACT
    assert hit.entry_age_seconds == pytest.approx(30.0)
    assert hit.record == _route()
    assert (other_scope.outcome, other_scope.reason) == (CacheLookupOutcome.MISS, "no_exact_match")
    assert other_query.outcome == CacheLookupOutcome.MISS
    assert list(client.ttls.values()) == [300]
    assert all(key.startswith(f"aifa_unit_cache:route:{SCOPE}:") for key in client.values)


def test_expired_and_invalid_route_records_are_removed(adapter: RedisVLModelResponseCache) -> None:
    client = _FakeRedis.instances[0]
    adapter.store(_route(expires=timedelta(seconds=10)))

    expired = adapter.lookup(_route_lookup())

    assert (expired.outcome, expired.reason) == (CacheLookupOutcome.MISS, "expired")
    assert client.values == {}

    adapter.store(_route())
    key = next(iter(client.values))
    client.values[key] = b'{"schema_version":"2"}'
    invalid = adapter.lookup(_route_lookup())

    assert (invalid.outcome, invalid.reason) == (CacheLookupOutcome.ERROR, "cached_schema_invalid")
    assert client.values == {}


def test_generation_reuse_distinguishes_exact_semantic_and_scope(
    adapter: RedisVLModelResponseCache,
) -> None:
    adapter.store(_generation())

    exact = adapter.lookup(_generation_lookup("what is an etf?"))
    semantic = adapter.lookup(_generation_lookup("what's an etf", vector_text="what is an etf?"))
    exact_only = adapter.lookup(
        _generation_lookup("explain index fund costs", allow_semantic=False)
    )
    cross_session = adapter.lookup(_generation_lookup("what is an etf?", scope=OTHER_SCOPE))

    assert exact.outcome == CacheLookupOutcome.HIT
    assert exact.match_kind == CacheMatchKind.EXACT
    assert exact.similarity == pytest.approx(1.0)
    assert exact.entry_age_seconds == pytest.approx(10.0)
    assert exact.record is not None
    assert exact.record.expires_at == NOW + timedelta(seconds=300)
    assert semantic.outcome == CacheLookupOutcome.HIT
    assert semantic.match_kind == CacheMatchKind.SEMANTIC
    assert semantic.record is not None
    assert semantic.record.normalized_query == "what is an etf?"
    assert (exact_only.outcome, exact_only.reason) == (CacheLookupOutcome.MISS, "no_candidate")
    assert cross_session.outcome == CacheLookupOutcome.MISS


def test_generation_lookup_rejects_malformed_redisvl_text(
    adapter: RedisVLModelResponseCache,
) -> None:
    _FakeSemanticCache.instances[0].raw_hit_override = {
        "prompt": 7,
        "response": "{}",
        "inserted_at": str(NOW.timestamp()),
    }

    with pytest.raises(ValueError, match="malformed text field"):
        adapter.lookup(_generation_lookup("what is an etf?"))


def test_purge_session_removes_only_that_scope(adapter: RedisVLModelResponseCache) -> None:
    client = _FakeRedis.instances[0]
    adapter.store(_route())
    adapter.store(_route(scope=OTHER_SCOPE))
    adapter.store(_generation())
    adapter.store(_generation(scope=OTHER_SCOPE))

    assert adapter.purge_session(SCOPE) == 2
    assert adapter.purge_session(SCOPE) == 0
    assert all(OTHER_SCOPE in key for key in client.values)
    assert adapter.lookup(_generation_lookup("what is an etf?", scope=OTHER_SCOPE)).outcome == (
        CacheLookupOutcome.HIT
    )


def test_purge_all_removes_every_route_and_generation(adapter: RedisVLModelResponseCache) -> None:
    client = _FakeRedis.instances[0]
    semantic = _FakeSemanticCache.instances[0]
    adapter.store(_route())
    adapter.store(_route(scope=OTHER_SCOPE))
    adapter.store(_generation())

    assert adapter.purge_all() == 3
    assert client.values == {}
    assert semantic.index.drops[-1] == ("*", True)
    assert adapter.purge_all() == 0


def test_readiness_reports_availability_and_close_releases_connections(
    adapter: RedisVLModelResponseCache,
) -> None:
    client = _FakeRedis.instances[0]

    ready = adapter.readiness()
    client.ping_error = True
    unavailable = adapter.readiness()
    adapter.close()

    assert (ready.configured, ready.available, ready.adapter) == (True, True, "redisvl")
    assert "is ready" in ready.detail
    assert unavailable.available is False
    assert "unavailable" in unavailable.detail
    assert client.closed is True
    assert _FakeSemanticCache.instances[0].disconnected is True
