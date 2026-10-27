"""Dense and sparse representation adapters used by offline ingestion and retrieval."""

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from ai_finance_assistant.knowledge.models import (
    DENSE_MODEL_ARTIFACT_SHA256,
    DENSE_MODEL_REVISION,
    SPARSE_MODEL_ARTIFACT_SHA256,
    SPARSE_MODEL_REVISION,
    SparseEmbedding,
)

_TOKEN = re.compile(r"[a-z0-9]+")


class RepresentationEncoder(Protocol):
    @property
    def dense_model_id(self) -> str: ...

    @property
    def sparse_model_id(self) -> str: ...

    @property
    def dense_model_revision(self) -> str: ...

    @property
    def dense_artifact_sha256(self) -> str: ...

    @property
    def sparse_model_revision(self) -> str: ...

    @property
    def sparse_artifact_sha256(self) -> str: ...

    @property
    def dense_dimensions(self) -> int: ...

    def embed_dense(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_sparse(self, texts: Sequence[str]) -> list[SparseEmbedding]: ...


class DeterministicTestEncoder:
    """Stable fake encoder; never use its vectors as production evidence."""

    dense_model_id = "deterministic-test-dense-v1"
    sparse_model_id = "deterministic-test-sparse-v1"
    dense_model_revision = "deterministic-dense-revision-v1"
    dense_artifact_sha256 = "1" * 64
    sparse_model_revision = "deterministic-sparse-revision-v1"
    sparse_artifact_sha256 = "2" * 64

    def __init__(self, dimensions: int = 32) -> None:
        self._dimensions = dimensions

    @property
    def dense_dimensions(self) -> int:
        return self._dimensions

    def embed_dense(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._dimensions
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self._dimensions
                vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors

    def embed_sparse(self, texts: Sequence[str]) -> list[SparseEmbedding]:
        embeddings: list[SparseEmbedding] = []
        for text in texts:
            counts: Counter[int] = Counter(
                int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
                for token in _TOKEN.findall(text.lower())
            )
            indices = tuple(sorted(counts))
            embeddings.append(
                SparseEmbedding(
                    indices=indices,
                    values=tuple(float(counts[index]) for index in indices),
                )
            )
        return embeddings


class FastEmbedEncoder:
    """Local CPU encoder using the frozen M1 model identifiers."""

    dense_model_id = "BAAI/bge-small-en-v1.5"
    sparse_model_id = "Qdrant/bm25"
    dense_model_revision = DENSE_MODEL_REVISION
    dense_artifact_sha256 = DENSE_MODEL_ARTIFACT_SHA256
    sparse_model_revision = SPARSE_MODEL_REVISION
    sparse_artifact_sha256 = SPARSE_MODEL_ARTIFACT_SHA256
    dense_dimensions = 384

    def __init__(self) -> None:
        from fastembed import SparseTextEmbedding, TextEmbedding

        self._dense = TextEmbedding(model_name=self.dense_model_id)
        self._sparse = SparseTextEmbedding(model_name=self.sparse_model_id)

    def embed_dense(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._dense.embed(list(texts))]

    def embed_sparse(self, texts: Sequence[str]) -> list[SparseEmbedding]:
        return [
            SparseEmbedding(
                indices=tuple(int(index) for index in vector.indices.tolist()),
                values=tuple(float(value) for value in vector.values.tolist()),
            )
            for vector in self._sparse.embed(list(texts))
        ]
