"""Versioned REST, SSE recovery, import-transport, and browser telemetry contracts."""

from __future__ import annotations

import base64
import binascii
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_finance_assistant.contracts.common import Identifier, NarrativeText
from ai_finance_assistant.contracts.errors import SafeError
from ai_finance_assistant.contracts.events import RunEvent
from ai_finance_assistant.finance.models import (
    CsvImportPayload,
    ImportPayload,
    ImportSourceKind,
    JsonImportPayload,
    ManualImportPayload,
    PortfolioImportMetadata,
    PortfolioImportRequest,
    QuoteSet,
    SecurityReference,
    XlsxImportPayload,
)
from ai_finance_assistant.persistence.models import RunRecord, SessionRecord


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = Field(default=None, max_length=128)


class SessionList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[SessionRecord, ...]


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(min_length=1, max_length=20_000)
    context_references: tuple[Identifier, ...] = Field(default=(), max_length=20)
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    jurisdiction: str = Field(default="US", min_length=2, max_length=32)


class EncodedFileImportPayload(BaseModel):
    """JSON-safe transport for the three file import modes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[ImportSourceKind.JSON, ImportSourceKind.CSV, ImportSourceKind.XLSX]
    content_base64: str = Field(min_length=1, max_length=2_700_000)
    filename: str = Field(min_length=1, max_length=255)

    @field_validator("content_base64")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("content_base64 must be canonical base64") from exc
        return value

    def decoded_content(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


class PortfolioImportApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    metadata: PortfolioImportMetadata
    payload: ManualImportPayload | EncodedFileImportPayload

    def to_domain(self) -> PortfolioImportRequest:
        payload = self.payload
        domain_payload: ImportPayload
        if isinstance(payload, ManualImportPayload):
            domain_payload = payload
        else:
            content = payload.decoded_content()
            if payload.kind == ImportSourceKind.JSON:
                domain_payload = JsonImportPayload(content=content, filename=payload.filename)
            elif payload.kind == ImportSourceKind.CSV:
                domain_payload = CsvImportPayload(content=content, filename=payload.filename)
            else:
                domain_payload = XlsxImportPayload(content=content, filename=payload.filename)
        return PortfolioImportRequest(metadata=self.metadata, payload=domain_payload)


class RunList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[RunRecord, ...]


class RunEventHistory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    events: tuple[RunEvent, ...]
    recovery: str = "Use Last-Event-ID for SSE replay or reload this resource and the Run."


class ResponseChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: Identifier
    chunk_id: Identifier
    text: NarrativeText
    terminal: bool = True


class CreateSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: Identifier | None = None
    security_references: tuple[SecurityReference, ...] = ()
    quote_set: QuoteSet


class PurgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = Field(default=None, max_length=128)
    deleted_bar_count: int = Field(ge=0)
    memory_cache_cleared: bool = True


BrowserTelemetryKind = Literal["navigation", "api_timing", "web_vital", "error_boundary"]
BrowserPage = Literal[
    "shell",
    "assistant",
    "portfolio",
    "market",
    "goals",
    "history",
    "inspector",
]
BrowserApiRoute = Literal[
    "health",
    "sessions",
    "runs",
    "run_stream",
    "portfolio_imports",
    "portfolios",
    "snapshots",
    "market_quotes",
    "market_history",
    "goals",
    "browser_telemetry",
]
BrowserFailureCategory = Literal[
    "none",
    "validation",
    "authorization",
    "not_ready",
    "conflict",
    "rate_limited",
    "timeout",
    "upstream",
    "network",
    "internal",
]


class BrowserTelemetryEvent(BaseModel):
    """Bounded browser signal; intentionally has no message or arbitrary metadata field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    kind: BrowserTelemetryKind
    page: BrowserPage
    api_route: BrowserApiRoute | None = None
    status_class: Literal["2xx", "4xx", "5xx", "network_error"] | None = None
    failure_category: BrowserFailureCategory = "none"
    duration_ms: float | None = Field(default=None, ge=0, le=600_000)
    metric_name: Literal["CLS", "FCP", "INP", "LCP", "TTFB"] | None = None
    metric_value: float | None = Field(default=None, ge=0, le=10_000_000)
    rating: Literal["good", "needs-improvement", "poor"] | None = None
    trace_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    request_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> BrowserTelemetryEvent:
        if self.kind == "api_timing" and (
            self.api_route is None or self.status_class is None or self.duration_ms is None
        ):
            raise ValueError("api_timing requires route, status class, and duration")
        if self.kind == "web_vital" and (
            self.metric_name is None or self.metric_value is None or self.rating is None
        ):
            raise ValueError("web_vital requires metric name, value, and rating")
        if self.kind == "error_boundary" and self.failure_category == "none":
            raise ValueError("error_boundary requires a failure category")
        return self


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: SafeError
