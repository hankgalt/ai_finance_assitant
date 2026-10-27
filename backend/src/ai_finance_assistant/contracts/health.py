"""Health and readiness response contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


class CheckStatus(StrEnum):
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    NOT_IMPLEMENTED = "not_implemented"
    FAILED = "failed"


class DependencyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: CheckStatus
    detail: str
    expected: dict[str, JsonValue] = Field(default_factory=dict)


class Liveness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus = HealthStatus.OK
    service: str
    version: str


class Readiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: HealthStatus
    checks: tuple[DependencyCheck, ...]


class HealthSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    status: HealthStatus
    mode: str
    liveness: Liveness
    readiness: Readiness
