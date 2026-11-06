"""Deterministic QdrantKnowledgeStore behavior against an in-process Qdrant engine.

The opt-in server test in ``test_qdrant_integration.py`` remains the authority for server-only
behavior. Qdrant local mode does not report payload indexes or HTTP 404s, so the wrapper below
reproduces only those two server responses and delegates storage and retrieval to the real
in-process engine.
"""

from __future__ import annotations

import warnings
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx
import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from ai_finance_assistant.knowledge import qdrant_store
from ai_finance_assistant.knowledge.models import (
    ChunkingPolicy,
    CollectionCompatibility,
    CollectionManifest,
    EmbeddedChunk,
    KnowledgeChunk,
    LogicalKnowledgeBase,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalStrategy,
    SourceStatus,
    SourceType,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore

NOW = datetime(2026, 10, 27, tzinfo=UTC)
DENSE_ID = "local-dense-v1"
SPARSE_ID = "local-sparse-v1"


class _ServerLikeLocalClient:
    """Real local Qdrant engine with server-shaped 404s and payload-index reporting."""

    def __init__(self) -> None:
        self._client = QdrantClient(location=":memory:")
        self.indexes: dict[str, dict[str, models.PayloadIndexInfo]] = {}
        self.fail_with: UnexpectedResponse | None = None
        self.status_override: models.CollectionStatus | None = None
        self.drop_index: str | None = None
        self.count_offset = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def get_collection(self, collection_name: str) -> models.CollectionInfo:
        if self.fail_with is not None:
            raise self.fail_with
        if not self._client.collection_exists(collection_name):
            raise UnexpectedResponse(404, "Not Found", b"", httpx.Headers())
        info = self._client.get_collection(collection_name)
        schema = {
            field: value
            for field, value in self.indexes.get(collection_name, {}).items()
            if field != self.drop_index
        }
        update: dict[str, Any] = {"payload_schema": schema}
        if self.status_override is not None:
            update["status"] = self.status_override
        return info.model_copy(update=update)

    def create_payload_index(
        self, collection_name: str, field_name: str, field_schema: models.PayloadSchemaType
    ) -> None:
        self.indexes.setdefault(collection_name, {})[field_name] = models.PayloadIndexInfo(
            data_type=field_schema, points=0
        )

    def count(self, collection_name: str, exact: bool = True) -> models.CountResult:
        result = self._client.count(collection_name, exact=exact)
        return models.CountResult(count=result.count + self.count_offset)


@pytest.fixture
def local() -> _ServerLikeLocalClient:
    return _ServerLikeLocalClient()


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, local: _ServerLikeLocalClient) -> QdrantKnowledgeStore:
    monkeypatch.setattr(qdrant_store, "QdrantClient", lambda **_: local)
    return QdrantKnowledgeStore("http://qdrant.invalid:6333")


def _chunk(
    version: str, index: int, text: str, *, jurisdiction: str = "US-Federal"
) -> KnowledgeChunk:
    return KnowledgeChunk(
        logical_kb=LogicalKnowledgeBase.FINANCE,
        collection_version=version,
        document_id=f"doc-{index}",
        document_version="c" * 64,
        chunk_id=sha256(f"{version}-{index}".encode()).hexdigest(),
        title=f"Source {index}",
        publisher="Test publisher",
        canonical_url=f"https://example.gov/{index}",
        source_type=SourceType.HTML,
        section_path=f"Source {index} > Section",
        jurisdiction=jurisdiction,
        content_hash=str(index) * 64,
        fetched_at=NOW,
        reviewed_at=NOW,
        permitted_use="Synthetic local-engine fixture",
        status=SourceStatus.APPROVED,
        text=text,
    )


