from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_finance_assistant.contracts.events import EventStatus, EventType
from ai_finance_assistant.core.redaction import sanitize_metadata
from ai_finance_assistant.evaluation.models import (
    CheckResult,
    CheckStatus,
    DimensionStatus,
    EvaluationDimension,
    EvaluationManifest,
    ReviewStatus,
)
from ai_finance_assistant.evaluation.runner import CHECK_SPECS, build_report, load_manifest
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.observability.ports import NoOpObservability
from ai_finance_assistant.observability.safe import safe_attributes
from ai_finance_assistant.workflow.events import (
    EventIdentity,
    InMemoryRunEventRepository,
    RunEventRecorder,
)

ROOT = Path(__file__).parents[2]
MANIFEST_PATH = ROOT / "backend" / "data" / "evaluation" / "m8_cases.v1.json"
SECURITY_PATH = ROOT / "backend" / "data" / "evaluation" / "security_cases.v1.json"


def _passed_checks() -> tuple[CheckResult, ...]:
    return tuple(
        CheckResult(
            check_id=spec.check_id,
            status=CheckStatus.PASSED,
            command=spec.command,
            duration_seconds=0.01,
            exit_code=0,
            output_tail="passed",
        )
        for spec in CHECK_SPECS
    )


def test_m8_manifest_covers_every_dimension_and_references_real_evidence() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert {case.dimension for case in manifest.cases} == set(EvaluationDimension)
    assert all(case.critical for case in manifest.cases)
    assert all((ROOT / path).is_file() for case in manifest.cases for path in case.evidence_paths)
    known_checks = {spec.check_id for spec in CHECK_SPECS}
    assert all(set(case.check_ids) <= known_checks for case in manifest.cases)


def test_m8_manifest_rejects_path_traversal() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["cases"][0]["evidence_paths"] = ["../outside.txt"]

    with pytest.raises(ValidationError, match="repository-relative"):
        EvaluationManifest.model_validate(payload)


def test_m8_approved_manifest_passes_release_gate() -> None:
    report = build_report(
        load_manifest(MANIFEST_PATH),
        profile="full",
        repo_root=ROOT,
        checks=_passed_checks(),
    )

    assert all(item.status == DimensionStatus.PASSED for item in report.dimensions)
    assert report.release_gate_passed
    assert report.critical_failure_count == 0
    assert report.critical_incomplete_count == 0


def test_m8_report_keeps_pending_human_review_visible_and_blocks_release() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    review_case_ids = {
        "live-model-routing-review",
        "live-model-synthesis-review",
        "citation-claim-support-review",
        "generated-answer-groundedness-review",
        "financial-safety-human-review",
        "response-cache-latency-cost-safety",
    }
    pending_manifest = manifest.model_copy(
        update={
            "cases": tuple(
                case.model_copy(update={"review_status": ReviewStatus.PENDING})
                if case.case_id in review_case_ids
                else case
                for case in manifest.cases
            )
        }
    )
    report = build_report(
        pending_manifest,
        profile="full",
        repo_root=ROOT,
        checks=_passed_checks(),
    )

    by_dimension = {item.dimension: item for item in report.dimensions}
    assert by_dimension[EvaluationDimension.ROUTING].status == DimensionStatus.REVIEW_REQUIRED
    assert by_dimension[EvaluationDimension.COLLABORATION].status == DimensionStatus.REVIEW_REQUIRED
    assert by_dimension[EvaluationDimension.CITATIONS].status == DimensionStatus.REVIEW_REQUIRED
    assert by_dimension[EvaluationDimension.GROUNDEDNESS].status == DimensionStatus.REVIEW_REQUIRED
    assert (
        by_dimension[EvaluationDimension.FINANCIAL_SAFETY].status == DimensionStatus.REVIEW_REQUIRED
    )
    assert by_dimension[EvaluationDimension.LATENCY_COST].status == DimensionStatus.REVIEW_REQUIRED
    assert not report.release_gate_passed
    assert report.critical_failure_count == 0
    assert report.critical_incomplete_count == 6


def test_security_dataset_is_versioned_and_bound_to_automated_seams() -> None:
    dataset = json.loads(SECURITY_PATH.read_text(encoding="utf-8"))
    cases = dataset["cases"]

    assert dataset["schema_version"] == "1"
    assert len(cases) >= 12
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {
        "prompt_injection",
        "safe_file",
        "access_isolation",
        "observability_redaction",
        "observability_cardinality",
        "reliability",
    } <= {case["category"] for case in cases}
    for case in cases:
        test_path, separator, test_name = case["automated_test"].partition("::")
        assert separator == "::"
        source_path = ROOT / test_path
        assert source_path.is_file()
        assert f"def {test_name}(" in source_path.read_text(encoding="utf-8")


def test_cache_events_retain_bounded_dimensions_without_raw_reason_or_context() -> None:
    metadata = sanitize_metadata(
        {
            "operation": "generation_lookup",
            "outcome": "hit",
            "match_kind": "semantic",
            "policy_version": "response-cache-policy-v1",
            "semantic_mode": "shadow",
            "avoided_model_request": True,
            "similarity_bucket": "0.95_to_0.98",
            "entry_age_bucket": "1m_to_1h",
            "reason": "unbounded internal detail",
            "session_id": "session-private",
            "message": "private question",
        }
    )

    assert metadata == {
        "operation": "generation_lookup",
        "outcome": "hit",
        "match_kind": "semantic",
        "policy_version": "response-cache-policy-v1",
        "semantic_mode": "shadow",
        "avoided_model_request": True,
        "similarity_bucket": "0.95_to_0.98",
        "entry_age_bucket": "1m_to_1h",
    }
    assert safe_attributes(metadata) == {
        "operation": "generation_lookup",
        "outcome": "hit",
        "match_kind": "semantic",
        "policy_version": "response-cache-policy-v1",
        "semantic_mode": "shadow",
    }


def test_run_event_sequences_remain_unique_under_bounded_concurrency() -> None:
    repository = InMemoryRunEventRepository()
    recorder = RunEventRecorder(repository=repository, observability=NoOpObservability())
    identity = EventIdentity(
        execution_id="run-m8-concurrent",
        session_id="session-m8-concurrent",
        workflow_id="finance-assistant",
        workflow_version="1",
    )

    def record(index: int) -> None:
        recorder.record(
            identity,
            event_type=EventType.NODE_COMPLETED,
            status=EventStatus.COMPLETED,
            node_id=f"node-{index}",
            summary="Bounded concurrency event.",
            completed=True,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        tuple(executor.map(record, range(128)))

    events = repository.list_for_run(
        "run-m8-concurrent",
        session_id="session-m8-concurrent",
    )
    assert tuple(event.sequence for event in events) == tuple(range(1, 129))
    assert len({event.event_id for event in events}) == 128


def test_metric_attributes_reject_session_cardinality_and_sensitive_canary() -> None:
    telemetry = InMemoryObservability()
    canary = "M8-DO-NOT-EXPORT"
    for index in range(128):
        telemetry.count(
            "backend.http.requests",
            1,
            {
                "route": "/api/v1/sessions/{session_id}/runs",
                "http_method": "POST",
                "status_class": "2xx",
                "session_id": f"session-{index}",
                "prompt": canary,
                "message": canary,
                "token": canary,
            },
        )

    dimensions = {tuple(sorted(metric.attributes.items())) for metric in telemetry.metrics}
    serialized = json.dumps([metric.attributes for metric in telemetry.metrics])
    assert len(dimensions) == 1
    assert canary not in serialized
    assert "session-" not in serialized
