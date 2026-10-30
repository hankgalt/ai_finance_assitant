"""Authoritative versioned REST resources and replayable SSE."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_finance_assistant.agents.context import GoalAgentContext, PortfolioAgentContext
from ai_finance_assistant.api.errors import ApiProblem
from ai_finance_assistant.api.services import ApplicationServices
from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.contracts.api import (
    BrowserTelemetryEvent,
    ContinueRunRequest,
    CreateRunRequest,
    CreateSessionRequest,
    CreateSnapshotRequest,
    PortfolioImportApiRequest,
    PurgeResult,
    ResponseChunk,
    RunEventHistory,
    RunList,
    SessionList,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.core.logging import (
    reset_execution_id,
    reset_session_id,
    set_execution_id,
    set_session_id,
)
from ai_finance_assistant.finance.models import (
    GoalProjectionRequest,
    GoalProjectionResult,
    ImportedPortfolio,
    PortfolioAnalysisRequest,
    PortfolioImportResult,
    PortfolioSnapshot,
)
from ai_finance_assistant.persistence.models import (
    IdempotencyConflict,
    RunRecord,
    SessionRecord,
    SessionState,
)
from ai_finance_assistant.providers.models import (
    HistoricalRequest,
    HistoricalResult,
    InstrumentSearchRequest,
    InstrumentSearchResult,
    QuoteRequest,
    QuoteResult,
)
from ai_finance_assistant.workflow.models import (
    RequiredInputKind,
    WorkflowRequest,
    WorkflowRunResult,
    WorkflowStatus,
)

router = APIRouter(prefix="/v1", tags=["v1"])
logger = logging.getLogger(__name__)

IdempotencyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]


def _create_and_execute_run(
    *,
    services: ApplicationServices,
    session_id: str,
    message: str,
    context_references: tuple[str, ...],
    locale: str,
    jurisdiction: str,
    continuation_of_execution_id: str | None,
    continuation_agent_ids: tuple[AgentId, ...],
    idempotency_key: str | None,
    request_hash: str,
    response: Response,
) -> RunRecord:
    execution_id = f"run-{uuid4().hex}"
    try:
        record, created = services.application_repository.create_run(
            execution_id=execution_id,
            session_id=session_id,
            workflow_id="finance-assistant",
            workflow_version="1",
            request_message=message,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
    except IdempotencyConflict as exc:
        raise ApiProblem(
            409,
            "IDEMPOTENCY_CONFLICT",
            ErrorCategory.CONFLICT,
            str(exc),
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
        return record

    session_token = set_session_id(session_id)
    execution_token = set_execution_id(record.execution_id)
    try:
        try:
            result = services.workflow.run(
                WorkflowRequest(
                    execution_id=record.execution_id,
                    session_id=session_id,
                    workflow_id=record.workflow_id,
                    workflow_version=record.workflow_version,
                    message=message,
                    context_references=context_references,
                    continuation_of_execution_id=continuation_of_execution_id,
                    continuation_agent_ids=continuation_agent_ids,
                    locale=locale,
                    jurisdiction=jurisdiction,
                    deadline_at=datetime.now(UTC)
                    + timedelta(seconds=services.settings.api_run_deadline_seconds),
                )
            )
        except Exception:
            logger.exception("workflow_run_failed")
            result = WorkflowRunResult(
                execution_id=record.execution_id,
                session_id=session_id,
                workflow_id=record.workflow_id,
                workflow_version=record.workflow_version,
                status=WorkflowStatus.FAILED,
                selected_agent_ids=continuation_agent_ids,
                agent_results=(),
                summary="The Run could not be completed.",
                errors=(
                    SafeError(
                        code="RUN_EXECUTION_FAILED",
                        category=ErrorCategory.INTERNAL,
                        message="The Run failed safely before a result was available.",
                        retryable=True,
                    ),
                ),
                continuation_of_execution_id=continuation_of_execution_id,
                locale=locale,
                jurisdiction=jurisdiction,
                trace_unavailable_reason=("The unexpected failure prevented trace correlation."),
            )
        finished = services.application_repository.finish_run(result)
    finally:
        reset_execution_id(execution_token)
        reset_session_id(session_token)
    response.status_code = status.HTTP_201_CREATED
    return finished


def _services(request: Request) -> ApplicationServices:
    return request.app.state.services  # type: ignore[no-any-return]


def _require_session(services: ApplicationServices, session_id: str) -> SessionRecord:
    session = services.application_repository.get_session(session_id)
    if session is None:
        raise ApiProblem(
            404,
            "SESSION_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "The requested Session is unavailable.",
        )
    return session


def _require_active_session(
    services: ApplicationServices,
    session_id: str,
) -> SessionRecord:
    session = _require_session(services, session_id)
    if session.state == SessionState.ARCHIVED:
        raise ApiProblem(
            409,
            "SESSION_ARCHIVED",
            ErrorCategory.CONFLICT,
            "The Session is archived and read-only.",
        )
    return session


def _request_hash(model: object) -> str:
    if isinstance(model, BaseModel):
        payload = model.model_dump_json()
    else:
        payload = json.dumps(model, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


@router.post("/sessions", response_model=SessionRecord, status_code=201)
def create_session(body: CreateSessionRequest, request: Request) -> SessionRecord:
    return _services(request).application_repository.create_session(
        f"session-{uuid4().hex}",
        label=body.label,
    )


@router.get("/sessions", response_model=SessionList)
def list_sessions(
    request: Request,
    state: Annotated[SessionState | None, Query()] = None,
) -> SessionList:
    return SessionList(items=_services(request).application_repository.list_sessions(state=state))


@router.get("/sessions/{session_id}", response_model=SessionRecord)
def get_session(session_id: str, request: Request) -> SessionRecord:
    return _require_session(_services(request), session_id)


@router.post("/sessions/{session_id}/archive", response_model=SessionRecord)
def archive_session(session_id: str, request: Request) -> SessionRecord:
    archived = _services(request).application_repository.archive_session(session_id)
    if archived is None:
        raise ApiProblem(
            404,
            "SESSION_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "The requested Session is unavailable.",
        )
    return archived


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request) -> Response:
    services = _services(request)
    session = _require_session(services, session_id)
    if session.state != SessionState.ARCHIVED:
        raise ApiProblem(
            409,
            "SESSION_ARCHIVE_REQUIRED",
            ErrorCategory.CONFLICT,
            "Archive the Session before permanently deleting it.",
        )
    if not services.delete_session(session_id):
        raise ApiProblem(
            404,
            "SESSION_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "The requested Session is unavailable.",
        )
    return Response(status_code=204)


@router.post("/sessions/{session_id}/runs", response_model=RunRecord)
def create_run(
    session_id: str,
    body: CreateRunRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyHeader = None,
) -> RunRecord:
    services = _services(request)
    _require_active_session(services, session_id)
    return _create_and_execute_run(
        services=services,
        session_id=session_id,
        message=body.message,
        context_references=body.context_references,
        locale=body.locale,
        jurisdiction=body.jurisdiction,
        continuation_of_execution_id=None,
        continuation_agent_ids=(),
        idempotency_key=idempotency_key,
        request_hash=_request_hash(body),
        response=response,
    )


@router.post(
    "/sessions/{session_id}/runs/{execution_id}/continue",
    response_model=RunRecord,
)
def continue_run(
    session_id: str,
    execution_id: str,
    body: ContinueRunRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyHeader = None,
) -> RunRecord:
    services = _services(request)
    _require_active_session(services, session_id)
    try:
        source = services.application_repository.get_run(
            execution_id,
            session_id=session_id,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "RUN_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Run is outside the requested Session scope.",
        ) from exc
    if source is None:
        raise ApiProblem(
            404,
            "RUN_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "Run not found.",
        )
    result = source.result
    if (
        result is None
        or result.required_input is None
        or result.required_input.kind != RequiredInputKind.PORTFOLIO_SELECTION
        or source.request_message is None
    ):
        raise ApiProblem(
            409,
            "RUN_CONTINUATION_NOT_AVAILABLE",
            ErrorCategory.CONFLICT,
            "This Run is not waiting for a Portfolio selection.",
        )
    existing = next(
        (
            item
            for item in services.application_repository.list_runs(session_id=session_id)
            if item.result is not None and item.result.continuation_of_execution_id == execution_id
        ),
        None,
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing
    context_references = tuple(dict.fromkeys(body.context_references))
    if any(
        not isinstance(
            services.context_repository.get(session_id, reference),
            PortfolioAgentContext,
        )
        for reference in context_references
    ):
        raise ApiProblem(
            403,
            "PORTFOLIO_CONTEXT_DENIED",
            ErrorCategory.AUTHORIZATION,
            "A selected Portfolio is unavailable in this Session.",
        )
    return _create_and_execute_run(
        services=services,
        session_id=session_id,
        message=source.request_message,
        context_references=context_references,
        locale=result.locale,
        jurisdiction=result.jurisdiction,
        continuation_of_execution_id=execution_id,
        continuation_agent_ids=result.selected_agent_ids,
        idempotency_key=idempotency_key,
        request_hash=_request_hash(
            {
                "continuation_of_execution_id": execution_id,
                "context_references": context_references,
            }
        ),
        response=response,
    )


@router.get("/sessions/{session_id}/runs", response_model=RunList)
def list_runs(session_id: str, request: Request) -> RunList:
    services = _services(request)
    _require_session(services, session_id)
    return RunList(items=services.application_repository.list_runs(session_id=session_id))


@router.get("/sessions/{session_id}/runs/{execution_id}", response_model=RunRecord)
def get_run(session_id: str, execution_id: str, request: Request) -> RunRecord:
    services = _services(request)
    try:
        run = services.application_repository.get_run(execution_id, session_id=session_id)
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "RUN_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Run is outside the requested Session scope.",
        ) from exc
    if run is None:
        raise ApiProblem(404, "RUN_NOT_FOUND", ErrorCategory.AUTHORIZATION, "Run not found.")
    return run


@router.get(
    "/sessions/{session_id}/runs/{execution_id}/events",
    response_model=RunEventHistory,
)
def run_events(session_id: str, execution_id: str, request: Request) -> RunEventHistory:
    services = _services(request)
    get_run(session_id, execution_id, request)
    try:
        events = services.event_repository.list_for_run(
            execution_id,
            session_id=session_id,
            limit=services.settings.api_sse_replay_limit,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "TRACE_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The trace is outside the requested Session scope.",
        ) from exc
    return RunEventHistory(execution_id=execution_id, events=events)


@router.get(
    "/sessions/{session_id}/traces/{execution_id}",
    response_model=RunEventHistory,
)
def trace_history(session_id: str, execution_id: str, request: Request) -> RunEventHistory:
    return run_events(session_id, execution_id, request)


@router.get("/sessions/{session_id}/runs/{execution_id}/stream")
def stream_run(
    session_id: str,
    execution_id: str,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    services = _services(request)
    run = get_run(session_id, execution_id, request)
    after_sequence, chunk_seen = _sse_cursor(execution_id, last_event_id)
    events = services.event_repository.list_for_run(
        execution_id,
        session_id=session_id,
        after_sequence=after_sequence,
        limit=services.settings.api_sse_replay_limit,
    )

    def generate() -> Iterator[str]:
        for event in events:
            yield _sse_frame(event.event_id, "run_event", event.model_dump_json())
        if run.result is not None and not chunk_seen:
            chunk = ResponseChunk(
                execution_id=execution_id,
                chunk_id=f"chunk:{execution_id}:1",
                text=run.result.summary,
            )
            yield _sse_frame(chunk.chunk_id, "response_chunk", chunk.model_dump_json())

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/portfolio-imports/validate",
    response_model=PortfolioImportResult,
)
def validate_portfolio_import(
    session_id: str,
    body: PortfolioImportApiRequest,
    request: Request,
) -> PortfolioImportResult:
    services = _services(request)
    _require_active_session(services, session_id)
    return services.portfolio_import.import_portfolio(body.to_domain())


@router.post(
    "/sessions/{session_id}/portfolios",
    response_model=PortfolioImportResult,
)
def create_portfolio(
    session_id: str,
    body: PortfolioImportApiRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyHeader = None,
) -> PortfolioImportResult:
    services = _services(request)
    _require_active_session(services, session_id)
    result = services.portfolio_import.import_portfolio(body.to_domain())
    if not result.accepted or result.portfolio is None:
        response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return result
    try:
        portfolio, created = services.application_repository.save_portfolio(
            result.portfolio,
            session_id=session_id,
            idempotency_key=idempotency_key,
            request_hash=_request_hash(body),
        )
    except IdempotencyConflict as exc:
        raise ApiProblem(
            409,
            "IDEMPOTENCY_CONFLICT",
            ErrorCategory.CONFLICT,
            str(exc),
        ) from exc
    services.context_repository.put(
        session_id,
        PortfolioAgentContext(
            context_id=portfolio.portfolio_id,
            portfolio=portfolio,
            calculated_at=portfolio.imported_at,
        ),
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return result.model_copy(update={"portfolio": portfolio})


@router.get("/sessions/{session_id}/portfolios", response_model=tuple[ImportedPortfolio, ...])
def list_portfolios(session_id: str, request: Request) -> tuple[ImportedPortfolio, ...]:
    services = _services(request)
    _require_session(services, session_id)
    return services.application_repository.list_portfolios(session_id=session_id)


@router.get(
    "/sessions/{session_id}/portfolios/{portfolio_id}",
    response_model=ImportedPortfolio,
)
def get_portfolio(session_id: str, portfolio_id: str, request: Request) -> ImportedPortfolio:
    services = _services(request)
    try:
        portfolio = services.application_repository.get_portfolio(
            portfolio_id,
            session_id=session_id,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "PORTFOLIO_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Portfolio is outside the requested Session scope.",
        ) from exc
    if portfolio is None:
        raise ApiProblem(
            404,
            "PORTFOLIO_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "Portfolio not found.",
        )
    return portfolio


@router.delete("/sessions/{session_id}/portfolios/{portfolio_id}", status_code=204)
def delete_portfolio(session_id: str, portfolio_id: str, request: Request) -> Response:
    services = _services(request)
    _require_active_session(services, session_id)
    try:
        deleted = services.application_repository.delete_portfolio(
            portfolio_id,
            session_id=session_id,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "PORTFOLIO_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Portfolio is outside the requested Session scope.",
        ) from exc
    if not deleted:
        raise ApiProblem(
            404,
            "PORTFOLIO_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "Portfolio not found.",
        )
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/portfolios/{portfolio_id}/snapshots",
    response_model=PortfolioSnapshot,
    status_code=201,
)
def create_snapshot(
    session_id: str,
    portfolio_id: str,
    body: CreateSnapshotRequest,
    request: Request,
) -> PortfolioSnapshot:
    services = _services(request)
    _require_active_session(services, session_id)
    portfolio = get_portfolio(session_id, portfolio_id, request)
    calculated_at = datetime.now(UTC)
    snapshot = services.portfolio_analysis.analyze(
        PortfolioAnalysisRequest(
            snapshot_id=body.snapshot_id or f"snapshot-{uuid4().hex}",
            calculated_at=calculated_at,
            portfolio=portfolio,
            security_references=body.security_references,
            quote_set=body.quote_set,
        )
    )
    services.application_repository.save_snapshot(snapshot, session_id=session_id)
    services.context_repository.put(
        session_id,
        PortfolioAgentContext(
            context_id=portfolio_id,
            portfolio=portfolio,
            security_references=body.security_references,
            calculated_at=calculated_at,
        ),
    )
    return snapshot


@router.get(
    "/sessions/{session_id}/portfolios/{portfolio_id}/snapshots",
    response_model=tuple[PortfolioSnapshot, ...],
)
def list_snapshots(
    session_id: str,
    portfolio_id: str,
    request: Request,
) -> tuple[PortfolioSnapshot, ...]:
    services = _services(request)
    try:
        return services.application_repository.list_snapshots(
            portfolio_id,
            session_id=session_id,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "PORTFOLIO_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Portfolio is outside the requested Session scope.",
        ) from exc
    except LookupError as exc:
        raise ApiProblem(
            404,
            "PORTFOLIO_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "Portfolio not found.",
        ) from exc


@router.get(
    "/sessions/{session_id}/snapshots/{snapshot_id}",
    response_model=PortfolioSnapshot,
)
def get_snapshot(session_id: str, snapshot_id: str, request: Request) -> PortfolioSnapshot:
    services = _services(request)
    try:
        snapshot = services.application_repository.get_snapshot(
            snapshot_id,
            session_id=session_id,
        )
    except PermissionError as exc:
        raise ApiProblem(
            403,
            "SNAPSHOT_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "The Portfolio Snapshot is outside the requested Session scope.",
        ) from exc
    if snapshot is None:
        raise ApiProblem(
            404,
            "SNAPSHOT_NOT_FOUND",
            ErrorCategory.AUTHORIZATION,
            "Portfolio Snapshot not found.",
        )
    return snapshot


@router.post(
    "/sessions/{session_id}/market/instruments/search",
    response_model=InstrumentSearchResult,
)
def search_instruments(
    session_id: str,
    body: InstrumentSearchRequest,
    request: Request,
) -> InstrumentSearchResult:
    services = _services(request)
    _require_active_session(services, session_id)
    return services.market.search_instruments(body)


@router.post("/sessions/{session_id}/market/quotes", response_model=QuoteResult)
def market_quote(session_id: str, body: QuoteRequest, request: Request) -> QuoteResult:
    services = _services(request)
    _require_active_session(services, session_id)
    return services.market.get_quote(body)


@router.post("/sessions/{session_id}/market/history", response_model=HistoricalResult)
def market_history(
    session_id: str,
    body: HistoricalRequest,
    request: Request,
) -> HistoricalResult:
    services = _services(request)
    _require_active_session(services, session_id)
    return services.market.get_history(body)


@router.post(
    "/sessions/{session_id}/goal-projections",
    response_model=GoalProjectionResult,
)
def goal_projection(
    session_id: str,
    body: GoalProjectionRequest,
    request: Request,
) -> GoalProjectionResult:
    services = _services(request)
    _require_active_session(services, session_id)
    services.context_repository.put(
        session_id,
        GoalAgentContext(context_id=body.projection_id, projection=body),
    )
    return services.goal_projection.project(body)


@router.delete("/admin/provider-cache", response_model=PurgeResult)
def purge_provider_cache(
    request: Request,
    provider: Annotated[str | None, Query(max_length=128)] = None,
    admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> PurgeResult:
    services = _services(request)
    configured = services.settings.local_admin_token
    if configured is None:
        raise ApiProblem(
            503,
            "ADMIN_PURGE_NOT_READY",
            ErrorCategory.NOT_READY,
            "Administrative purge is disabled until a local admin token is configured.",
        )
    supplied = admin_token or ""
    if not hmac.compare_digest(configured.get_secret_value(), supplied):
        raise ApiProblem(
            403,
            "ADMIN_SCOPE_DENIED",
            ErrorCategory.AUTHORIZATION,
            "Administrative authorization failed.",
        )
    count = services.purge_provider_cache(provider=provider)
    return PurgeResult(provider=provider, deleted_bar_count=count)


@router.post("/telemetry/browser", status_code=204)
def browser_telemetry(body: BrowserTelemetryEvent, request: Request) -> Response:
    observability = _services(request).observability
    if body.kind == "navigation":
        observability.count("frontend.navigation", 1, {"page": body.page})
    elif body.kind == "error_boundary":
        observability.count(
            "frontend.errors",
            1,
            {"page": body.page, "failure_category": body.failure_category},
        )
    elif body.kind == "web_vital":
        observability.observe(
            "frontend.web_vital",
            body.metric_value or 0,
            {
                "page": body.page,
                "metric_name": body.metric_name or "unavailable",
                "rating": body.rating or "unavailable",
            },
        )
    else:
        attributes = {
            "page": body.page,
            "route": body.api_route or "unavailable",
            "status_class": body.status_class or "unavailable",
            "failure_category": body.failure_category,
        }
        observability.count("frontend.api.requests", 1, attributes)
        observability.observe("frontend.api.duration_ms", body.duration_ms or 0, attributes)
    return Response(status_code=204)


def _sse_cursor(execution_id: str, value: str | None) -> tuple[int, bool]:
    if value is None:
        return 0, False
    chunk_id = f"chunk:{execution_id}:1"
    if value == chunk_id:
        return 2**31 - 1, True
    prefix = f"evt:{execution_id}:"
    if not value.startswith(prefix):
        raise ApiProblem(
            400,
            "INVALID_LAST_EVENT_ID",
            ErrorCategory.VALIDATION,
            "Last-Event-ID does not belong to this Run.",
        )
    try:
        return int(value.removeprefix(prefix)), False
    except ValueError as exc:
        raise ApiProblem(
            400,
            "INVALID_LAST_EVENT_ID",
            ErrorCategory.VALIDATION,
            "Last-Event-ID is malformed.",
        ) from exc


def _sse_frame(event_id: str, event_type: str, data: str) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"
