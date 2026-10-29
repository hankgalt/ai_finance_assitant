"""Versioned, minimized model request and response contracts."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.common import Identifier, ShortText


class ModelEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: Identifier
    content: str = Field(min_length=1, max_length=8_000)


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    agent_id: AgentId
    user_message: str = Field(min_length=1, max_length=20_000)
    instructions: str = Field(min_length=1, max_length=4_000)
    evidence: tuple[ModelEvidence, ...] = Field(default=(), max_length=10)
    facts: tuple[dict[str, JsonValue], ...] = Field(default=(), max_length=100)
    max_output_tokens: int = Field(default=1_200, ge=1, le=4_000)
    deadline_at: AwareDatetime


class ModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    summary: ShortText
    warnings: tuple[ShortText, ...] = Field(default=(), max_length=20)


class ModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    method: str | None = Field(default=None, max_length=128)


class ModelAdapterResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, JsonValue]
    usage: ModelUsage = Field(default_factory=ModelUsage)
