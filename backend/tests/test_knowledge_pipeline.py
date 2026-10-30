from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_finance_assistant.knowledge.cli import _load_qrels, _next_run_path
from ai_finance_assistant.knowledge.evaluation import evaluate_candidate
from ai_finance_assistant.knowledge.ingestion import OfflineIngestionService, document_versions
from ai_finance_assistant.knowledge.memory_store import InMemoryKnowledgeStore
from ai_finance_assistant.knowledge.models import (
    ChunkingPolicy,
    EvaluationCase,
    LogicalKnowledgeBase,
    PermittedUse,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalStrategy,
    SourceDefinition,
    SourceRegistry,
    SourceStatus,
    SourceType,
)
from ai_finance_assistant.knowledge.registry import (
    CachedSourceFetcher,
    FixtureSourceFetcher,
    load_source_registry,
)
from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever

REVIEWED_AT = datetime(2026, 10, 27, tzinfo=UTC)


def _source(
    source_id: str,
    *,
    kb: LogicalKnowledgeBase = LogicalKnowledgeBase.FINANCE,
    title: str = "Compound Interest",
    tax_years: tuple[int, ...] = (),
    status: SourceStatus = SourceStatus.APPROVED,
    enabled: bool = True,
) -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        logical_kb=kb,
        title=title,
        publisher="Example Federal Agency",
        canonical_url=f"https://example.gov/{source_id}",
        source_type=SourceType.HTML,
        jurisdiction="US-Federal",
        tax_years=tax_years,
        status=status,
        permitted_use=PermittedUse(
            basis="United States government work; source review recorded.",
            reviewer="repository-owner",
            ai_processing_allowed=True,
            redistribution_allowed=True,
            attribution_required=True,
            restrictions=("Do not imply agency endorsement.",),
            reviewed_at=REVIEWED_AT,
        ),
        ingestion_enabled=enabled,
    )


def _registry(*sources: SourceDefinition) -> SourceRegistry:
    return SourceRegistry(reviewed_at=REVIEWED_AT, sources=sources)


def _html(*paragraphs: str) -> bytes:
    content = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return (
        "<html><head><title>Ignored</title><script>secret()</script></head>"
        f"<body><nav>menu</nav><main><h1>Learning</h1>{content}</main></body></html>"
    ).encode()


def _service(
    registry: SourceRegistry, bodies: dict[str, bytes]
) -> tuple[OfflineIngestionService, InMemoryKnowledgeStore, DeterministicTestEncoder]:
    del registry
    store = InMemoryKnowledgeStore()
    encoder = DeterministicTestEncoder()
    return (
        OfflineIngestionService(
            fetcher=FixtureSourceFetcher(bodies),
            encoder=encoder,
            store=store,
            chunking_policy=ChunkingPolicy(max_chars=400, overlap_chars=40, min_chars=20),
        ),
        store,
        encoder,
    )


def test_registry_rejects_unreviewed_enabled_source() -> None:
    with pytest.raises(ValidationError, match="only approved sources"):
        _source("pending", status=SourceStatus.PENDING_REVIEW)


def test_governed_tax_registry_includes_publication_560_for_sep_education() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "data" / "knowledge"
    registry = load_source_registry(data_dir / "source_registry.v1.json")
    source = next(item for item in registry.sources if item.source_id == "irs-p560-2025")
    qrels = _load_qrels(data_dir / "qrels.tax.v1.json")
    sep_case = next(item for item in qrels if item.case_id == "tax-2025-sep-ira")

    assert source.status == SourceStatus.APPROVED
    assert source.ingestion_enabled is True
    assert source.tax_years == (2025,)
    assert source.jurisdiction == "US-Federal"
    assert source.permitted_use.ai_processing_allowed is True
    assert source.permitted_use.redistribution_allowed is True
    assert sep_case.expected_document_ids == (source.source_id,)
    assert sep_case.filters.tax_year == 2025
    assert sep_case.filters.jurisdiction == "US-Federal"


