"""Strict contracts for the versioned M8 qualification manifest and report."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationDimension(StrEnum):
    ROUTING = "EVAL-01"
    SPECIALIZATION = "EVAL-02"
    COLLABORATION = "EVAL-03"
    ARITHMETIC = "EVAL-04"
    PORTFOLIO_IMPORT = "EVAL-05"
    PROVENANCE = "EVAL-06"
    RETRIEVAL = "EVAL-07"
    CITATIONS = "EVAL-08"
    TAX_YEAR = "EVAL-09"
    GROUNDEDNESS = "EVAL-10"
    PROMPT_INJECTION = "EVAL-11"
    FINANCIAL_SAFETY = "EVAL-12"
    API_RELIABILITY = "EVAL-13"
    FRONTEND = "EVAL-14"
    INSPECTOR = "EVAL-15"
    REGRESSION = "EVAL-16"
    LATENCY_COST = "EVAL-17"
    PERSISTENCE_PRIVACY = "EVAL-18"


class ReviewStatus(StrEnum):
    AUTOMATED = "automated"
    APPROVED = "approved"
    PENDING = "pending"


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class DimensionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    REVIEW_REQUIRED = "review_required"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,127}$")
    dimension: EvaluationDimension
    critical: bool
    description: str = Field(min_length=1, max_length=512)
    check_ids: tuple[str, ...] = Field(min_length=1)
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.AUTOMATED

    @model_validator(mode="after")
    def reject_unsafe_paths(self) -> EvaluationCase:
        for path in self.evidence_paths:
            if path.startswith("/") or ".." in path.split("/"):
                raise ValueError("evidence paths must remain repository-relative")
        return self


class EvaluationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(pattern=r"^1$")
    dataset_version: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    cases: tuple[EvaluationCase, ...] = Field(min_length=18)

    @model_validator(mode="after")
    def validate_coverage(self) -> EvaluationManifest:
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case identifiers must be unique")
        covered = {case.dimension for case in self.cases}
        missing = set(EvaluationDimension) - covered
        if missing:
            labels = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"evaluation manifest is missing dimensions: {labels}")
        return self


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    status: CheckStatus
    command: tuple[str, ...]
    duration_seconds: float = Field(ge=0)
    exit_code: int | None
    output_tail: str = Field(max_length=8_000)


class DimensionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: EvaluationDimension
    status: DimensionStatus
    critical: bool
    case_ids: tuple[str, ...]
    missing_evidence_paths: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    not_run_check_ids: tuple[str, ...]
    pending_review_case_ids: tuple[str, ...]


class QualificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    dataset_version: str
    generated_at: datetime
    profile: str
    release_gate_passed: bool
    critical_failure_count: int = Field(ge=0)
    critical_incomplete_count: int = Field(ge=0)
    checks: tuple[CheckResult, ...]
    dimensions: tuple[DimensionResult, ...]
