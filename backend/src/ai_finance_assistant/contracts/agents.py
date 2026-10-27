"""Contracts shared by the six future agent modules."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from ai_finance_assistant.contracts.common import Identifier, ShortText
from ai_finance_assistant.contracts.errors import SafeError


class AgentId(StrEnum):
    FINANCE_QA = "finance_qa"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    MARKET_ANALYSIS = "market_analysis"
    GOAL_PLANNING = "goal_planning"
    NEWS_SYNTHESIZER = "news_synthesizer"
    TAX_EDUCATION = "tax_education"


class AgentResultStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: Identifier
    title: ShortText
    publisher: ShortText
    canonical_url: str = Field(min_length=1, max_length=2048)
    source_anchor: str | None = Field(default=None, max_length=512)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    execution_id: Identifier
    session_id: Identifier
    workflow_id: Identifier
    workflow_version: Identifier
    agent_id: AgentId
    message: str = Field(min_length=1, max_length=20_000)
    context_references: tuple[Identifier, ...] = ()
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)
    deadline_at: AwareDatetime


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    agent_id: AgentId
    status: AgentResultStatus
    summary: ShortText
    facts: tuple[dict[str, JsonValue], ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    visualization: dict[str, JsonValue] | None = None
    as_of: AwareDatetime | None = None
    warnings: tuple[ShortText, ...] = ()
    errors: tuple[SafeError, ...] = ()

    @model_validator(mode="after")
    def validate_error_state(self) -> "AgentResult":
        if self.status == AgentResultStatus.ERROR and not self.errors:
            raise ValueError("error results require at least one safe error")
        if self.status == AgentResultStatus.OK and self.errors:
            raise ValueError("ok results cannot contain errors")
        return self
