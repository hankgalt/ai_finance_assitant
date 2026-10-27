"""Storage boundary for candidate collections, retrieval, and alias activation."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ai_finance_assistant.knowledge.models import (
    CollectionCompatibility,
    CollectionManifest,
    EmbeddedChunk,
    Evidence,
    RetrievalQuery,
    SparseEmbedding,
)


@dataclass(frozen=True)
class CandidateWriteResult:
    manifest: CollectionManifest
    created: bool
    points_written: int


@dataclass(frozen=True)
class ActivationResult:
    alias: str
    active_collection: str
    previous_collection: str | None


class KnowledgeStore(Protocol):
    def get_manifest(self, collection_name: str) -> CollectionManifest | None: ...

    def count_points(self, collection_name: str) -> int: ...

    def write_candidate(
        self, manifest: CollectionManifest, records: Sequence[EmbeddedChunk]
    ) -> CandidateWriteResult: ...

    def search(
        self,
        collection_name: str,
        query: RetrievalQuery,
        dense: Sequence[float],
        sparse: SparseEmbedding,
    ) -> tuple[Evidence, ...]: ...

    def mark_ready(self, collection_name: str, evaluation_artifact: str) -> CollectionManifest: ...

    def activate(self, alias: str, collection_name: str) -> ActivationResult: ...

    def resolve_alias(self, alias: str) -> str | None: ...

    def validate_active(
        self, alias: str, expected: CollectionCompatibility
    ) -> tuple[bool, str]: ...
