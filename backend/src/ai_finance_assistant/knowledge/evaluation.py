"""Fixed-qrels retrieval evaluation and candidate activation gate."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from ai_finance_assistant.knowledge.models import (
    EvaluationCase,
    EvaluationReport,
    LogicalKnowledgeBase,
    RetrievalQuery,
    RetrievalStrategy,
    StrategyMetrics,
)
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever


@dataclass(frozen=True)
class _CaseScore:
    recall: float
    precision: float
    reciprocal_rank: float


def qrels_checksum(cases: Sequence[EvaluationCase]) -> str:
    serialized = json.dumps(
        [case.model_dump(mode="json") for case in cases],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def evaluate_candidate(
    *,
    logical_kb: LogicalKnowledgeBase,
    collection_name: str,
    cases: Sequence[EvaluationCase],
    retriever: KnowledgeRetriever,
    minimum_hybrid_recall_at_5: float = 0.85,
) -> EvaluationReport:
    if not cases:
        raise ValueError("evaluation requires at least one qrel case")

    metrics: list[StrategyMetrics] = []
    critical_filters_exact = True
    citation_integrity = True
    failures: list[str] = []
    for strategy in RetrievalStrategy:
        case_scores: list[_CaseScore] = []
        for case in cases:
            evidence = retriever.retrieve(
                collection_name,
                RetrievalQuery(
                    text=case.query,
                    strategy=strategy,
                    filters=case.filters,
                    limit=5,
                ),
            )
            returned_documents = [item.document_id for item in evidence]
            relevant = set(case.expected_document_ids)
            found = relevant.intersection(returned_documents)
            recall = len(found) / len(relevant)
            precision = sum(document_id in relevant for document_id in returned_documents) / 5
            first_relevant = next(
                (
                    rank
                    for rank, document_id in enumerate(returned_documents, start=1)
                    if document_id in relevant
                ),
                None,
            )
            case_scores.append(
                _CaseScore(
                    recall=recall,
                    precision=precision,
                    reciprocal_rank=0.0 if first_relevant is None else 1.0 / first_relevant,
                )
            )
            if case.critical_filter:
                exact = bool(evidence) and all(
                    (case.filters.tax_year is None or case.filters.tax_year in item.tax_years)
                    and (
                        case.filters.jurisdiction is None
                        or case.filters.jurisdiction == item.jurisdiction
                    )
                    for item in evidence
                )
                if not exact:
                    critical_filters_exact = False
                    failures.append(f"{strategy}:{case.case_id}:filter")
            citations_valid = all(
                item.chunk_id
                and item.document_id
                and item.canonical_url.startswith("https://")
                and item.content_hash
                for item in evidence
            )
            if not citations_valid:
                citation_integrity = False
                failures.append(f"{strategy}:{case.case_id}:citation")

        denominator = len(case_scores)
        metrics.append(
            StrategyMetrics(
                strategy=strategy,
                recall_at_5=sum(score.recall for score in case_scores) / denominator,
                precision_at_5=sum(score.precision for score in case_scores) / denominator,
                mean_reciprocal_rank=(
                    sum(score.reciprocal_rank for score in case_scores) / denominator
                ),
            )
        )

    hybrid = next(metric for metric in metrics if metric.strategy == RetrievalStrategy.HYBRID)
    if hybrid.recall_at_5 < minimum_hybrid_recall_at_5:
        failures.append(
            f"hybrid:recall_at_5:{hybrid.recall_at_5:.3f}<{minimum_hybrid_recall_at_5:.3f}"
        )
    passed = (
        hybrid.recall_at_5 >= minimum_hybrid_recall_at_5
        and critical_filters_exact
        and citation_integrity
    )
    return EvaluationReport(
        logical_kb=logical_kb,
        collection_name=collection_name,
        qrels_checksum=qrels_checksum(cases),
        qrels_case_count=len(cases),
        metrics=tuple(metrics),
        critical_filters_exact=critical_filters_exact,
        citation_integrity=citation_integrity,
        minimum_hybrid_recall_at_5=minimum_hybrid_recall_at_5,
        passed=passed,
        failures=tuple(failures),
    )
