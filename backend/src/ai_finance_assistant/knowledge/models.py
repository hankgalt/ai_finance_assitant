"""Versioned contracts for knowledge sources, chunks, collections, and evaluation."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

DENSE_MODEL_REVISION = "aa8f8b060edb00e03bfdd08813a2949946c8ba55"
DENSE_MODEL_ARTIFACT_SHA256 = "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"
SPARSE_MODEL_REVISION = "22b8d2af71a76161e18dd432d2cee0eefa66e412"
SPARSE_MODEL_ARTIFACT_SHA256 = "019f104ba2ed07436d05f9cdd3383034ad66014edc27fc651f837e1a038b6451"


class LogicalKnowledgeBase(StrEnum):
    FINANCE = "finance_education"
    TAX = "tax_education"


class SourceStatus(StrEnum):
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    QUARANTINED = "quarantined"


class SourceType(StrEnum):
    HTML = "html"
    PDF = "pdf"


class PermittedUse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    basis: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    ai_processing_allowed: bool
    redistribution_allowed: bool
    attribution_required: bool
    restrictions: tuple[str, ...] = ()
    reviewed_at: datetime


class SourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    logical_kb: LogicalKnowledgeBase
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    canonical_url: HttpUrl
    source_type: SourceType
    jurisdiction: str = Field(min_length=1)
    tax_years: tuple[int, ...] = ()
    status: SourceStatus
    permitted_use: PermittedUse
    ingestion_enabled: bool = False

    @model_validator(mode="after")
    def validate_activation(self) -> "SourceDefinition":
        if self.ingestion_enabled and self.status != SourceStatus.APPROVED:
            raise ValueError("only approved sources may be enabled for ingestion")
        if self.logical_kb == LogicalKnowledgeBase.TAX and not self.tax_years:
            raise ValueError("tax sources must declare at least one tax year")
        return self


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    reviewed_at: datetime
    sources: tuple[SourceDefinition, ...]

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "SourceRegistry":
        source_ids = [source.source_id for source in self.sources]
        urls = [str(source.canonical_url) for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        if len(urls) != len(set(urls)):
            raise ValueError("canonical_url values must be unique")
        return self


class FetchedSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    canonical_url: str
    content_type: str
    body: bytes
    fetched_at: datetime
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class NormalizedSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    text: str = Field(min_length=1)


class NormalizedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    document_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: SourceDefinition
    fetched_at: datetime
    sections: tuple[NormalizedSection, ...]


class ChunkingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "structural-v1"
    max_chars: int = Field(default=1_600, ge=400, le=8_000)
    overlap_chars: int = Field(default=160, ge=0, le=1_000)
    min_chars: int = Field(default=80, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkingPolicy":
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        return self


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: LogicalKnowledgeBase
    collection_version: str
    document_id: str
    document_version: str
    chunk_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str
    publisher: str
    canonical_url: str
    source_type: SourceType
    section_path: str
    effective_from: str | None = None
    effective_to: str | None = None
    tax_year: tuple[int, ...] = ()
    jurisdiction: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    fetched_at: datetime
    reviewed_at: datetime
    permitted_use: str
    status: SourceStatus
    text: str = Field(min_length=1)


class SparseEmbedding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    indices: tuple[int, ...]
    values: tuple[float, ...]

    @model_validator(mode="after")
    def validate_lengths(self) -> "SparseEmbedding":
        if len(self.indices) != len(self.values):
            raise ValueError("sparse indices and values must have the same length")
        return self


class EmbeddedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: KnowledgeChunk
    dense: tuple[float, ...]
    sparse: SparseEmbedding


class CollectionState(StrEnum):
    CANDIDATE = "candidate"
    READY = "ready"
    ACTIVE = "active"
    RETIRED = "retired"


class CollectionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    logical_kb: LogicalKnowledgeBase
    collection_name: str
    collection_version: str
    corpus_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_registry_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    dense_vector_name: str = "dense"
    dense_model_id: str
    dense_model_revision: str = DENSE_MODEL_REVISION
    dense_artifact_sha256: str = DENSE_MODEL_ARTIFACT_SHA256
    dense_dimensions: int = Field(gt=0)
    sparse_vector_name: str = "sparse"
    sparse_model_id: str
    sparse_model_revision: str = SPARSE_MODEL_REVISION
    sparse_artifact_sha256: str = SPARSE_MODEL_ARTIFACT_SHA256
    chunking_policy: ChunkingPolicy
    point_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    source_ids: tuple[str, ...]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: CollectionState = CollectionState.CANDIDATE
    ready: bool = False
    evaluation_artifact: str | None = None


class CollectionCompatibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    logical_kb: LogicalKnowledgeBase
    dense_vector_name: str = "dense"
    dense_model_id: str
    dense_model_revision: str = DENSE_MODEL_REVISION
    dense_artifact_sha256: str = DENSE_MODEL_ARTIFACT_SHA256
    dense_dimensions: int = Field(gt=0)
    sparse_vector_name: str = "sparse"
    sparse_model_id: str
    sparse_model_revision: str = SPARSE_MODEL_REVISION
    sparse_artifact_sha256: str = SPARSE_MODEL_ARTIFACT_SHA256
    chunking_policy_version: str = "structural-v1"


class RetrievalStrategy(StrEnum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class RetrievalFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: LogicalKnowledgeBase
    tax_year: int | None = None
    jurisdiction: str | None = None


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    filters: RetrievalFilter
    limit: int = Field(default=5, ge=1, le=50)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    document_id: str
    title: str
    publisher: str
    canonical_url: str
    section_path: str
    text: str
    score: float
    rank: int = Field(ge=1)
    collection_name: str
    collection_version: str
    document_version: str
    content_hash: str
    fetched_at: datetime
    tax_years: tuple[int, ...] = ()
    jurisdiction: str


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    query: str
    filters: RetrievalFilter
    expected_document_ids: tuple[str, ...]
    critical_filter: bool = False


class StrategyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: RetrievalStrategy
    recall_at_5: float = Field(ge=0, le=1)
    precision_at_5: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    logical_kb: LogicalKnowledgeBase
    collection_name: str
    qrels_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    top_k: int = 5
    qrels_case_count: int = Field(gt=0)
    metrics: tuple[StrategyMetrics, ...]
    critical_filters_exact: bool
    citation_integrity: bool
    failures: tuple[str, ...] = ()
    minimum_hybrid_recall_at_5: float = 0.85
    passed: bool
