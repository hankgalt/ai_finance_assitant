"""Authorized typed context references kept outside general graph state."""

from datetime import date
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier
from ai_finance_assistant.finance.models import (
    GoalProjectionRequest,
    ImportedPortfolio,
    SecurityReference,
)


class PortfolioAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["portfolio"] = "portfolio"
    context_id: Identifier
    portfolio: ImportedPortfolio
    security_references: tuple[SecurityReference, ...] = ()
    calculated_at: AwareDatetime


class MarketAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["market"] = "market"
    context_id: Identifier
    symbol: Identifier
    currency: CurrencyCode
    start_date: date
    end_date: date


class GoalAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["goal"] = "goal"
    context_id: Identifier
    projection: GoalProjectionRequest


class NewsAgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["news"] = "news"
    context_id: Identifier
    query: str = Field(min_length=2, max_length=200)
    symbols: tuple[Identifier, ...] = Field(default=(), max_length=10)
    start_date: date
    end_date: date


AuthorizedAgentContext = (
    PortfolioAgentContext | MarketAgentContext | GoalAgentContext | NewsAgentContext
)


class AgentContextRepository(Protocol):
    def get(self, session_id: str, context_id: str) -> AuthorizedAgentContext | None: ...


class InMemoryAgentContextRepository:
    def __init__(self) -> None:
        self._contexts: dict[tuple[str, str], AuthorizedAgentContext] = {}

    def put(self, session_id: str, context: AuthorizedAgentContext) -> None:
        self._contexts[(session_id, context.context_id)] = context

    def get(self, session_id: str, context_id: str) -> AuthorizedAgentContext | None:
        return self._contexts.get((session_id, context_id))
