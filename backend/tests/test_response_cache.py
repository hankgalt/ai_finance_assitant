from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import sleep

import pytest

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.knowledge.models import Evidence, SparseEmbedding
from ai_finance_assistant.llm.models import (
    ModelOutput,
    PublicRagCacheEligibility,
    RoutingModelOutput,
    RoutingReason,
)
from ai_finance_assistant.response_cache.adapters import (
    InMemoryModelResponseCache,
    UnavailableModelResponseCache,
)
from ai_finance_assistant.response_cache.models import (
    CacheLookupOutcome,
    CacheRecord,
    CacheWriteOutcome,
)
from ai_finance_assistant.response_cache.service import (
    GenerationCacheContext,
    ResponseCacheService,
    RouteCacheContext,
    normalize_query,
)


class MappingEncoder:
    dense_model_id = "mapping-encoder-v1"
    sparse_model_id = "unused"
    dense_model_revision = "mapping-revision-v1"
    dense_artifact_sha256 = "a" * 64
    sparse_model_revision = "unused"
    sparse_artifact_sha256 = "b" * 64
    dense_dimensions = 2

    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self._vectors = vectors or {}

    def embed_dense(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vectors.get(normalize_query(text), [1.0, 0.0]) for text in texts]

    def embed_sparse(self, texts: Sequence[str]) -> list[SparseEmbedding]:
        return [SparseEmbedding(indices=(1,), values=(1.0,)) for _ in texts]


def evidence(
    *,
    logical_name: str = "finance",
    content_hash: str = "c" * 64,
    tax_years: tuple[int, ...] = (),
) -> Evidence:
    return Evidence(
        chunk_id=f"{logical_name}-chunk",
        document_id=f"{logical_name}-document",
        title="Public education source",
        publisher="Authoritative Publisher",
        canonical_url="https://example.invalid/source",
        section_path="Overview",
        text="Bounded public education evidence.",
        score=0.98,
        rank=1,
        collection_name=f"{logical_name}_v1",
        collection_version="v1",
        document_version="document-v1",
        content_hash=content_hash,
        fetched_at=datetime(2026, 10, 31, 12, 0, tzinfo=UTC),
        tax_years=tax_years,
        jurisdiction="US-Federal",
    )


