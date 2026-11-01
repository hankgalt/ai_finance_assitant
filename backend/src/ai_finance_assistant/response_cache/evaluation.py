"""Frozen semantic-cache calibration without enabling serving."""

from __future__ import annotations

import argparse
import json
import math
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.knowledge.representations import (
    FastEmbedEncoder,
    RepresentationEncoder,
)


class CalibrationRelationship(StrEnum):
    EXACT = "exact"
    SAFE_PARAPHRASE = "safe_paraphrase"
    NEAR_MISS = "near_miss"
    ADVERSARIAL = "adversarial"


class HumanReview(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CalibrationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=128)
    agent_id: AgentId
    canonical_query: str = Field(min_length=1, max_length=20_000)
    candidate_query: str = Field(min_length=1, max_length=20_000)
    relationship: CalibrationRelationship
    route_eligible: bool
    exact_filters_match: bool = True
    expected_semantic_reuse: bool
    critical: bool
    human_review: HumanReview


class CalibrationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(pattern=r"^1$")
    dataset_version: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    cases: tuple[CalibrationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self) -> CalibrationDataset:
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("calibration case identifiers must be unique")
        return self


class CalibrationCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    relationship: CalibrationRelationship
    route_eligible: bool
    exact_filters_match: bool
    expected_semantic_reuse: bool
    similarity: float = Field(ge=-1.0, le=1.0)
    proposed_semantic_hit: bool
    critical_false_hit: bool
    human_review: HumanReview


class CalibrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    dataset_version: str
    encoder_model_id: str
    encoder_revision: str
    encoder_artifact_sha256: str
    minimum_similarity: float = Field(ge=0.0, le=1.0)
    case_count: int = Field(gt=0)
    eligible_case_count: int = Field(ge=0)
    proposed_semantic_hit_count: int = Field(ge=0)
    critical_false_hit_count: int = Field(ge=0)
    unreviewed_proposed_hit_count: int = Field(ge=0)
    serving_gate_passed: bool
    results: tuple[CalibrationCaseResult, ...]


def load_dataset(path: Path) -> CalibrationDataset:
    return CalibrationDataset.model_validate_json(path.read_text())


def evaluate_dataset(
    dataset: CalibrationDataset,
    *,
    encoder: RepresentationEncoder,
    minimum_similarity: float,
) -> CalibrationReport:
    if not 0.0 <= minimum_similarity <= 1.0:
        raise ValueError("minimum_similarity must be between zero and one")
    texts = tuple(
        text for case in dataset.cases for text in (case.canonical_query, case.candidate_query)
    )
    vectors = encoder.embed_dense(texts)
    results: list[CalibrationCaseResult] = []
    for index, case in enumerate(dataset.cases):
        similarity = _cosine(vectors[index * 2], vectors[index * 2 + 1])
        proposed_hit = bool(
            case.relationship != CalibrationRelationship.EXACT
            and case.route_eligible
            and case.exact_filters_match
            and similarity >= minimum_similarity
        )
        critical_false_hit = bool(
            case.critical and proposed_hit and not case.expected_semantic_reuse
        )
        results.append(
            CalibrationCaseResult(
                case_id=case.case_id,
                relationship=case.relationship,
                route_eligible=case.route_eligible,
                exact_filters_match=case.exact_filters_match,
                expected_semantic_reuse=case.expected_semantic_reuse,
                similarity=similarity,
                proposed_semantic_hit=proposed_hit,
                critical_false_hit=critical_false_hit,
                human_review=case.human_review,
            )
        )
    proposed = tuple(item for item in results if item.proposed_semantic_hit)
    false_hits = tuple(item for item in results if item.critical_false_hit)
    unreviewed = tuple(item for item in proposed if item.human_review != HumanReview.APPROVED)
    return CalibrationReport(
        dataset_version=dataset.dataset_version,
        encoder_model_id=encoder.dense_model_id,
        encoder_revision=encoder.dense_model_revision,
        encoder_artifact_sha256=encoder.dense_artifact_sha256,
        minimum_similarity=minimum_similarity,
        case_count=len(results),
        eligible_case_count=sum(item.route_eligible for item in results),
        proposed_semantic_hit_count=len(proposed),
        critical_false_hit_count=len(false_hits),
        unreviewed_proposed_hit_count=len(unreviewed),
        serving_gate_passed=not false_hits and not unreviewed,
        results=tuple(results),
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(first * second for first, second in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen response-cache calibration cases")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--minimum-similarity", type=float, required=True)
    args = parser.parse_args()
    report = evaluate_dataset(
        load_dataset(args.cases),
        encoder=FastEmbedEncoder(),
        minimum_similarity=args.minimum_similarity,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