def test_governed_finance_registry_covers_mutual_fund_and_etf_comparison() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "data" / "knowledge"
    registry = load_source_registry(data_dir / "source_registry.v1.json")
    source = next(
        item
        for item in registry.sources
        if item.source_id == "investor-mutual-fund-etf-characteristics"
    )
    qrels = _load_qrels(data_dir / "qrels.finance.v1.json")
    comparison_case = next(item for item in qrels if item.case_id == "finance-mutual-funds-vs-etfs")

    assert source.status == SourceStatus.APPROVED
    assert source.ingestion_enabled is True
    assert source.jurisdiction == "US-Federal"
    assert source.permitted_use.ai_processing_allowed is True
    assert source.permitted_use.redistribution_allowed is True
    assert comparison_case.expected_document_ids == (source.source_id,)
    assert comparison_case.filters.jurisdiction == "US-Federal"


def test_source_cache_reuses_checksum_verified_body(tmp_path: Path) -> None:
    source = _source("cached-source")
    original = _html("This approved fixture is stable across repeat offline ingestion runs.")
    cache = CachedSourceFetcher(FixtureSourceFetcher({source.source_id: original}), tmp_path)

    first = cache.fetch(source)
    second = CachedSourceFetcher(FixtureSourceFetcher({}), tmp_path).fetch(source)

    assert second == first


def test_run_evidence_does_not_overwrite_an_existing_activation_record(
    tmp_path: Path,
) -> None:
    recorded_at = datetime(2026, 10, 27, 18, 31, 20, tzinfo=UTC)
    first = _next_run_path(tmp_path, "finance_v1", recorded_at)
    first.write_text("initial activation", encoding="utf-8")

    rerun = _next_run_path(tmp_path, "finance_v1", recorded_at)

    assert first.name == "finance_v1.run.json"
    assert rerun.name == "finance_v1.run-20261027T183120000000Z.json"


def test_extraction_chunking_payload_and_idempotent_ingestion() -> None:
    source = _source("compound-interest")
    registry = _registry(source)
    service, store, _ = _service(
        registry,
        {
            source.source_id: _html(
                "Compound interest earns returns on principal and prior accumulated returns.",
                "Longer time horizons can make compounding more significant for investors.",
            )
        },
    )

    prepared = service.prepare(registry, LogicalKnowledgeBase.FINANCE)
    assert prepared.manifest.document_count == 1
    assert prepared.manifest.point_count == len(prepared.chunks) > 0
    assert all(chunk.logical_kb == LogicalKnowledgeBase.FINANCE for chunk in prepared.chunks)
    assert all(
        chunk.collection_version == prepared.manifest.collection_version
        for chunk in prepared.chunks
    )
    assert all("secret" not in chunk.text and "menu" not in chunk.text for chunk in prepared.chunks)
    assert all(chunk.content_hash and chunk.chunk_id for chunk in prepared.chunks)

    first = service.ingest(prepared)
    second = service.ingest(prepared)
    assert first.created is True
    assert first.points_written == len(prepared.chunks)
    assert second.created is False
    assert second.points_written == 0
    assert store.get_manifest(prepared.manifest.collection_name) == prepared.manifest


def test_duplicate_content_is_collapsed_and_changed_content_creates_new_version() -> None:
    first_source = _source("source-one", title="Shared Title")
    duplicate_source = _source("source-two", title="Shared Title")
    registry = _registry(first_source, duplicate_source)
    body = _html("A substantive paragraph shared by these two registered source fixtures.")
    service, _, _ = _service(registry, {"source-one": body, "source-two": body})

    original = service.prepare(registry, LogicalKnowledgeBase.FINANCE)
    assert original.manifest.document_count == 1

    changed_service, _, _ = _service(
        registry,
        {
            "source-one": _html("The source changed in a meaningful and traceable way."),
            "source-two": body,
        },
    )
    changed = changed_service.prepare(registry, LogicalKnowledgeBase.FINANCE)
    assert changed.manifest.document_count == 2
    assert changed.manifest.collection_name != original.manifest.collection_name
    assert document_versions(changed.documents) != document_versions(original.documents)