def cache_service(
    *,
    encoder: MappingEncoder | None = None,
    semantic_mode: str = "serving",
    minimum_similarity: float = 0.92,
    clock: object | None = None,
    adapter: InMemoryModelResponseCache | UnavailableModelResponseCache | None = None,
    policy_version: str = "test-policy-v1",
    schema_version: str = "1",
) -> ResponseCacheService:
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    return ResponseCacheService(
        adapter=adapter
        or InMemoryModelResponseCache(
            clock=clock if callable(clock) else lambda: datetime.now(UTC)
        ),
        encoder=encoder or MappingEncoder(),
        policy_version=policy_version,
        schema_version=schema_version,
        ttl_seconds=300,
        minimum_semantic_similarity=minimum_similarity,
        semantic_mode=semantic_mode,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def route_context(
    *,
    session_id: str = "session-a",
    message: str = "What is diversification?",
    workflow_version: str = "1",
    has_context_references: bool = False,
) -> RouteCacheContext:
    return RouteCacheContext(
        session_id=session_id,
        message=message,
        locale="en-US",
        jurisdiction="US",
        workflow_version=workflow_version,
        provider_id="openai",
        model_id="gpt-test",
        prompt_version="routing-v1",
        has_context_references=has_context_references,
    )


def generation_context(
    *,
    agent_id: AgentId = AgentId.FINANCE_QA,
    session_id: str = "session-a",
    message: str = "What is diversification?",
    item: Evidence | None = None,
    tax_year: int | None = None,
    public_rag_eligible: bool = True,
    has_context_references: bool = False,
) -> GenerationCacheContext:
    return GenerationCacheContext(
        session_id=session_id,
        agent_id=agent_id,
        message=message,
        locale="en-US",
        jurisdiction="US",
        workflow_version="1",
        provider_id="openai",
        model_id="gpt-test",
        prompt_version="generation-v1",
        instructions="Use only current evidence.",
        evidence=(item or evidence(),),
        tax_year=tax_year,
        public_rag_eligible=public_rag_eligible,
        has_context_references=has_context_references,
    )


@pytest.mark.parametrize("agent_id", [AgentId.FINANCE_QA, AgentId.TAX_EDUCATION])
def test_exact_route_cache_is_session_and_version_scoped(agent_id: AgentId) -> None:
    cache = cache_service()
    context = route_context(message=f"Public {agent_id.value} question")
    output = RoutingModelOutput(
        selected_agent_ids=(agent_id,),
        reason_category=RoutingReason.SINGLE_DOMAIN,
        cache_eligibility=PublicRagCacheEligibility.PUBLIC_RAG,
    )

    assert cache.store_route(context, output).outcome == CacheWriteOutcome.STORED
    hit = cache.lookup_route(context)

    assert hit.outcome == CacheLookupOutcome.HIT
    assert hit.payload is not None
    assert hit.payload["selected_agent_ids"] == [agent_id.value]
    assert (
        cache.lookup_route(context.model_copy(update={"session_id": "session-b"})).outcome
        == CacheLookupOutcome.MISS
    )
    assert (
        cache.lookup_route(context.model_copy(update={"workflow_version": "2"})).outcome
        == CacheLookupOutcome.MISS
    )


def test_route_cache_denies_context_and_non_public_routes() -> None:
    cache = cache_service()
    public = RoutingModelOutput(
        selected_agent_ids=(AgentId.FINANCE_QA,),
        reason_category=RoutingReason.SINGLE_DOMAIN,
        cache_eligibility=PublicRagCacheEligibility.PUBLIC_RAG,
    )
    private = public.model_copy(update={"cache_eligibility": PublicRagCacheEligibility.INELIGIBLE})

    assert cache.store_route(route_context(), private).outcome == CacheWriteOutcome.BYPASS
    assert (
        cache.store_route(route_context(has_context_references=True), public).outcome
        == CacheWriteOutcome.BYPASS
    )


def test_route_cache_denies_multi_agent_routes() -> None:
    cache = cache_service()
    output = RoutingModelOutput(
        selected_agent_ids=(AgentId.FINANCE_QA, AgentId.TAX_EDUCATION),
        reason_category=RoutingReason.MULTI_DOMAIN,
        cache_eligibility=PublicRagCacheEligibility.INELIGIBLE,
    )

    assert cache.store_route(route_context(), output).outcome == CacheWriteOutcome.BYPASS


def test_semantic_generation_requires_minimum_similarity_and_matching_evidence() -> None:
    original = "What is diversification?"
    paraphrase = "Explain how diversification works."
    near_miss = "How is a concentrated portfolio taxed?"
    encoder = MappingEncoder(
        {
            normalize_query(original): [1.0, 0.0],
            normalize_query(paraphrase): [0.96, 0.28],
            normalize_query(near_miss): [0.8, 0.6],
        }
    )
    cache = cache_service(encoder=encoder, minimum_similarity=0.92)
    output = ModelOutput(summary="Diversification spreads exposure across investments.")

    assert (
        cache.store_generation(generation_context(message=original), output).outcome
        == CacheWriteOutcome.STORED
    )
    semantic_hit = cache.lookup_generation(generation_context(message=paraphrase))
    below_cutoff = cache.lookup_generation(generation_context(message=near_miss))
    changed_evidence = cache.lookup_generation(
        generation_context(
            message=paraphrase,
            item=evidence(content_hash="d" * 64),
        )
    )

    assert semantic_hit.outcome == CacheLookupOutcome.HIT
    assert semantic_hit.similarity == pytest.approx(0.96, abs=0.01)
    assert below_cutoff.outcome == CacheLookupOutcome.MISS
    assert below_cutoff.reason == "below_minimum_similarity"
    assert changed_evidence.outcome == CacheLookupOutcome.MISS


def test_tax_semantic_generation_requires_same_year_and_current_tax_evidence() -> None:
    original = "How are pension and annuity payments taxed in 2025?"
    paraphrase = "How are pension or annuity payments taxed for 2025?"
    cache = cache_service(
        encoder=MappingEncoder(
            {
                normalize_query(original): [1.0, 0.0],
                normalize_query(paraphrase): [0.99, 0.1],
            }
        )
    )
    tax_evidence = evidence(logical_name="tax", tax_years=(2025,))
    original_context = generation_context(
        agent_id=AgentId.TAX_EDUCATION,
        message=original,
        item=tax_evidence,
        tax_year=2025,
    )
    cache.store_generation(original_context, ModelOutput(summary="Year-specific tax education."))

    hit = cache.lookup_generation(original_context.model_copy(update={"message": paraphrase}))
    changed_year = cache.lookup_generation(
        original_context.model_copy(update={"message": paraphrase, "tax_year": 2026})
    )

    assert hit.outcome == CacheLookupOutcome.HIT
    assert hit.match_kind is not None and hit.match_kind.value == "semantic"
    assert changed_year.outcome == CacheLookupOutcome.MISS


def test_semantic_shadow_mode_never_serves_a_candidate() -> None:
    original = "What is an ETF?"
    paraphrase = "Explain exchange traded funds."
    cache = cache_service(
        encoder=MappingEncoder(
            {
                normalize_query(original): [1.0, 0.0],
                normalize_query(paraphrase): [0.99, 0.1],
            }
        ),
        semantic_mode="shadow",
    )
    cache.store_generation(
        generation_context(message=original),
        ModelOutput(summary="An ETF is a pooled investment vehicle."),
    )

    result = cache.lookup_generation(generation_context(message=paraphrase))

    assert result.outcome == CacheLookupOutcome.SHADOW_HIT
    assert result.payload is None
    assert result.reason == "semantic_shadow_mode"


def test_tax_generation_is_partitioned_by_tax_year_and_jurisdiction() -> None:
    cache = cache_service()
    tax_evidence = evidence(logical_name="tax", tax_years=(2025,))
    context = generation_context(
        agent_id=AgentId.TAX_EDUCATION,
        item=tax_evidence,
        tax_year=2025,
    )
    cache.store_generation(context, ModelOutput(summary="Year-specific tax education."))

    assert cache.lookup_generation(context).outcome == CacheLookupOutcome.HIT
    assert (
        cache.lookup_generation(context.model_copy(update={"tax_year": 2026})).outcome
        == CacheLookupOutcome.MISS
    )
    assert (
        cache.lookup_generation(context.model_copy(update={"jurisdiction": "CA"})).outcome
        == CacheLookupOutcome.BYPASS
    )


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"public_rag_eligible": False}, "route_not_public_rag"),
        ({"has_context_references": True}, "context_bearing_request"),
        ({"checkpoint_dependent": True}, "checkpoint_dependent_request"),
        ({"agent_id": AgentId.PORTFOLIO_ANALYSIS}, "agent_ineligible"),
        ({"agent_id": AgentId.MARKET_ANALYSIS}, "agent_ineligible"),
        ({"agent_id": AgentId.NEWS_SYNTHESIZER}, "agent_ineligible"),
        ({"agent_id": AgentId.GOAL_PLANNING}, "agent_ineligible"),
    ],
)
def test_generation_cache_is_deny_by_default(
    updates: dict[str, object],
    reason: str,
) -> None:
    result = cache_service().lookup_generation(generation_context().model_copy(update=updates))

    assert result.outcome == CacheLookupOutcome.BYPASS
    assert result.reason == reason


