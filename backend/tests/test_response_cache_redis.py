from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheLookupRequest,
    CacheRecord,
    CacheRecordKind,
)
from ai_finance_assistant.response_cache.redis_adapter import RedisVLModelResponseCache

pytestmark = pytest.mark.redis


def test_real_redisvl_adapter_enforces_scope_filters_and_purge() -> None:
    redis_url = os.environ.get("AIFA_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("set AIFA_TEST_REDIS_URL for the opt-in Redis integration test")
    adapter = RedisVLModelResponseCache(
        redis_url=redis_url,
        index_name=f"aifa_test_cache_{uuid4().hex}",
        encoder=DeterministicTestEncoder(),
        ttl_seconds=300,
        minimum_similarity=0.8,
        timeout_seconds=1.0,
    )
    now = datetime.now(UTC)
    vector = tuple(DeterministicTestEncoder().embed_dense(["What is an ETF?"])[0])
    record = CacheRecord(
        kind=CacheRecordKind.GENERATION,
        session_scope="a" * 64,
        normalized_query="what is an etf?",
        filter_fingerprint="b" * 64,
        payload_json='{"schema_version":"1","summary":"Public answer.","warnings":[]}',
        vector=vector,
        created_at=now,
        expires_at=now.replace(year=now.year + 1),
    )
    try:
        adapter.store(record)
        hit = adapter.lookup(
            CacheLookupRequest(
                kind=CacheRecordKind.GENERATION,
                session_scope="a" * 64,
                normalized_query="what is an etf?",
                filter_fingerprint="b" * 64,
                vector=vector,
                allow_semantic=True,
                minimum_similarity=0.8,
                observed_at=now,
            )
        )
        cross_session = adapter.lookup(
            CacheLookupRequest(
                kind=CacheRecordKind.GENERATION,
                session_scope="c" * 64,
                normalized_query="what is an etf?",
                filter_fingerprint="b" * 64,
                vector=vector,
                allow_semantic=True,
                minimum_similarity=0.8,
                observed_at=now,
            )
        )

        assert hit.outcome == CacheLookupOutcome.HIT
        assert cross_session.outcome == CacheLookupOutcome.MISS
        assert adapter.purge_session("a" * 64) == 1
    finally:
        adapter.purge_all()
        adapter.close()
