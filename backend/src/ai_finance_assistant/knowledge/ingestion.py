"""Deterministic offline ingestion from reviewed sources to candidate records."""

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO

from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader

from ai_finance_assistant.knowledge.models import (
    ChunkingPolicy,
    CollectionManifest,
    EmbeddedChunk,
    FetchedSource,
    KnowledgeChunk,
    LogicalKnowledgeBase,
    NormalizedDocument,
    NormalizedSection,
    SourceDefinition,
    SourceRegistry,
)
from ai_finance_assistant.knowledge.registry import SourceFetcher, registry_checksum
from ai_finance_assistant.knowledge.representations import RepresentationEncoder
from ai_finance_assistant.knowledge.store import CandidateWriteResult, KnowledgeStore

_WHITESPACE = re.compile(r"\s+")


def _sha256(value: str | bytes) -> str:
    data = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def normalize_html(source: SourceDefinition, fetched: FetchedSource) -> NormalizedDocument:
    """Extract heading-aware content while excluding active and navigational elements."""

    soup = BeautifulSoup(fetched.body, "html.parser")
    for unwanted in soup.select(
        "script, style, noscript, svg, nav, footer, form, button, [aria-hidden='true']"
    ):
        unwanted.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    heading_path: list[str] = [source.title]
    sections: list[NormalizedSection] = []
    for element in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        if not isinstance(element, Tag):
            continue
        text = _WHITESPACE.sub(" ", element.get_text(" ", strip=True)).strip()
        if not text:
            continue
        if element.name and element.name.startswith("h"):
            level = int(element.name[1])
            heading_path = [*heading_path[: max(1, level - 1)], text]
            continue
        if len(text) < 20:
            continue
        sections.append(NormalizedSection(path=" > ".join(heading_path), text=text))

    if not sections:
        raise ValueError(f"source {source.source_id} had no substantive extractable content")

    canonical = json.dumps(
        [section.model_dump(mode="json") for section in sections],
        sort_keys=True,
        separators=(",", ":"),
    )
    return NormalizedDocument(
        document_id=source.source_id,
        document_version=_sha256(canonical),
        source=source,
        fetched_at=fetched.fetched_at,
        sections=tuple(sections),
    )


def normalize_pdf(source: SourceDefinition, fetched: FetchedSource) -> NormalizedDocument:
    """Extract page-bounded PDF text without executing embedded content."""

    reader = PdfReader(BytesIO(fetched.body), strict=True)
    sections: list[NormalizedSection] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = _WHITESPACE.sub(" ", page.extract_text(extraction_mode="layout") or "").strip()
        if len(text) < 20:
            continue
        sections.append(NormalizedSection(path=f"{source.title} > Page {page_number}", text=text))
    if not sections:
        raise ValueError(f"source {source.source_id} had no substantive extractable PDF content")
    canonical = json.dumps(
        [section.model_dump(mode="json") for section in sections],
        sort_keys=True,
        separators=(",", ":"),
    )
    return NormalizedDocument(
        document_id=source.source_id,
        document_version=_sha256(canonical),
        source=source,
        fetched_at=fetched.fetched_at,
        sections=tuple(sections),
    )


def normalize_source(source: SourceDefinition, fetched: FetchedSource) -> NormalizedDocument:
    if source.source_type.value == "html":
        return normalize_html(source, fetched)
    if source.source_type.value == "pdf":
        return normalize_pdf(source, fetched)
    raise ValueError(f"unsupported source type {source.source_type}")


def _window_text(text: str, policy: ChunkingPolicy) -> list[str]:
    if len(text) <= policy.max_chars:
        return [text]
    windows: list[str] = []
    start = 0
    while start < len(text):
        target_end = min(start + policy.max_chars, len(text))
        end = target_end
        if target_end < len(text):
            boundary = max(text.rfind(". ", start, target_end), text.rfind(" ", start, target_end))
            if boundary > start + policy.min_chars:
                end = boundary + 1
        window = text[start:end].strip()
        if window:
            windows.append(window)
        if end >= len(text):
            break
        start = max(end - policy.overlap_chars, start + 1)
    return windows


def chunk_document(
    document: NormalizedDocument,
    *,
    collection_version: str,
    policy: ChunkingPolicy,
) -> tuple[KnowledgeChunk, ...]:
    """Group adjacent structural blocks, then apply bounded sentence-aware windows."""

    grouped: dict[str, list[str]] = defaultdict(list)
    path_order: list[str] = []
    for section in document.sections:
        if section.path not in grouped:
            path_order.append(section.path)
        grouped[section.path].append(section.text)

    chunks: list[KnowledgeChunk] = []
    for path in path_order:
        combined = "\n\n".join(grouped[path])
        for ordinal, text in enumerate(_window_text(combined, policy)):
            if len(text) < policy.min_chars and chunks:
                continue
            content_hash = _sha256(text)
            chunk_id = _sha256(
                f"{document.document_id}:{document.document_version}:{path}:{ordinal}:{content_hash}"
            )
            chunks.append(
                KnowledgeChunk(
                    logical_kb=document.source.logical_kb,
                    collection_version=collection_version,
                    document_id=document.document_id,
                    document_version=document.document_version,
                    chunk_id=chunk_id,
                    title=document.source.title,
                    publisher=document.source.publisher,
                    canonical_url=str(document.source.canonical_url),
                    source_type=document.source.source_type,
                    section_path=path,
                    tax_year=document.source.tax_years,
                    jurisdiction=document.source.jurisdiction,
                    content_hash=content_hash,
                    fetched_at=document.fetched_at,
                    reviewed_at=document.source.permitted_use.reviewed_at,
                    permitted_use=document.source.permitted_use.basis,
                    status=document.source.status,
                    text=text,
                )
            )
    return tuple(chunks)


