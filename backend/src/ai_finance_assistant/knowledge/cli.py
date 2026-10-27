"""Command-line entry point for explicit M1 ingestion, activation, and rollback."""

import argparse
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_finance_assistant.knowledge.evaluation import evaluate_candidate
from ai_finance_assistant.knowledge.ingestion import OfflineIngestionService
from ai_finance_assistant.knowledge.models import (
    DENSE_MODEL_ARTIFACT_SHA256,
    DENSE_MODEL_REVISION,
    SPARSE_MODEL_ARTIFACT_SHA256,
    SPARSE_MODEL_REVISION,
    CollectionCompatibility,
    EvaluationCase,
    LogicalKnowledgeBase,
)
from ai_finance_assistant.knowledge.qdrant_store import QdrantKnowledgeStore
from ai_finance_assistant.knowledge.registry import (
    CachedSourceFetcher,
    HttpSourceFetcher,
    load_source_registry,
)
from ai_finance_assistant.knowledge.representations import FastEmbedEncoder
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REGISTRY = _BACKEND_ROOT / "data/knowledge/source_registry.v1.json"
_DEFAULT_ARTIFACTS = _BACKEND_ROOT / "artifacts/m1"
_DEFAULT_SOURCE_CACHE = _BACKEND_ROOT / ".cache/knowledge-sources"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_reference(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(_BACKEND_ROOT))
    except ValueError:
        return str(resolved)


def _next_run_path(artifacts_dir: Path, collection_name: str, recorded_at: datetime) -> Path:
    primary = artifacts_dir / f"{collection_name}.run.json"
    if not primary.exists():
        return primary
    timestamp = recorded_at.strftime("%Y%m%dT%H%M%S%fZ")
    return artifacts_dir / f"{collection_name}.run-{timestamp}.json"