def _records(version: str) -> tuple[EmbeddedChunk, ...]:
    return (
        EmbeddedChunk(
            chunk=_chunk(version, 1, "Index funds track a market benchmark at low cost."),
            dense=(1.0, 0.0, 0.0, 0.0),
            sparse=SparseEmbedding(indices=(1, 2), values=(1.0, 0.5)),
        ),
        EmbeddedChunk(
            chunk=_chunk(version, 2, "Bonds pay interest to holders.", jurisdiction="US-NY"),
            dense=(0.0, 1.0, 0.0, 0.0),
            sparse=SparseEmbedding(indices=(3, 4), values=(1.0, 0.5)),
        ),
    )


def _manifest(
    name: str, version: str, *, points: int = 2, checksum: str = "a"
) -> CollectionManifest:
    return CollectionManifest(
        logical_kb=LogicalKnowledgeBase.FINANCE,
        collection_name=name,
        collection_version=version,
        corpus_checksum=checksum * 64,
        source_registry_checksum="b" * 64,
        dense_model_id=DENSE_ID,
        dense_dimensions=4,
        sparse_model_id=SPARSE_ID,
        chunking_policy=ChunkingPolicy(max_chars=400, overlap_chars=40, min_chars=20),
        point_count=points,
        document_count=points,
        source_ids=tuple(f"doc-{index}" for index in range(1, points + 1)),
        created_at=NOW,
    )


def _compatibility(**overrides: Any) -> CollectionCompatibility:
    values: dict[str, Any] = {
        "logical_kb": LogicalKnowledgeBase.FINANCE,
        "dense_model_id": DENSE_ID,
        "dense_dimensions": 4,
        "sparse_model_id": SPARSE_ID,
    }
    values.update(overrides)
    return CollectionCompatibility(**values)


def _ready(store: QdrantKnowledgeStore, name: str = "finance_v1", version: str = "v1") -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        store.write_candidate(_manifest(name, version), _records(version))
    store.mark_ready(name, "synthetic:evaluation")


def test_candidate_write_is_idempotent_and_records_manifest_metadata(
    store: QdrantKnowledgeStore, local: _ServerLikeLocalClient
) -> None:
    manifest = _manifest("finance_v1", "v1")

    assert store.get_manifest("finance_v1") is None
    first = store.write_candidate(manifest, _records("v1"))
    second = store.write_candidate(manifest, _records("v1"))

    assert (first.created, first.points_written) == (True, 2)
    assert (second.created, second.points_written) == (False, 2)
    assert store.count_points("finance_v1") == 2
    assert store.get_manifest("finance_v1") == manifest
    assert set(local.indexes["finance_v1"]) == qdrant_store._REQUIRED_INDEXES
    metadata = local._client.get_collection("finance_v1").config.metadata or {}
    assert metadata["dense_model_id"] == DENSE_ID
    assert len(metadata["manifest_checksum"]) == 64


def test_candidate_write_rejects_incompatible_or_inconsistent_input(
    store: QdrantKnowledgeStore, local: _ServerLikeLocalClient
) -> None:
    store.write_candidate(_manifest("finance_v1", "v1"), _records("v1"))

    with pytest.raises(ValueError, match="incompatible metadata"):
        store.write_candidate(_manifest("finance_v1", "v1", checksum="9"), _records("v1"))
    with pytest.raises(ValueError, match="point count does not match"):
        store.write_candidate(_manifest("finance_v2", "v2", points=3), _records("v2"))

    local.count_offset = 1
    with pytest.raises(ValueError, match="candidate point count mismatch"):
        store.write_candidate(_manifest("finance_v3", "v3"), _records("v3"))


def test_manifest_lookup_surfaces_non_404_errors_and_invalid_metadata(
    store: QdrantKnowledgeStore, local: _ServerLikeLocalClient
) -> None:
    local._client.create_collection(
        "foreign",
        vectors_config={"dense": models.VectorParams(size=4, distance=models.Distance.COSINE)},
    )
    with pytest.raises(ValueError, match="no valid M1 manifest"):
        store.get_manifest("foreign")

    local.fail_with = UnexpectedResponse(500, "Server Error", b"", httpx.Headers())
    with pytest.raises(UnexpectedResponse):
        store.get_manifest("foreign")