@dataclass(frozen=True)
class PreparedCorpus:
    manifest: CollectionManifest
    documents: tuple[NormalizedDocument, ...]
    chunks: tuple[KnowledgeChunk, ...]


class OfflineIngestionService:
    """Coordinates the complete write-side workflow; runtime code never calls it."""

    def __init__(
        self,
        *,
        fetcher: SourceFetcher,
        encoder: RepresentationEncoder,
        store: KnowledgeStore,
        chunking_policy: ChunkingPolicy | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._encoder = encoder
        self._store = store
        self._chunking_policy = chunking_policy or ChunkingPolicy()

    def prepare(self, registry: SourceRegistry, logical_kb: LogicalKnowledgeBase) -> PreparedCorpus:
        sources = tuple(
            source
            for source in registry.sources
            if source.logical_kb == logical_kb and source.ingestion_enabled
        )
        if not sources:
            raise ValueError(f"no approved, enabled sources for {logical_kb}")

        documents_by_version: dict[str, NormalizedDocument] = {}
        for source in sources:
            fetched = self._fetcher.fetch(source)
            document = normalize_source(source, fetched)
            documents_by_version.setdefault(document.document_version, document)
        documents = tuple(sorted(documents_by_version.values(), key=lambda item: item.document_id))

        corpus_material = {
            "documents": [(doc.document_id, doc.document_version) for doc in documents],
            "enabled_sources": [source.model_dump(mode="json") for source in sources],
            "policy": self._chunking_policy.model_dump(mode="json"),
            "dense_model": self._encoder.dense_model_id,
            "dense_model_revision": self._encoder.dense_model_revision,
            "dense_artifact_sha256": self._encoder.dense_artifact_sha256,
            "sparse_model": self._encoder.sparse_model_id,
            "sparse_model_revision": self._encoder.sparse_model_revision,
            "sparse_artifact_sha256": self._encoder.sparse_artifact_sha256,
            "schema": "1",
        }
        corpus_checksum = _sha256(
            json.dumps(corpus_material, sort_keys=True, separators=(",", ":"))
        )
        collection_version = f"v1-{corpus_checksum[:12]}"
        chunks = tuple(
            chunk
            for document in documents
            for chunk in chunk_document(
                document,
                collection_version=collection_version,
                policy=self._chunking_policy,
            )
        )
        collection_name = f"{logical_kb.value}_{collection_version.replace('-', '_')}"
        manifest = CollectionManifest(
            logical_kb=logical_kb,
            collection_name=collection_name,
            collection_version=collection_version,
            corpus_checksum=corpus_checksum,
            source_registry_checksum=registry_checksum(registry),
            dense_model_id=self._encoder.dense_model_id,
            dense_model_revision=self._encoder.dense_model_revision,
            dense_artifact_sha256=self._encoder.dense_artifact_sha256,
            dense_dimensions=self._encoder.dense_dimensions,
            sparse_model_id=self._encoder.sparse_model_id,
            sparse_model_revision=self._encoder.sparse_model_revision,
            sparse_artifact_sha256=self._encoder.sparse_artifact_sha256,
            chunking_policy=self._chunking_policy,
            point_count=len(chunks),
            document_count=len(documents),
            source_ids=tuple(document.document_id for document in documents),
        )
        return PreparedCorpus(manifest=manifest, documents=documents, chunks=chunks)

    def ingest(self, prepared: PreparedCorpus) -> CandidateWriteResult:
        existing = self._store.get_manifest(prepared.manifest.collection_name)
        if existing is not None:
            if existing.corpus_checksum != prepared.manifest.corpus_checksum:
                raise ValueError("collection name collision with a different corpus checksum")
            if self._store.count_points(prepared.manifest.collection_name) == existing.point_count:
                return CandidateWriteResult(manifest=existing, created=False, points_written=0)

        dense = self._encoder.embed_dense([chunk.text for chunk in prepared.chunks])
        sparse = self._encoder.embed_sparse([chunk.text for chunk in prepared.chunks])
        if len(dense) != len(prepared.chunks) or len(sparse) != len(prepared.chunks):
            raise ValueError("encoder returned an unexpected number of embeddings")
        embedded = tuple(
            EmbeddedChunk(chunk=chunk, dense=tuple(dense_vector), sparse=sparse_vector)
            for chunk, dense_vector, sparse_vector in zip(
                prepared.chunks, dense, sparse, strict=True
            )
        )
        return self._store.write_candidate(prepared.manifest, embedded)


def document_versions(documents: Iterable[NormalizedDocument]) -> dict[str, str]:
    return {document.document_id: document.document_version for document in documents}
