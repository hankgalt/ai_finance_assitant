"""Environment-owned response-cache composition."""

from __future__ import annotations

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.knowledge.representations import (
    DeterministicTestEncoder,
    FastEmbedEncoder,
    RepresentationEncoder,
)
from ai_finance_assistant.response_cache.adapters import (
    DisabledModelResponseCache,
    InMemoryModelResponseCache,
    UnavailableModelResponseCache,
)
from ai_finance_assistant.response_cache.ports import ModelResponseCache
from ai_finance_assistant.response_cache.redis_adapter import RedisVLModelResponseCache
from ai_finance_assistant.response_cache.service import ResponseCacheService


def response_cache_service_from_settings(
    settings: Settings,
    *,
    encoder: RepresentationEncoder | None = None,
) -> ResponseCacheService:
    selected_encoder: RepresentationEncoder
    adapter: ModelResponseCache
    if settings.response_cache_adapter == "disabled":
        selected_encoder = encoder or DeterministicTestEncoder(
            dimensions=settings.expected_dense_dimensions
        )
        adapter = DisabledModelResponseCache()
    else:
        try:
            selected_encoder = encoder or (
                DeterministicTestEncoder(dimensions=settings.expected_dense_dimensions)
                if settings.mode == "test"
                else FastEmbedEncoder()
            )
            if settings.response_cache_adapter == "in_memory":
                adapter = InMemoryModelResponseCache(
                    maximum_entries=settings.response_cache_memory_max_entries
                )
            else:
                adapter = RedisVLModelResponseCache(
                    redis_url=settings.response_cache_redis_url,
                    index_name=settings.response_cache_index_name,
                    encoder=selected_encoder,
                    ttl_seconds=settings.response_cache_ttl_seconds,
                    minimum_similarity=settings.response_cache_minimum_similarity,
                    timeout_seconds=settings.response_cache_lookup_timeout_milliseconds / 1_000,
                )
        except Exception:
            selected_encoder = encoder or DeterministicTestEncoder(
                dimensions=settings.expected_dense_dimensions
            )
            adapter = UnavailableModelResponseCache(
                adapter=settings.response_cache_adapter,
                detail=(
                    "The optional response cache is unavailable or incompatible; requests "
                    "will execute normally."
                ),
            )
    return ResponseCacheService(
        adapter=adapter,
        encoder=selected_encoder,
        policy_version=settings.response_cache_policy_version,
        schema_version=settings.response_cache_schema_version,
        ttl_seconds=settings.response_cache_ttl_seconds,
        minimum_semantic_similarity=settings.response_cache_minimum_similarity,
        semantic_mode=settings.response_cache_semantic_mode,
    )


def disabled_response_cache_service() -> ResponseCacheService:
    return ResponseCacheService(
        adapter=DisabledModelResponseCache(),
        encoder=DeterministicTestEncoder(),
        policy_version="public-rag-evidence-bound-v2",
        schema_version="1",
        ttl_seconds=86_400,
        minimum_semantic_similarity=0.92,
        semantic_mode="shadow",
    )