def test_session_purge_and_expiry_remove_entries() -> None:
    now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)

    class Clock:
        value = now

        def __call__(self) -> datetime:
            return self.value

    clock = Clock()
    cache = cache_service(clock=clock)
    context = generation_context()
    cache.store_generation(context, ModelOutput(summary="Cached response."))
    assert cache.lookup_generation(context).outcome == CacheLookupOutcome.HIT

    assert cache.purge_session("session-a") == 1
    assert cache.lookup_generation(context).outcome == CacheLookupOutcome.MISS

    cache.store_generation(context, ModelOutput(summary="Cached response."))
    clock.value = now + timedelta(minutes=6)
    assert cache.lookup_generation(context).outcome == CacheLookupOutcome.MISS


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("locale", "es-US"),
        ("jurisdiction", "US-Federal"),
        ("workflow_version", "2"),
        ("provider_id", "other-provider"),
        ("model_id", "other-model"),
        ("prompt_version", "generation-v2"),
        ("instructions", "Use current evidence with a revised policy."),
    ],
)
def test_generation_cache_invalidates_every_request_version_filter(
    field: str,
    changed: object,
) -> None:
    cache = cache_service()
    context = generation_context()
    cache.store_generation(context, ModelOutput(summary="Cached response."))

    assert (
        cache.lookup_generation(context.model_copy(update={field: changed})).outcome
        == CacheLookupOutcome.MISS
    )


