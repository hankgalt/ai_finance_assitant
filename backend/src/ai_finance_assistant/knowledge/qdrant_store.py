"""Qdrant implementation of immutable candidates and read-only runtime retrieval."""

import json
import uuid
from collections.abc import Sequence
from hashlib import sha256
from importlib.metadata import version
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from ai_finance_assistant.knowledge.models import (
    CollectionCompatibility,
    CollectionManifest,
    CollectionState,
    EmbeddedChunk,
    Evidence,
    KnowledgeChunk,
    RetrievalQuery,
    RetrievalStrategy,
    SparseEmbedding,
)
from ai_finance_assistant.knowledge.store import ActivationResult, CandidateWriteResult

_KEYWORD_INDEXES = (
    "logical_kb",
    "status",
    "publisher",
    "source_type",
    "jurisdiction",
    "document_id",
    "document_version",
    "chunk_id",
    "content_hash",
)
_DATETIME_INDEXES = ("fetched_at", "reviewed_at")
_REQUIRED_INDEXES = {*_KEYWORD_INDEXES, *_DATETIME_INDEXES, "tax_year"}
_UPSERT_BATCH_SIZE = 128


class QdrantKnowledgeStore:
    def __init__(self, url: str, *, timeout_seconds: int = 10) -> None:
        self._client = QdrantClient(url=url, timeout=timeout_seconds, check_compatibility=True)

    @staticmethod
    def _metadata(manifest: CollectionManifest) -> dict[str, Any]:
        manifest_data = manifest.model_dump(mode="json")
        manifest_checksum = sha256(
            json.dumps(manifest_data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "schema_version": manifest.schema_version,
            "logical_kb": manifest.logical_kb.value,
            "collection_version": manifest.collection_version,
            "dense_model_id": manifest.dense_model_id,
            "dense_model_revision": manifest.dense_model_revision,
            "dense_artifact_sha256": manifest.dense_artifact_sha256,
            "dense_dimensions": manifest.dense_dimensions,
            "sparse_model_id": manifest.sparse_model_id,
            "sparse_model_revision": manifest.sparse_model_revision,
            "sparse_artifact_sha256": manifest.sparse_artifact_sha256,
            "chunking_policy_version": manifest.chunking_policy.version,
            "ready": manifest.ready,
            "manifest_checksum": manifest_checksum,
            "qdrant_client_version": version("qdrant-client"),
            "fastembed_version": version("fastembed"),
            "manifest": manifest_data,
        }

    def get_manifest(self, collection_name: str) -> CollectionManifest | None:
        try:
            info = self._client.get_collection(collection_name)
        except UnexpectedResponse as error:
            if error.status_code == 404:
                return None
            raise
        metadata = info.config.metadata or {}
        raw_manifest = metadata.get("manifest")
        if not isinstance(raw_manifest, dict):
            raise ValueError(f"collection {collection_name} has no valid M1 manifest")
        return CollectionManifest.model_validate(raw_manifest)

    def count_points(self, collection_name: str) -> int:
        return self._client.count(collection_name, exact=True).count

    def write_candidate(
        self, manifest: CollectionManifest, records: Sequence[EmbeddedChunk]
    ) -> CandidateWriteResult:
        existing = self.get_manifest(manifest.collection_name)
        if existing is not None and existing.corpus_checksum != manifest.corpus_checksum:
            raise ValueError(f"collection {manifest.collection_name} has incompatible metadata")
        if len(records) != manifest.point_count:
            raise ValueError("manifest point count does not match records")

        if existing is None:
            self._client.create_collection(
                collection_name=manifest.collection_name,
                vectors_config={
                    manifest.dense_vector_name: models.VectorParams(
                        size=manifest.dense_dimensions,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    manifest.sparse_vector_name: models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False),
                        modifier=models.Modifier.IDF,
                    )
                },
                metadata=self._metadata(manifest),
            )
            self._create_payload_indexes(manifest.collection_name)

        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, record.chunk.chunk_id)),
                vector={
                    manifest.dense_vector_name: list(record.dense),
                    manifest.sparse_vector_name: models.SparseVector(
                        indices=list(record.sparse.indices),
                        values=list(record.sparse.values),
                    ),
                },
                payload=record.chunk.model_dump(mode="json"),
            )
            for record in records
        ]
        for start in range(0, len(points), _UPSERT_BATCH_SIZE):
            self._client.upsert(
                manifest.collection_name,
                points=points[start : start + _UPSERT_BATCH_SIZE],
                wait=True,
            )
        actual_count = self.count_points(manifest.collection_name)
        if actual_count != manifest.point_count:
            raise ValueError(
                "candidate point count mismatch: "
                f"expected {manifest.point_count}, got {actual_count}"
            )
        return CandidateWriteResult(
            manifest=manifest,
            created=existing is None,
            points_written=len(points),
        )

    def _create_payload_indexes(self, collection_name: str) -> None:
        for field in _KEYWORD_INDEXES:
            self._client.create_payload_index(
                collection_name, field, models.PayloadSchemaType.KEYWORD
            )
        self._client.create_payload_index(
            collection_name, "tax_year", models.PayloadSchemaType.INTEGER
        )
        for field in _DATETIME_INDEXES:
            self._client.create_payload_index(
                collection_name, field, models.PayloadSchemaType.DATETIME
            )

    @staticmethod
    def _filter(query: RetrievalQuery) -> models.Filter:
        conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="logical_kb",
                match=models.MatchValue(value=query.filters.logical_kb.value),
            )
        ]
        if query.filters.tax_year is not None:
            conditions.append(
                models.FieldCondition(
                    key="tax_year",
                    match=models.MatchValue(value=query.filters.tax_year),
                )
            )
        if query.filters.jurisdiction is not None:
            conditions.append(
                models.FieldCondition(
                    key="jurisdiction",
                    match=models.MatchValue(value=query.filters.jurisdiction),
                )
            )
        return models.Filter(must=conditions)

    def search(
        self,
        collection_name: str,
        query: RetrievalQuery,
        dense: Sequence[float],
        sparse: SparseEmbedding,
    ) -> tuple[Evidence, ...]:
        query_filter = self._filter(query)
        sparse_vector = models.SparseVector(
            indices=list(sparse.indices), values=list(sparse.values)
        )
        if query.strategy == RetrievalStrategy.DENSE:
            response = self._client.query_points(
                collection_name,
                query=list(dense),
                using="dense",
                query_filter=query_filter,
                limit=query.limit,
                with_payload=True,
            )
        elif query.strategy == RetrievalStrategy.SPARSE:
            response = self._client.query_points(
                collection_name,
                query=sparse_vector,
                using="sparse",
                query_filter=query_filter,
                limit=query.limit,
                with_payload=True,
            )
        else:
            prefetch_limit = max(20, query.limit * 4)
            response = self._client.query_points(
                collection_name,
                prefetch=[
                    models.Prefetch(
                        query=list(dense),
                        using="dense",
                        filter=query_filter,
                        limit=prefetch_limit,
                    ),
                    models.Prefetch(
                        query=sparse_vector,
                        using="sparse",
                        filter=query_filter,
                        limit=prefetch_limit,
                    ),
                ],
                query=models.RrfQuery(rrf=models.Rrf(k=60)),
                query_filter=query_filter,
                limit=query.limit,
                with_payload=True,
            )
        return tuple(
            self._evidence(point.payload, point.score, rank, collection_name)
            for rank, point in enumerate(response.points, start=1)
        )

    @staticmethod
    def _evidence(
        payload: dict[str, Any] | None,
        score: float,
        rank: int,
        collection_name: str,
    ) -> Evidence:
        if payload is None:
            raise ValueError("retrieved point has no payload")
        chunk = KnowledgeChunk.model_validate(payload)
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
        manifest = self.get_manifest(collection_name)
        if manifest is None:
            raise ValueError(f"unknown collection {collection_name}")
        updated = manifest.model_copy(
            update={
                "state": CollectionState.READY,
                "ready": True,
                "evaluation_artifact": evaluation_artifact,
            }
        )
        self._client.update_collection(collection_name, metadata=self._metadata(updated))
        return updated

    def activate(self, alias: str, collection_name: str) -> ActivationResult:
        manifest = self.get_manifest(collection_name)
        if manifest is None or not manifest.ready:
            raise ValueError("only evaluated, ready collections may be activated")
        previous = self.resolve_alias(alias)
        if previous == collection_name:
            return ActivationResult(alias, collection_name, previous)
        operations: list[models.CreateAliasOperation | models.DeleteAliasOperation] = []
        if previous is not None:
            operations.append(
                models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias))
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name=collection_name,
                    alias_name=alias,
                )
            )
        )
        self._client.update_collection_aliases(operations)
        return ActivationResult(alias, collection_name, previous)

    def resolve_alias(self, alias: str) -> str | None:
        aliases = self._client.get_aliases().aliases
        match = next((entry for entry in aliases if entry.alias_name == alias), None)
        return None if match is None else match.collection_name

    def validate_active(self, alias: str, expected: CollectionCompatibility) -> tuple[bool, str]:
        collection_name = self.resolve_alias(alias)
        if collection_name is None:
            return False, "active alias is missing"
        info = self._client.get_collection(collection_name)
        if info.status in {models.CollectionStatus.RED, models.CollectionStatus.GREY}:
            return False, f"Qdrant collection status is {info.status.value}"
        try:
            manifest = self.get_manifest(collection_name)
        except ValueError as error:
            return False, str(error)
        if manifest is None:
            return False, "active collection is missing"
        mismatches: list[str] = []
        if manifest.schema_version != expected.schema_version:
            mismatches.append("schema_version")
        if manifest.logical_kb != expected.logical_kb:
            mismatches.append("logical_kb")
        if manifest.dense_model_id != expected.dense_model_id:
            mismatches.append("dense_model_id")
        if manifest.dense_model_revision != expected.dense_model_revision:
            mismatches.append("dense_model_revision")
        if manifest.dense_artifact_sha256 != expected.dense_artifact_sha256:
            mismatches.append("dense_artifact_sha256")
        if manifest.dense_dimensions != expected.dense_dimensions:
            mismatches.append("dense_dimensions")
        if manifest.sparse_model_id != expected.sparse_model_id:
            mismatches.append("sparse_model_id")
        if manifest.sparse_model_revision != expected.sparse_model_revision:
            mismatches.append("sparse_model_revision")
        if manifest.sparse_artifact_sha256 != expected.sparse_artifact_sha256:
            mismatches.append("sparse_artifact_sha256")
        if manifest.chunking_policy.version != expected.chunking_policy_version:
            mismatches.append("chunking_policy_version")
        if mismatches:
            return False, f"incompatible collection metadata: {', '.join(mismatches)}"
        if not manifest.ready:
            return False, "collection is not marked ready"

        vectors = info.config.params.vectors
        dense_config = (
            vectors.get(expected.dense_vector_name) if isinstance(vectors, dict) else None
        )
        sparse_vectors = info.config.params.sparse_vectors or {}
        if dense_config is None or dense_config.size != expected.dense_dimensions:
            return False, "required dense vector is missing or incompatible"
        if expected.sparse_vector_name not in sparse_vectors:
            return False, "required sparse vector is missing"
        missing_indexes = _REQUIRED_INDEXES.difference(info.payload_schema)
        if missing_indexes:
            return (
                False,
                f"required payload indexes are missing: {', '.join(sorted(missing_indexes))}",
            )
        if not info.points_count:
            return False, "active collection contains no points"
        return True, f"{alias} resolves to compatible collection {collection_name}"