def _load_qrels(path: Path) -> tuple[EvaluationCase, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("qrels file must contain a JSON list")
    return tuple(EvaluationCase.model_validate(item) for item in raw)


def _logical_kb(value: str) -> LogicalKnowledgeBase:
    return LogicalKnowledgeBase(value)


def _alias(logical_kb: LogicalKnowledgeBase) -> str:
    return f"{logical_kb.value}_active"


def _run(args: argparse.Namespace) -> int:
    logical_kb = _logical_kb(args.kb)
    registry = load_source_registry(args.registry)
    qrels = _load_qrels(args.qrels)
    if any(case.filters.logical_kb != logical_kb for case in qrels):
        raise ValueError("qrels logical knowledge base does not match --kb")

    store = QdrantKnowledgeStore(args.qdrant_url)
    encoder = FastEmbedEncoder()
    service = OfflineIngestionService(
        fetcher=CachedSourceFetcher(
            HttpSourceFetcher(), args.source_cache, refresh=args.refresh_sources
        ),
        encoder=encoder,
        store=store,
    )
    prepared = service.prepare(registry, logical_kb)
    write_result = service.ingest(prepared)
    final_manifest = write_result.manifest
    retriever = KnowledgeRetriever(store=store, encoder=encoder)
    report = evaluate_candidate(
        logical_kb=logical_kb,
        collection_name=prepared.manifest.collection_name,
        cases=qrels,
        retriever=retriever,
    )
    report_path = args.artifacts_dir / f"{prepared.manifest.collection_name}.evaluation.json"
    _write_json(report_path, report.model_dump(mode="json"))
    recorded_at = datetime.now(UTC)
    run_record: dict[str, Any] = {
        "schema_version": "1",
        "recorded_at": recorded_at.isoformat(),
        "collection_name": prepared.manifest.collection_name,
        "write": {
            "created": write_result.created,
            "points_written": write_result.points_written,
        },
        "evaluation_artifact": _artifact_reference(report_path),
        "evaluation_passed": report.passed,
        "activation_requested": args.activate,
    }
    if report.passed:
        final_manifest = store.mark_ready(
            prepared.manifest.collection_name,
            _artifact_reference(report_path),
        )
        if args.activate:
            activation = store.activate(_alias(logical_kb), prepared.manifest.collection_name)
            run_record["activation"] = {
                "alias": activation.alias,
                "active_collection": activation.active_collection,
                "previous_collection": activation.previous_collection,
            }
    _write_json(
        args.artifacts_dir / f"{prepared.manifest.collection_name}.manifest.json",
        {
            "manifest": final_manifest.model_dump(mode="json"),
            "documents": [
                {
                    "document_id": document.document_id,
                    "document_version": document.document_version,
                    "fetched_at": document.fetched_at.isoformat(),
                    "canonical_url": str(document.source.canonical_url),
                    "tax_years": list(document.source.tax_years),
                }
                for document in prepared.documents
            ],
        },
    )
    _write_json(
        _next_run_path(
            args.artifacts_dir,
            prepared.manifest.collection_name,
            recorded_at,
        ),
        run_record,
    )
    print(json.dumps(run_record, indent=2, sort_keys=True))
    return 0 if report.passed else 2


def _rollback(args: argparse.Namespace) -> int:
    logical_kb = _logical_kb(args.kb)
    store = QdrantKnowledgeStore(args.qdrant_url)
    result = store.activate(_alias(logical_kb), args.collection)
    record = {
        "schema_version": "1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "action": "rollback",
        "alias": result.alias,
        "active_collection": result.active_collection,
        "previous_collection": result.previous_collection,
    }
    _write_json(
        args.artifacts_dir
        / f"rollback-{logical_kb.value}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json",
        record,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def _validate(args: argparse.Namespace) -> int:
    logical_kb = _logical_kb(args.kb)
    compatible, detail = QdrantKnowledgeStore(args.qdrant_url).validate_active(
        _alias(logical_kb),
        CollectionCompatibility(
            logical_kb=logical_kb,
            dense_model_id="BAAI/bge-small-en-v1.5",
            dense_model_revision=DENSE_MODEL_REVISION,
            dense_artifact_sha256=DENSE_MODEL_ARTIFACT_SHA256,
            dense_dimensions=384,
            sparse_model_id="Qdrant/bm25",
            sparse_model_revision=SPARSE_MODEL_REVISION,
            sparse_artifact_sha256=SPARSE_MODEL_ARTIFACT_SHA256,
        ),
    )
    print(json.dumps({"compatible": compatible, "detail": detail}, indent=2))
    return 0 if compatible else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qdrant-url",
        default=os.getenv("AIFA_QDRANT_URL", "http://127.0.0.1:6333"),
    )
    parser.add_argument("--artifacts-dir", type=Path, default=_DEFAULT_ARTIFACTS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="ingest and evaluate one candidate")
    run_parser.add_argument(
        "--kb", required=True, choices=[item.value for item in LogicalKnowledgeBase]
    )
    run_parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY)
    run_parser.add_argument("--qrels", type=Path, required=True)
    run_parser.add_argument("--source-cache", type=Path, default=_DEFAULT_SOURCE_CACHE)
    run_parser.add_argument("--refresh-sources", action="store_true")
    run_parser.add_argument("--activate", action="store_true")
    run_parser.set_defaults(handler=_run)

    rollback_parser = subparsers.add_parser("rollback", help="atomically repoint an active alias")
    rollback_parser.add_argument(
        "--kb", required=True, choices=[item.value for item in LogicalKnowledgeBase]
    )
    rollback_parser.add_argument("--collection", required=True)
    rollback_parser.set_defaults(handler=_rollback)

    validate_parser = subparsers.add_parser("validate", help="validate one active alias")
    validate_parser.add_argument(
        "--kb", required=True, choices=[item.value for item in LogicalKnowledgeBase]
    )
    validate_parser.set_defaults(handler=_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