def test_generation_cache_invalidates_policy_schema_and_encoder_versions() -> None:
    adapter = InMemoryModelResponseCache()
    context = generation_context()
    first = cache_service(adapter=adapter)
    first.store_generation(context, ModelOutput(summary="Cached response."))

    assert (
        cache_service(adapter=adapter, policy_version="test-policy-v2")
        .lookup_generation(context)
        .outcome
        == CacheLookupOutcome.MISS
    )
    assert (
        cache_service(adapter=adapter, schema_version="2").lookup_generation(context).outcome
        == CacheLookupOutcome.MISS
    )
    changed_encoder = MappingEncoder()
    changed_encoder.dense_model_revision = "mapping-revision-v2"
    assert (
        cache_service(adapter=adapter, encoder=changed_encoder).lookup_generation(context).outcome
        == CacheLookupOutcome.MISS
    )


class RecordingAdapter(InMemoryModelResponseCache):
    last_record: CacheRecord | None = None

    def store(self, record: CacheRecord) -> None:
        self.last_record = record
        super().store(record)


def test_stored_record_uses_opaque_scope_and_excludes_private_context() -> None:
    adapter = RecordingAdapter()
    cache = cache_service(adapter=adapter)
    context = generation_context(session_id="raw-session-identifier")

    cache.store_generation(context, ModelOutput(summary="Cached response."))

    assert adapter.last_record is not None
    serialized = adapter.last_record.model_dump_json()
    assert "raw-session-identifier" not in serialized
    assert "Use only current evidence." not in serialized
    assert adapter.last_record.session_scope != context.session_id


def test_malformed_entry_and_unavailable_adapter_fail_open() -> None:
    adapter = RecordingAdapter()
    cache = cache_service(adapter=adapter)
    context = generation_context()
    cache.store_generation(context, ModelOutput(summary="Cached response."))
    assert adapter.last_record is not None
    adapter.store(adapter.last_record.model_copy(update={"payload_json": "not-json"}))

    malformed = cache.lookup_generation(context)
    unavailable = cache_service(
        adapter=UnavailableModelResponseCache(
            adapter="redisvl",
            detail="Redis is unavailable for this test.",
        )
    )

    assert malformed.outcome == CacheLookupOutcome.ERROR
    assert malformed.reason == "cached_schema_invalid"
    assert unavailable.lookup_generation(context).outcome == CacheLookupOutcome.ERROR
    assert (
        unavailable.store_generation(context, ModelOutput(summary="Normal result.")).outcome
        == CacheWriteOutcome.ERROR
    )


def test_generation_guard_coalesces_same_session_identical_misses() -> None:
    cache = cache_service()
    context = generation_context()
    model_calls = 0
    count_lock = Lock()

    def execute() -> CacheLookupOutcome:
        nonlocal model_calls
        with cache.generation_guard(context):
            lookup = cache.lookup_generation(context)
            if lookup.outcome == CacheLookupOutcome.HIT:
                return lookup.outcome
            with count_lock:
                model_calls += 1
            sleep(0.03)
            cache.store_generation(context, ModelOutput(summary="Coalesced response."))
            return CacheLookupOutcome.MISS

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(lambda _: execute(), range(2)))

    assert model_calls == 1
    assert set(outcomes) == {CacheLookupOutcome.MISS, CacheLookupOutcome.HIT}
