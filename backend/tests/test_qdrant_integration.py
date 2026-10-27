import os
import uuid
from datetime import UTC, datetime

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models

from ai_finance_assistant.knowledge.models import (
    ChunkingPolicy,
    CollectionCompatibility,
    CollectionManifest,
    EmbeddedChunk,
    KnowledgeChunk,
    LogicalKnowledgeBase,
    SourceStatus,
    SourceType,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore

QDRANT_URL = os.getenv("AIFA_TEST_QDRANT_URL")


def _candidate(name: str, version: str) -> tuple[CollectionManifest, EmbeddedChunk]:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    manifest = CollectionManifest(
        logical_kb=LogicalKnowledgeBase.FINANCE,
        collection_name=name,
        collection_version=version,
        corpus_checksum="a" * 64,
        source_registry_checksum="b" * 64,
        dense_model_id="integration-dense-v1",
        dense_dimensions=4,
        sparse_model_id="integration-sparse-v1",
        chunking_policy=ChunkingPolicy(max_chars=400, overlap_chars=40, min_chars=20),
        point_count=1,
        document_count=1,
        source_ids=("integration-source",),
        created_at=now,
    )
    chunk = KnowledgeChunk(
        logical_kb=LogicalKnowledgeBase.FINANCE,
        collection_version=version,
        document_id="integration-source",
        document_version="c" * 64,
        chunk_id=("d" if version == "v1" else "e") * 64,
        title="Integration source",
        publisher="Test publisher",
        canonical_url="https://example.gov/integration",
        source_type=SourceType.HTML,
        section_path="Integration source > Test",
        jurisdiction="US-Federal",
        content_hash="f" * 64,
        fetched_at=now,
        reviewed_at=now,
        permitted_use="Synthetic integration fixture",
        status=SourceStatus.APPROVED,
        text="Synthetic Qdrant integration content that is never product evidence.",
    )
    return manifest, EmbeddedChunk(
        chunk=chunk,
        dense=(1.0, 0.0, 0.0, 0.0),
        sparse=SparseEmbedding(indices=(1, 2), values=(1.0, 0.5)),
    )


@pytest.mark.qdrant
@pytest.mark.skipif(QDRANT_URL is None, reason="AIFA_TEST_QDRANT_URL is not configured")
def test_qdrant_candidate_validation_activation_and_rollback() -> None:
    assert QDRANT_URL is not None
    suffix = uuid.uuid4().hex[:10]
    first_name = f"m1_integration_first_{suffix}"
    second_name = f"m1_integration_second_{suffix}"
    alias = f"m1_integration_active_{suffix}"
    store = QdrantKnowledgeStore(QDRANT_URL)
    client = QdrantClient(url=QDRANT_URL)
    try:
        first, first_record = _candidate(first_name, "v1")
        second, second_record = _candidate(second_name, "v2")
        store.write_candidate(first, (first_record,))
        store.write_candidate(second, (second_record,))
        store.mark_ready(first_name, "synthetic:first")
        store.mark_ready(second_name, "synthetic:second")

        initial = store.activate(alias, first_name)
        replacement = store.activate(alias, second_name)
        rollback = store.activate(alias, first_name)

        assert initial.previous_collection is None
        assert replacement.previous_collection == first_name
        assert rollback.previous_collection == second_name
        assert store.resolve_alias(alias) == first_name
        compatible, _ = store.validate_active(
            alias,
            CollectionCompatibility(
                logical_kb=LogicalKnowledgeBase.FINANCE,
                dense_model_id="integration-dense-v1",
                dense_dimensions=4,
                sparse_model_id="integration-sparse-v1",
            ),
        )
        assert compatible is True
    finally:
        if store.resolve_alias(alias) is not None:
            client.update_collection_aliases(
                [models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias))]
            )
        for collection_name in (first_name, second_name):
            if client.collection_exists(collection_name):
                client.delete_collection(collection_name)