@pytest.mark.parametrize(
    ("strategy", "dense", "sparse", "expected_first"),
    [
        (RetrievalStrategy.DENSE, (1.0, 0.0, 0.0, 0.0), ((9,), (1.0,)), "doc-1"),
        (RetrievalStrategy.SPARSE, (0.0, 0.0, 1.0, 0.0), ((3, 4), (1.0, 1.0)), "doc-2"),
        (RetrievalStrategy.HYBRID, (0.0, 1.0, 0.0, 0.0), ((3,), (1.0,)), "doc-2"),
    ],
)
def test_search_returns_attributed_evidence_for_each_strategy(
    store: QdrantKnowledgeStore,
    strategy: RetrievalStrategy,
    dense: tuple[float, ...],
    sparse: tuple[tuple[int, ...], tuple[float, ...]],
    expected_first: str,
) -> None:
    _ready(store)
    query = RetrievalQuery(
        text="synthetic",
        strategy=strategy,
        filters=RetrievalFilter(logical_kb=LogicalKnowledgeBase.FINANCE),
        limit=2,
    )

    evidence = store.search(
        "finance_v1", query, dense, SparseEmbedding(indices=sparse[0], values=sparse[1])
    )

    assert evidence[0].document_id == expected_first
    assert [item.rank for item in evidence] == list(range(1, len(evidence) + 1))
    assert evidence[0].collection_name == "finance_v1"
    assert evidence[0].collection_version == "v1"
    assert evidence[0].canonical_url.startswith("https://example.gov/")


def test_search_applies_jurisdiction_and_tax_year_filters(store: QdrantKnowledgeStore) -> None:
    _ready(store)
    dense = (1.0, 1.0, 0.0, 0.0)
    sparse = SparseEmbedding(indices=(1, 3), values=(1.0, 1.0))

    new_york = store.search(
        "finance_v1",
        RetrievalQuery(
            text="synthetic",
            strategy=RetrievalStrategy.DENSE,
            filters=RetrievalFilter(logical_kb=LogicalKnowledgeBase.FINANCE, jurisdiction="US-NY"),
        ),
        dense,
        sparse,
    )
    tax_year = store.search(
        "finance_v1",
        RetrievalQuery(
            text="synthetic",
            filters=RetrievalFilter(logical_kb=LogicalKnowledgeBase.FINANCE, tax_year=2025),
        ),
        dense,
        sparse,
    )

    assert [item.document_id for item in new_york] == ["doc-2"]
    assert tax_year == ()


def test_evidence_requires_a_payload() -> None:
    with pytest.raises(ValueError, match="no payload"):
        QdrantKnowledgeStore._evidence(None, 1.0, 1, "finance_v1")


def test_activation_requires_ready_collections_and_supports_rollback(
    store: QdrantKnowledgeStore,
) -> None:
    with pytest.raises(ValueError, match="unknown collection"):
        store.mark_ready("missing", "synthetic")
    store.write_candidate(_manifest("finance_v1", "v1"), _records("v1"))
    with pytest.raises(ValueError, match="only evaluated, ready"):
        store.activate("finance_active", "finance_v1")

    store.mark_ready("finance_v1", "synthetic:first")
    _ready(store, "finance_v2", "v2")

    initial = store.activate("finance_active", "finance_v1")
    unchanged = store.activate("finance_active", "finance_v1")
    replacement = store.activate("finance_active", "finance_v2")
    rollback = store.activate("finance_active", "finance_v1")

    assert initial.previous_collection is None
    assert unchanged.previous_collection == "finance_v1"
    assert replacement.previous_collection == "finance_v1"
    assert rollback.previous_collection == "finance_v2"
    assert store.resolve_alias("finance_active") == "finance_v1"
    assert store.resolve_alias("missing_alias") is None


