"""Deterministic, bounded intent routing for the six specialist agents."""

import re

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.common import ShortText


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_agent_ids: tuple[AgentId, ...] = Field(max_length=6)
    reason_category: ShortText


_KEYWORDS: dict[AgentId, tuple[str, ...]] = {
    AgentId.FINANCE_QA: (
        "etf",
        "mutual fund",
        "bond",
        "diversification",
        "asset class",
        "financial literacy",
        "compound interest",
        "index fund",
        "emergency fund",
        "risk and return",
        "risk versus return",
        "inflation",
    ),
    AgentId.PORTFOLIO_ANALYSIS: (
        "portfolio",
        "holding",
        "allocation",
        "concentration",
        "expense ratio",
        "rebalance",
        "asset allocation",
    ),
    AgentId.MARKET_ANALYSIS: (
        "market price",
        "stock price",
        "quote",
        "historical price",
        "price history",
        "market performance",
        "what changed",
        "trading volume",
        "price today",
    ),
    AgentId.GOAL_PLANNING: (
        "goal",
        "retirement",
        "save for",
        "contribution",
        "future value",
        "down payment",
        "college fund",
        "savings target",
    ),
    AgentId.NEWS_SYNTHESIZER: (
        "news",
        "headline",
        "announcement",
        "latest story",
        "recent story",
        "recent development",
        "company report",
    ),
    AgentId.TAX_EDUCATION: (
        "tax",
        "capital gain",
        "wash sale",
        "roth ira",
        "traditional ira",
        "1099",
        "deduction",
        "taxable income",
    ),
}

_FOLLOW_UP_PHRASES = (
    "that another way",
    "explain that",
    "tell me more",
    "follow up",
    "what about that",
    "continue",
)


class IntentRouter:
    def route(
        self,
        message: str,
        *,
        previous_agent_ids: tuple[AgentId, ...] = (),
    ) -> RouteDecision:
        normalized = re.sub(r"\s+", " ", message.casefold())
        selected = tuple(
            agent_id
            for agent_id in AgentId
            if any(keyword in normalized for keyword in _KEYWORDS[agent_id])
        )
        if (
            not selected
            and previous_agent_ids
            and any(phrase in normalized for phrase in _FOLLOW_UP_PHRASES)
        ):
            return RouteDecision(
                selected_agent_ids=previous_agent_ids,
                reason_category="checkpoint_follow_up",
            )
        if not selected:
            return RouteDecision(
                selected_agent_ids=(),
                reason_category="clarification_required",
            )
        return RouteDecision(
            selected_agent_ids=selected,
            reason_category="single_domain" if len(selected) == 1 else "multi_domain",
        )
