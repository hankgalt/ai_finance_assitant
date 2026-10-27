"""In-memory knowledge store used for deterministic contract and pipeline tests."""

import math
from collections.abc import Sequence

from ai_finance_assistant.knowledge.models import (
    CollectionCompatibility,
    CollectionManifest,
    CollectionState,
    EmbeddedChunk,
    Evidence,
    RetrievalQuery,
    RetrievalStrategy,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.store import ActivationResult, CandidateWriteResult


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _sparse_dot(left: SparseEmbedding, right: SparseEmbedding) -> float:
    left_values = dict(zip(left.indices, left.values, strict=True))
    return sum(
        left_values.get(index, 0.0) * value
        for index, value in zip(right.indices, right.values, strict=True)
    )


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._manifests: dict[str, CollectionManifest] = {}
        self._records: dict[str, tuple[EmbeddedChunk, ...]] = {}
        self._aliases: dict[str, str] = {}

    def get_manifest(self, collection_name: str) -> CollectionManifest | None:
        return self._manifests.get(collection_name)

    def count_points(self, collection_name: str) -> int:
        return len(self._records.get(collection_name, ()))

    def write_candidate(
        self, manifest: CollectionManifest, records: Sequence[EmbeddedChunk]
    ) -> CandidateWriteResult:
        if manifest.collection_name in self._manifests:
            raise ValueError(f"collection {manifest.collection_name} already exists")
        if manifest.point_count != len(records):
            raise ValueError("manifest point count does not match records")
        self._manifests[manifest.collection_name] = manifest
        self._records[manifest.collection_name] = tuple(records)
        return CandidateWriteResult(
            manifest=manifest,
            created=True,
            points_written=len(records),
        )

    def search(
        self,
        collection_name: str,
        query: RetrievalQuery,
        dense: Sequence[float],
        sparse: SparseEmbedding,
    ) -> tuple[Evidence, ...]:
        records = self._records.get(collection_name)
        if records is None:
            raise ValueError(f"unknown collection {collection_name}")
        filtered = [record for record in records if self._matches(record, query)]
        dense_ranked = sorted(
            ((_cosine(dense, record.dense), record) for record in filtered),
            key=lambda item: (-item[0], item[1].chunk.chunk_id),
        )
        sparse_ranked = sorted(
            ((_sparse_dot(sparse, record.sparse), record) for record in filtered),
            key=lambda item: (-item[0], item[1].chunk.chunk_id),
        )
        if query.strategy == RetrievalStrategy.DENSE:
            ranked = dense_ranked
        elif query.strategy == RetrievalStrategy.SPARSE:
            ranked = sparse_ranked
        else:
            ranks: dict[str, float] = {}
            records_by_id: dict[str, EmbeddedChunk] = {}
            for ordered in (dense_ranked, sparse_ranked):
                for rank, (_, record) in enumerate(ordered, start=1):
                    chunk_id = record.chunk.chunk_id
                    records_by_id[chunk_id] = record
                    ranks[chunk_id] = ranks.get(chunk_id, 0.0) + 1.0 / (60 + rank)
            ranked = sorted(
                ((score, records_by_id[chunk_id]) for chunk_id, score in ranks.items()),
                key=lambda item: (-item[0], item[1].chunk.chunk_id),
            )
        return tuple(
            self._to_evidence(record, score, rank, collection_name)
            for rank, (score, record) in enumerate(ranked[: query.limit], start=1)
        )

    @staticmethod
    def _matches(record: EmbeddedChunk, query: RetrievalQuery) -> bool:
        chunk = record.chunk
        filters = query.filters
        if chunk.logical_kb != filters.logical_kb:
            return False
        if filters.tax_year is not None and filters.tax_year not in chunk.tax_year:
            return False
        return filters.jurisdiction is None or chunk.jurisdiction == filters.jurisdiction

    @staticmethod
    def _to_evidence(
        record: EmbeddedChunk, score: float, rank: int, collection_name: str
    ) -> Evidence:
        chunk = record.chunk
        return Evidence(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            title=chunk.title,
            publisher=chunk.publisher,
            canonical_url=chunk.canonical_url,
            section_path=chunk.section_path,
            text=chunk.text,
            score=score,
            rank=rank,
            collection_name=collection_name,
            collection_version=chunk.collection_version,
            document_version=chunk.document_version,
            content_hash=chunk.content_hash,
            fetched_at=chunk.fetched_at,
            tax_years=chunk.tax_year,
            jurisdiction=chunk.jurisdiction,
        )

    def mark_ready(self, collection_name: str, evaluation_artifact: str) -> CollectionManifest:
        current = self._manifests[collection_name]
        updated = current.model_copy(
            update={
                "state": CollectionState.READY,
                "ready": True,
                "evaluation_artifact": evaluation_artifact,
            }
        )
        self._manifests[collection_name] = updated
        return updated

    def activate(self, alias: str, collection_name: str) -> ActivationResult:
        manifest = self._manifests[collection_name]
        if not manifest.ready:
            raise ValueError("only evaluated, ready collections may be activated")
        previous = self._aliases.get(alias)
        self._aliases[alias] = collection_name
        self._manifests[collection_name] = manifest.model_copy(
            update={"state": CollectionState.ACTIVE}
        )
        if previous is not None and previous != collection_name:
            self._manifests[previous] = self._manifests[previous].model_copy(
                update={"state": CollectionState.RETIRED}
            )
        return ActivationResult(alias, collection_name, previous)

    def resolve_alias(self, alias: str) -> str | None:
        return self._aliases.get(alias)

    def validate_active(self, alias: str, expected: CollectionCompatibility) -> tuple[bool, str]:
        active = self.resolve_alias(alias)
        if active is None:
            return False, "active alias is missing"
        manifest = self._manifests[active]
        fields = (
            "schema_version",
            "logical_kb",
            "dense_model_id",
            "dense_model_revision",
            "dense_artifact_sha256",
            "dense_dimensions",
            "sparse_model_id",
            "sparse_model_revision",
            "sparse_artifact_sha256",
        )
        mismatches = [
            field for field in fields if getattr(manifest, field) != getattr(expected, field)
        ]
        if mismatches:
            return False, f"incompatible collection metadata: {', '.join(mismatches)}"
        if manifest.chunking_policy.version != expected.chunking_policy_version:
            return False, "incompatible collection metadata: chunking_policy_version"
        if not manifest.ready:
            return False, "collection is not marked ready"
        return True, f"{alias} resolves to compatible collection {active}"