def test_enabled_source_rights_change_creates_a_new_candidate_version() -> None:
    source = _source("rights-version")
    original_registry = _registry(source)
    changed_use = source.permitted_use.model_copy(
        update={"basis": "Updated, independently reviewed permitted-use basis."}
    )
    changed_registry = _registry(source.model_copy(update={"permitted_use": changed_use}))
    body = _html("Stable source text whose permitted-use record changes independently.")
    original_service, _, _ = _service(original_registry, {source.source_id: body})
    changed_service, _, _ = _service(changed_registry, {source.source_id: body})

    original = original_service.prepare(original_registry, LogicalKnowledgeBase.FINANCE)
    changed = changed_service.prepare(changed_registry, LogicalKnowledgeBase.FINANCE)

    assert original.documents[0].document_version == changed.documents[0].document_version
    assert original.manifest.collection_name != changed.manifest.collection_name


def test_tax_filters_retrieval_gate_activation_and_rollback() -> None:
    tax_2025 = _source(
        "tax-2025",
        kb=LogicalKnowledgeBase.TAX,
        title="Tax Year 2025",
        tax_years=(2025,),
    )
    tax_2024 = _source(
        "tax-2024",
        kb=LogicalKnowledgeBase.TAX,
        title="Tax Year 2024",
        tax_years=(2024,),
    )
    registry = _registry(tax_2025, tax_2024)
    service, store, encoder = _service(
        registry,
        {
            "tax-2025": _html(
                "For tax year 2025, qualified dividend income can receive capital gain rates."
            ),
            "tax-2024": _html(
                "For tax year 2024, standard deduction guidance applies to federal returns."
            ),
        },
    )
    prepared = service.prepare(registry, LogicalKnowledgeBase.TAX)
    service.ingest(prepared)
    retriever = KnowledgeRetriever(store=store, encoder=encoder)

    for strategy in RetrievalStrategy:
        evidence = retriever.retrieve(
            prepared.manifest.collection_name,
            RetrievalQuery(
                text="qualified dividend capital gain tax",
                strategy=strategy,
                filters=RetrievalFilter(
                    logical_kb=LogicalKnowledgeBase.TAX,
                    tax_year=2025,
                    jurisdiction="US-Federal",
                ),
            ),
        )
        assert evidence
        assert all(item.document_id == "tax-2025" for item in evidence)
        assert all(2025 in item.tax_years for item in evidence)

    report = evaluate_candidate(
        logical_kb=LogicalKnowledgeBase.TAX,
        collection_name=prepared.manifest.collection_name,
        cases=(
            EvaluationCase(
                case_id="qualified-dividends-2025",
                query="qualified dividend capital gain tax",
                filters=RetrievalFilter(
                    logical_kb=LogicalKnowledgeBase.TAX,
                    tax_year=2025,
                    jurisdiction="US-Federal",
                ),
                expected_document_ids=("tax-2025",),
                critical_filter=True,
            ),
        ),
        retriever=retriever,
    )
    assert report.passed is True
    assert report.critical_filters_exact is True
    assert report.citation_integrity is True

    with pytest.raises(ValueError, match="ready"):
        store.activate("tax_education_active", prepared.manifest.collection_name)
    store.mark_ready(prepared.manifest.collection_name, "reports/tax-eval.json")
    first_activation = store.activate("tax_education_active", prepared.manifest.collection_name)
    assert first_activation.previous_collection is None

    updated_service = OfflineIngestionService(
        fetcher=FixtureSourceFetcher(
            {
                "tax-2025": _html(
                    "Updated 2025 qualified dividend guidance with capital gain rates."
                ),
                "tax-2024": _html(
                    "For tax year 2024, standard deduction guidance applies to federal returns."
                ),
            }
        ),
        encoder=encoder,
        store=store,
        chunking_policy=ChunkingPolicy(max_chars=400, overlap_chars=40, min_chars=20),
    )
    updated = updated_service.prepare(registry, LogicalKnowledgeBase.TAX)
    updated_service.ingest(updated)
    store.mark_ready(updated.manifest.collection_name, "reports/tax-eval-2.json")
    replacement = store.activate("tax_education_active", updated.manifest.collection_name)
    assert replacement.previous_collection == prepared.manifest.collection_name

    rollback = store.activate("tax_education_active", prepared.manifest.collection_name)
    assert rollback.previous_collection == updated.manifest.collection_name
    assert store.resolve_alias("tax_education_active") == prepared.manifest.collection_name
