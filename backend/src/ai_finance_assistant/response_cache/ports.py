"""Application-owned model response-cache port."""

from typing import Protocol

from ai_finance_assistant.response_cache.models import (
    CacheLookupRequest,
    CacheLookupResult,
    CacheReadiness,
    CacheRecord,
)


class ModelResponseCache(Protocol):
    """Store and retrieve minimized structured model outputs only."""

    def lookup(self, request: CacheLookupRequest) -> CacheLookupResult: ...

    def store(self, record: CacheRecord) -> None: ...

    def purge_session(self, session_scope: str) -> int: ...

    def purge_all(self) -> int: ...

    def readiness(self) -> CacheReadiness: ...

    def close(self) -> None: ...