def test_validate_active_accepts_a_compatible_ready_collection(
    store: QdrantKnowledgeStore,
) -> None:
    _ready(store)
    store.activate("finance_active", "finance_v1")

    compatible, detail = store.validate_active("finance_active", _compatibility())

    assert compatible is True
    assert detail == "finance_active resolves to compatible collection finance_v1"


def test_validate_active_reports_missing_alias(store: QdrantKnowledgeStore) -> None:
    assert store.validate_active("finance_active", _compatibility()) == (
        False,
        "active alias is missing",
    )


def test_validate_active_reports_every_metadata_mismatch(store: QdrantKnowledgeStore) -> None:
    _ready(store)
    store.activate("finance_active", "finance_v1")

    compatible, detail = store.validate_active(
        "finance_active",
        _compatibility(
            schema_version="0",
            logical_kb=LogicalKnowledgeBase.TAX,
            dense_model_id="other-dense",
            dense_model_revision="other",
            dense_artifact_sha256="0" * 64,
            dense_dimensions=8,
            sparse_model_id="other-sparse",
            sparse_model_revision="other",
            sparse_artifact_sha256="0" * 64,
            chunking_policy_version="other",
        ),
    )

    assert compatible is False
    assert detail == (
        "incompatible collection metadata: schema_version, logical_kb, dense_model_id, "
        "dense_model_revision, dense_artifact_sha256, dense_dimensions, sparse_model_id, "
        "sparse_model_revision, sparse_artifact_sha256, chunking_policy_version"
    )


def test_validate_active_rejects_unready_unhealthy_or_incomplete_collections(
    store: QdrantKnowledgeStore, local: _ServerLikeLocalClient
) -> None:
    _ready(store)
    store.activate("finance_active", "finance_v1")

    local.drop_index = "tax_year"
    assert store.validate_active("finance_active", _compatibility()) == (
        False,
        "required payload indexes are missing: tax_year",
    )
    local.drop_index = None

    assert store.validate_active("finance_active", _compatibility(dense_vector_name="missing")) == (
        False,
        "required dense vector is missing or incompatible",
    )
    assert store.validate_active(
        "finance_active", _compatibility(sparse_vector_name="missing")
    ) == (False, "required sparse vector is missing")

    local.status_override = models.CollectionStatus.RED
    assert store.validate_active("finance_active", _compatibility()) == (
        False,
        "Qdrant collection status is red",
    )
    local.status_override = None

    local._client.update_collection(
        "finance_v1",
        metadata=store._metadata(_manifest("finance_v1", "v1")),
    )
    assert store.validate_active("finance_active", _compatibility()) == (
        False,
        "collection is not marked ready",
    )


def test_validate_active_rejects_empty_or_foreign_collections(
    store: QdrantKnowledgeStore, local: _ServerLikeLocalClient
) -> None:
    empty = _manifest("finance_empty", "v1", points=0).model_copy(
        update={"source_ids": (), "document_count": 0}
    )
    local._client.create_collection(
        "finance_empty",
        vectors_config={"dense": models.VectorParams(size=4, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
        metadata=store._metadata(empty),
    )
    for field in qdrant_store._REQUIRED_INDEXES:
        local.create_payload_index("finance_empty", field, models.PayloadSchemaType.KEYWORD)
    store.mark_ready("finance_empty", "synthetic")
    store.activate("finance_active", "finance_empty")
    assert store.validate_active("finance_active", _compatibility()) == (
        False,
        "active collection contains no points",
    )

    local._client.create_collection(
        "foreign",
        vectors_config={"dense": models.VectorParams(size=4, distance=models.Distance.COSINE)},
    )
    local._client.update_collection_aliases(
        [
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name="foreign", alias_name="foreign_active"
                )
            )
        ]
    )
    compatible, detail = store.validate_active("foreign_active", _compatibility())
    assert compatible is False
    assert "no valid M1 manifest" in detail
