"""Runtime knowledge-retrieval interface and adapters."""

from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ai_finance_assistant.knowledge.models import (
    Evidence,
    LogicalKnowledgeBase,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalStrategy,
)
from ai_finance_assistant.knowledge.retrieval import KnowledgeRetriever


def _canonical_jurisdiction(
    logical_kb: LogicalKnowledgeBase,
    jurisdiction: str,
) -> str:
    if jurisdiction == "US" and logical_kb in {
        LogicalKnowledgeBase.FINANCE,
        LogicalKnowledgeBase.TAX,
    }:
        return "US-Federal"
    return jurisdiction


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_kb: LogicalKnowledgeBase
    strategy: RetrievalStrategy
    evidence: tuple[Evidence, ...]


class KnowledgeRetrieval(Protocol):
    def retrieve(
        self,
        *,
        logical_kb: LogicalKnowledgeBase,
        text: str,
        tax_year: int | None = None,
        jurisdiction: str = "US",
        limit: int = 5,
    ) -> RetrievalResult: ...


class ActiveKnowledgeRetrieval:
    def __init__(
        self,
        *,
        retriever: KnowledgeRetriever,
        aliases: Mapping[LogicalKnowledgeBase, str],
    ) -> None:
        self._retriever = retriever
        self._aliases = dict(aliases)

    def retrieve(
        self,
        *,
        logical_kb: LogicalKnowledgeBase,
        text: str,
        tax_year: int | None = None,
        jurisdiction: str = "US",
        limit: int = 5,
    ) -> RetrievalResult:
        strategy = RetrievalStrategy.HYBRID
        canonical_jurisdiction = _canonical_jurisdiction(logical_kb, jurisdiction)
        query = RetrievalQuery(
            text=text,
            strategy=strategy,
            filters=RetrievalFilter(
                logical_kb=logical_kb,
                tax_year=tax_year,
                jurisdiction=canonical_jurisdiction,
            ),
            limit=limit,
        )
        return RetrievalResult(
            logical_kb=logical_kb,
            strategy=strategy,
            evidence=self._retriever.retrieve(self._aliases[logical_kb], query),
        )


class StaticKnowledgeRetrieval:
    """Deterministic adapter for tests and credential-free demonstrations."""

    def __init__(self, evidence: Mapping[LogicalKnowledgeBase, tuple[Evidence, ...]]) -> None:
        self._evidence = dict(evidence)

    def retrieve(
        self,
        *,
        logical_kb: LogicalKnowledgeBase,
        text: str,
        tax_year: int | None = None,
        jurisdiction: str = "US",
        limit: int = 5,
    ) -> RetrievalResult:
        del text
        canonical_jurisdiction = _canonical_jurisdiction(logical_kb, jurisdiction)
        candidates = self._evidence.get(logical_kb, ())
        filtered = tuple(
            item
            for item in candidates
            if item.jurisdiction == canonical_jurisdiction
            and (tax_year is None or tax_year in item.tax_years)
        )[:limit]
        return RetrievalResult(
            logical_kb=logical_kb,
            strategy=RetrievalStrategy.HYBRID,
            evidence=filtered,
        )
