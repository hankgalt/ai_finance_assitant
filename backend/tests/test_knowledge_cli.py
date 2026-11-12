"""Explicit knowledge CLI run, rollback, and validate commands with deterministic adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import HttpUrl, TypeAdapter

from ai_finance_assistant.knowledge import cli as knowledge_cli
from ai_finance_assistant.knowledge.memory_store import InMemoryKnowledgeStore
from ai_finance_assistant.knowledge.models import (
    EvaluationCase,
    LogicalKnowledgeBase,
    PermittedUse,
    RetrievalFilter,
    SourceDefinition,
    SourceRegistry,
    SourceStatus,
    SourceType,
)
from ai_finance_assistant.knowledge.registry import FixtureSourceFetcher
from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder

REVIEWED_AT = datetime(2026, 10, 27, tzinfo=UTC)
_http_url = TypeAdapter(HttpUrl)


def _source(source_id: str, title: str) -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        logical_kb=LogicalKnowledgeBase.FINANCE,
        title=title,
        publisher="Example Federal Agency",
        canonical_url=_http_url.validate_python(f"https://example.gov/{source_id}"),
        source_type=SourceType.HTML,
        jurisdiction="US-Federal",
        status=SourceStatus.APPROVED,
        permitted_use=PermittedUse(
            basis="United States government work; source review recorded.",
            reviewer="repository-owner",
            ai_processing_allowed=True,
            redistribution_allowed=True,
            attribution_required=True,
            restrictions=("Do not imply agency endorsement.",),
            reviewed_at=REVIEWED_AT,
        ),
        ingestion_enabled=True,
    )


def _html(text: str) -> bytes:
    return f"<html><body><main><h1>Learning</h1><p>{text}</p></main></body></html>".encode()


BODIES = {
    "index-funds": _html(
        "Index funds hold the securities in a market benchmark and usually charge low fees."
    ),
    "bond-basics": _html(
        "Bonds are loans to an issuer that pay periodic interest and return principal."
    ),
}


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> InMemoryKnowledgeStore:
    shared = InMemoryKnowledgeStore()
    urls: list[str] = []

    def store_factory(url: str, **kwargs: object) -> InMemoryKnowledgeStore:
        urls.append(url)
        shared.api_key = kwargs.get("api_key")  # type: ignore[attr-defined]
        return shared

    monkeypatch.setattr(knowledge_cli, "QdrantKnowledgeStore", store_factory)
    monkeypatch.setattr(knowledge_cli, "FastEmbedEncoder", DeterministicTestEncoder)
    monkeypatch.setattr(knowledge_cli, "HttpSourceFetcher", lambda: FixtureSourceFetcher(BODIES))
    registry = SourceRegistry(
        reviewed_at=REVIEWED_AT,
        sources=(_source("index-funds", "Index Funds"), _source("bond-basics", "Bond Basics")),
    )
    (tmp_path / "registry.json").write_text(registry.model_dump_json(), encoding="utf-8")
    shared.urls = urls  # type: ignore[attr-defined]
    return shared


def _qrels(
    path: Path, expected: str, *, kb: LogicalKnowledgeBase = LogicalKnowledgeBase.FINANCE
) -> Path:
    case = EvaluationCase(
        case_id="index-fund-fees",
        query="index funds benchmark low fees",
        filters=RetrievalFilter(logical_kb=kb),
        expected_document_ids=(expected,),
    )
    path.write_text(json.dumps([case.model_dump(mode="json")]), encoding="utf-8")
    return path


def _run_args(tmp_path: Path, qrels: Path, *extra: str) -> list[str]:
    return [
        "--qdrant-url",
        "http://qdrant.invalid:6333",
        "--artifacts-dir",
        str(tmp_path / "artifacts"),
        "run",
        "--kb",
        "finance_education",
        "--registry",
        str(tmp_path / "registry.json"),
        "--qrels",
        str(qrels),
        "--source-cache",
        str(tmp_path / "cache"),
        *extra,
    ]


def test_run_evaluates_records_evidence_and_activates_passing_candidate(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qrels = _qrels(tmp_path / "qrels.json", "index-funds")

    exit_code = knowledge_cli.main(_run_args(tmp_path, qrels, "--activate"))

    record = json.loads(capsys.readouterr().out)
    artifacts = tmp_path / "artifacts" / "finance-education"
    collection = record["collection_name"]
    manifest = json.loads((artifacts / f"{collection}.manifest.json").read_text())
    assert exit_code == 0
    assert record["evaluation_passed"] is True
    assert record["write"] == {"created": True, "points_written": record["write"]["points_written"]}
    assert record["activation"]["alias"] == "finance_education_active"
    assert record["activation"]["previous_collection"] is None
    assert store.resolve_alias("finance_education_active") == collection
    assert manifest["manifest"]["ready"] is True
    assert {item["document_id"] for item in manifest["documents"]} == {"index-funds", "bond-basics"}
    assert (artifacts / f"{collection}.evaluation.json").exists()
    assert (artifacts / f"{collection}.run.json").exists()
    assert sorted(path.name for path in (tmp_path / "cache").iterdir()) == [
        "bond-basics.bin",
        "bond-basics.json",
        "index-funds.bin",
        "index-funds.json",
    ]
    assert store.urls == ["http://qdrant.invalid:6333"]  # type: ignore[attr-defined]


def test_run_without_activate_keeps_alias_unchanged(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qrels = _qrels(tmp_path / "qrels.json", "index-funds")

    exit_code = knowledge_cli.main(_run_args(tmp_path, qrels))

    record = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "activation" not in record
    assert store.resolve_alias("finance_education_active") is None


def test_failed_evaluation_returns_nonzero_and_never_activates(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qrels = _qrels(tmp_path / "qrels.json", "missing-document")

    exit_code = knowledge_cli.main(_run_args(tmp_path, qrels, "--activate"))

    record = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert record["evaluation_passed"] is False
    assert "activation" not in record
    assert store.resolve_alias("finance_education_active") is None
    assert store.get_manifest(record["collection_name"]).ready is False  # type: ignore[union-attr]


def test_run_rejects_qrels_for_another_knowledge_base(
    store: InMemoryKnowledgeStore, tmp_path: Path
) -> None:
    del store
    qrels = _qrels(tmp_path / "qrels.json", "index-funds", kb=LogicalKnowledgeBase.TAX)

    with pytest.raises(ValueError, match="does not match --kb"):
        knowledge_cli.main(_run_args(tmp_path, qrels))


def test_qrels_must_be_a_json_list(store: InMemoryKnowledgeStore, tmp_path: Path) -> None:
    del store
    path = tmp_path / "qrels.json"
    path.write_text('{"case_id": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON list"):
        knowledge_cli.main(_run_args(tmp_path, path))


def test_rollback_repoints_alias_and_records_evidence(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    knowledge_cli.main(_run_args(tmp_path, _qrels(tmp_path / "qrels.json", "index-funds")))
    collection = json.loads(capsys.readouterr().out)["collection_name"]

    exit_code = knowledge_cli.main(
        [
            "--artifacts-dir",
            str(tmp_path / "artifacts"),
            "rollback",
            "--kb",
            "finance_education",
            "--collection",
            collection,
        ]
    )

    record = json.loads(capsys.readouterr().out)
    rollback_files = list((tmp_path / "artifacts" / "finance-education" / "rollback").iterdir())
    assert exit_code == 0
    assert record["action"] == "rollback"
    assert record["active_collection"] == collection
    assert store.resolve_alias("finance_education_active") == collection
    assert len(rollback_files) == 1


def test_validate_reports_missing_and_incompatible_active_collections(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    validate = ["validate", "--kb", "finance_education"]

    missing_code = knowledge_cli.main(validate)
    missing = json.loads(capsys.readouterr().out)
    knowledge_cli.main(
        _run_args(tmp_path, _qrels(tmp_path / "qrels.json", "index-funds"), "--activate")
    )
    capsys.readouterr()
    incompatible_code = knowledge_cli.main(validate)
    incompatible = json.loads(capsys.readouterr().out)

    assert (missing_code, missing) == (
        2,
        {"compatible": False, "detail": "active alias is missing"},
    )
    assert incompatible_code == 2
    assert incompatible["compatible"] is False
    assert "dense_model_id" in incompatible["detail"]
    assert store.resolve_alias("finance_education_active") is not None


def test_artifact_reference_is_backend_relative_when_possible(tmp_path: Path) -> None:
    reference = vars(knowledge_cli)["_artifact_reference"]

    assert reference(knowledge_cli._DEFAULT_ARTIFACTS / "x.json") == "artifacts/knowledge/x.json"
    assert reference(tmp_path / "x.json") == str((tmp_path / "x.json").resolve())


def test_api_key_is_read_from_file_and_passed_without_cli_payload(
    store: InMemoryKnowledgeStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api_key_file = tmp_path / "api-key"
    api_key_file.write_text("secret-token", encoding="utf-8")

    exit_code = knowledge_cli.main(
        [
            "--qdrant-api-key-file",
            str(api_key_file),
            "validate",
            "--kb",
            "finance_education",
        ]
    )

    assert exit_code == 2
    assert store.api_key == "secret-token"  # type: ignore[attr-defined]
    assert "secret-token" not in capsys.readouterr().out


def test_api_key_file_rejects_empty_or_multiline_values(tmp_path: Path) -> None:
    api_key_file = tmp_path / "api-key"
    api_key_file.write_text("first\nsecond", encoding="utf-8")

    with pytest.raises(ValueError, match="one non-empty token"):
        knowledge_cli.main(
            [
                "--qdrant-api-key-file",
                str(api_key_file),
                "validate",
                "--kb",
                "finance_education",
            ]
        )
