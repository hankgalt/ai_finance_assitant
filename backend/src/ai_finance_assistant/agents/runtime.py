"""Shared retrieval and structured-model execution with measured events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import TypeVar
from uuid import uuid4

from pydantic import JsonValue

from ai_finance_assistant.contracts.agents import AgentRequest
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.contracts.events import (
    EventStatus,
    EventType,
    MeasurementAvailability,
    RetrievalMetadata,
    RetrievalSourceMetadata,
    ToolResultMetadata,
    UsageMetadata,
)
from ai_finance_assistant.knowledge.models import LogicalKnowledgeBase
from ai_finance_assistant.llm.errors import ModelErrorCode, ModelProviderError
from ai_finance_assistant.llm.models import ModelEvidence, ModelOutput, ModelRequest
from ai_finance_assistant.llm.ports import ModelAdapter
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.providers.models import (
    HistoricalResult,
    InstrumentSearchResult,
    NewsSearchResult,
    ProviderErrorCode,
    ProviderStatus,
    QuoteResult,
)
from ai_finance_assistant.workflow.events import EventIdentity, RunEventRecorder
from ai_finance_assistant.workflow.retrieval import KnowledgeRetrieval, RetrievalResult


@dataclass(frozen=True)
class AgentRuntimeFailure(Exception):
    error: SafeError


ProviderToolResult = QuoteResult | HistoricalResult | InstrumentSearchResult | NewsSearchResult
_ProviderResultT = TypeVar("_ProviderResultT", bound=ProviderToolResult)


class AgentRuntime:
    def __init__(
        self,
        *,
        retrieval: KnowledgeRetrieval,
        model: ModelAdapter,
        event_recorder: RunEventRecorder,
        observability: Observability,
    ) -> None:
        self._retrieval = retrieval
        self._model = model
        self._events = event_recorder
        self._observability = observability

    def retrieve(
        self,
        request: AgentRequest,
        *,
        logical_kb: LogicalKnowledgeBase,
        tax_year: int | None = None,
    ) -> RetrievalResult:
        identity = _identity(request)
        started_monotonic = monotonic()
        started = self._events.record(
            identity,
            event_type=EventType.RETRIEVAL_STARTED,
            status=EventStatus.RUNNING,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            summary=f"{logical_kb.value} retrieval started.",
        )
        try:
            with self._observability.span(
                "knowledge.retrieve",
                {"strategy": "hybrid", "collection_version": "active"},
            ):
                result = self._retrieval.retrieve(
                    logical_kb=logical_kb,
                    text=request.message,
                    tax_year=tax_year,
                    jurisdiction=request.jurisdiction,
                    limit=5,
                )
        except Exception as exc:
            attributes = {"strategy": "hybrid", "result_status": "failed"}
            self._observability.count("retrieval.requests", 1, attributes)
            self._observability.observe(
                "retrieval.duration_ms",
                (monotonic() - started_monotonic) * 1_000,
                attributes,
            )
            error = SafeError(
                code="RETRIEVAL_UNAVAILABLE",
                category=ErrorCategory.NOT_READY,
                message="The required knowledge collection is unavailable.",
                retryable=True,
            )
            self._events.record(
                identity,
                event_type=EventType.RETRIEVAL_FAILED,
                status=EventStatus.FAILED,
                node_id=request.agent_id.value,
                agent_id=request.agent_id,
                summary="Knowledge retrieval failed.",
                error=error,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            raise AgentRuntimeFailure(error) from exc
        metadata = RetrievalMetadata(
            strategy=result.strategy.value,
            sources=tuple(
                RetrievalSourceMetadata(
                    logical_kb=result.logical_kb.value,
                    collection_version=item.collection_version,
                    source_id=item.document_id,
                    chunk_id=item.chunk_id,
                    rank=item.rank,
                    score=item.score,
                    score_type="provider_score",
                )
                for item in result.evidence
            ),
        )
        self._events.record(
            identity,
            event_type=EventType.RETRIEVAL_COMPLETED,
            status=EventStatus.COMPLETED,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            summary="Knowledge retrieval completed.",
            retrieval=metadata,
            safe_metadata={
                "strategy": result.strategy.value,
                "source_count": len(result.evidence),
                "collection_version": (
                    result.evidence[0].collection_version if result.evidence else "unavailable"
                ),
            },
            started_at=started.started_at,
            completed=True,
            parent_event_id=started.event_id,
        )
        attributes = {"strategy": result.strategy.value, "result_status": "completed"}
        self._observability.count("retrieval.requests", 1, attributes)
        self._observability.observe(
            "retrieval.duration_ms",
            (monotonic() - started_monotonic) * 1_000,
            attributes,
        )
        return result

    def generate(
        self,
        request: AgentRequest,
        *,
        instructions: str,
        evidence: tuple[ModelEvidence, ...] = (),
        facts: tuple[dict[str, JsonValue], ...] = (),
    ) -> ModelOutput:
        identity = _identity(request)
        model_metadata = {
            "provider": self._model.provider_id,
            "model_id": self._model.model_id,
            "prompt_version": self._model.prompt_version,
        }
        started = self._events.record(
            identity,
            event_type=EventType.MODEL_STARTED,
            status=EventStatus.RUNNING,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            summary="Structured model generation started.",
            safe_metadata=model_metadata,
        )
        try:
            with self._observability.span("model.generate", model_metadata):
                adapter_result = self._model.generate(
                    ModelRequest(
                        agent_id=request.agent_id,
                        user_message=request.message,
                        instructions=instructions,
                        evidence=evidence,
                        facts=facts,
                        deadline_at=request.deadline_at,
                    )
                )
                output = ModelOutput.model_validate(adapter_result.payload)
        except ModelProviderError as exc:
            error = _model_error(exc)
            self._events.record(
                identity,
                event_type=EventType.MODEL_FAILED,
                status=EventStatus.FAILED,
                node_id=request.agent_id.value,
                agent_id=request.agent_id,
                summary="Structured model generation failed safely.",
                error=error,
                safe_metadata=model_metadata,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            raise AgentRuntimeFailure(error) from exc
        except Exception as exc:
            error = SafeError(
                code="MODEL_OUTPUT_INVALID",
                category=ErrorCategory.UPSTREAM_UNAVAILABLE,
                message="The model returned an invalid structured result.",
                retryable=True,
            )
            self._events.record(
                identity,
                event_type=EventType.MODEL_FAILED,
                status=EventStatus.FAILED,
                node_id=request.agent_id.value,
                agent_id=request.agent_id,
                summary="Structured model generation failed validation.",
                error=error,
                safe_metadata=model_metadata,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            raise AgentRuntimeFailure(error) from exc
        usage = adapter_result.usage
        usage_metadata = (
            UsageMetadata(
                availability=MeasurementAvailability.MEASURED,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=(
                    usage.input_tokens + usage.output_tokens
                    if usage.input_tokens is not None and usage.output_tokens is not None
                    else None
                ),
                method=usage.method,
                unavailable_reason=None,
            )
            if usage.method is not None
            else UsageMetadata()
        )
        self._events.record(
            identity,
            event_type=EventType.MODEL_COMPLETED,
            status=EventStatus.COMPLETED,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            summary="Structured model generation completed.",
            usage=usage_metadata,
            safe_metadata=model_metadata,
            started_at=started.started_at,
            completed=True,
            parent_event_id=started.event_id,
        )
        return output

    def tool(
        self,
        request: AgentRequest,
        *,
        name: str,
        operation: Callable[[], _ProviderResultT],
    ) -> _ProviderResultT:
        identity = _identity(request)
        started_monotonic = monotonic()
        tool_call_id = f"tool:{request.agent_id.value}:{uuid4().hex[:12]}"
        started = self._events.record(
            identity,
            event_type=EventType.TOOL_STARTED,
            status=EventStatus.RUNNING,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            tool_call_id=tool_call_id,
            tool_name=name,
            summary=f"{name} started.",
        )
        try:
            with self._observability.span("tool.execute", {"provider": name}):
                result = operation()
        except Exception as exc:
            attributes = {"provider": name, "operation": name, "result_status": "failed"}
            self._observability.count("provider.tool.requests", 1, attributes)
            self._observability.observe(
                "provider.tool.duration_ms",
                (monotonic() - started_monotonic) * 1_000,
                attributes,
            )
            error = SafeError(
                code="TOOL_EXECUTION_FAILED",
                category=ErrorCategory.UPSTREAM_UNAVAILABLE,
                message="The external data operation failed safely.",
                retryable=True,
            )
            self._events.record(
                identity,
                event_type=EventType.TOOL_FAILED,
                status=EventStatus.FAILED,
                node_id=request.agent_id.value,
                agent_id=request.agent_id,
                tool_call_id=tool_call_id,
                tool_name=name,
                summary=f"{name} failed.",
                error=error,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            raise AgentRuntimeFailure(error) from exc

        succeeded = result.status in {ProviderStatus.SUCCESS, ProviderStatus.EMPTY}
        attributes = {
            "provider": result.provenance.provider,
            "operation": name,
            "result_status": result.status.value,
        }
        self._observability.count("provider.tool.requests", 1, attributes)
        self._observability.observe(
            "provider.tool.duration_ms",
            (monotonic() - started_monotonic) * 1_000,
            attributes,
        )
        if result.provenance.attempts > 1:
            self._observability.count(
                "provider.retries",
                result.provenance.attempts - 1,
                {"provider": result.provenance.provider, "operation": name},
            )
        if result.status in {ProviderStatus.RATE_LIMITED, ProviderStatus.BUDGET_EXHAUSTED}:
            self._observability.count(
                "provider.rate_limited",
                1,
                {"provider": result.provenance.provider, "operation": name},
            )
        safe_error = _provider_error(result) if not succeeded else None
        record_count = _record_count(result)
        tool_result = ToolResultMetadata(
            result_status=EventStatus.COMPLETED if succeeded else EventStatus.FAILED,
            provider=result.provenance.provider,
            record_count=record_count,
            freshness=result.provenance.delay_status.value,
            cache_status=result.provenance.cache_status.value,
            error_reference=(result.error.code.value if result.error is not None else None),
        )
        self._events.record(
            identity,
            event_type=EventType.TOOL_COMPLETED if succeeded else EventType.TOOL_FAILED,
            status=EventStatus.COMPLETED if succeeded else EventStatus.FAILED,
            node_id=request.agent_id.value,
            agent_id=request.agent_id,
            tool_call_id=tool_call_id,
            tool_name=name,
            tool_result=tool_result,
            summary=f"{name} finished with {result.status.value} status.",
            error=safe_error,
            safe_metadata={
                "provider": result.provenance.provider,
                "record_count": record_count,
                "cache_status": result.provenance.cache_status.value,
                "result_status": result.status.value,
            },
            started_at=started.started_at,
            completed=True,
            parent_event_id=started.event_id,
        )
        return result


def _identity(request: AgentRequest) -> EventIdentity:
    return EventIdentity(
        execution_id=request.execution_id,
        session_id=request.session_id,
        workflow_id=request.workflow_id,
        workflow_version=request.workflow_version,
    )


def _record_count(result: ProviderToolResult) -> int:
    if isinstance(result, QuoteResult):
        return int(result.quote is not None)
    if isinstance(result, HistoricalResult):
        return len(result.series.bars) if result.series is not None else 0
    if isinstance(result, InstrumentSearchResult):
        return len(result.matches)
    return len(result.items)


def _provider_error(result: ProviderToolResult) -> SafeError:
    if result.error is None:
        return SafeError(
            code="PROVIDER_RESULT_FAILED",
            category=ErrorCategory.UPSTREAM_UNAVAILABLE,
            message="The provider operation did not return usable data.",
        )
    category = {
        ProviderErrorCode.INVALID_REQUEST: ErrorCategory.VALIDATION,
        ProviderErrorCode.UNAUTHORIZED: ErrorCategory.AUTHORIZATION,
        ProviderErrorCode.ENTITLEMENT_REQUIRED: ErrorCategory.AUTHORIZATION,
        ProviderErrorCode.RATE_LIMITED: ErrorCategory.RATE_LIMITED,
        ProviderErrorCode.TIMEOUT: ErrorCategory.TIMEOUT,
        ProviderErrorCode.MALFORMED_RESPONSE: ErrorCategory.UPSTREAM_UNAVAILABLE,
        ProviderErrorCode.UNAVAILABLE: ErrorCategory.UPSTREAM_UNAVAILABLE,
        ProviderErrorCode.BUDGET_EXHAUSTED: ErrorCategory.RATE_LIMITED,
        ProviderErrorCode.CIRCUIT_OPEN: ErrorCategory.UPSTREAM_UNAVAILABLE,
        ProviderErrorCode.CONCURRENCY_LIMITED: ErrorCategory.RATE_LIMITED,
    }[result.error.code]
    return SafeError(
        code=f"PROVIDER_{result.error.code.value.upper()}",
        category=category,
        message=result.error.message,
        retryable=result.error.retryable,
    )


def _model_error(failure: ModelProviderError) -> SafeError:
    code_and_category = {
        ModelErrorCode.NOT_READY: ("MODEL_NOT_READY", ErrorCategory.NOT_READY),
        ModelErrorCode.AUTHENTICATION_FAILED: (
            "MODEL_AUTHENTICATION_FAILED",
            ErrorCategory.AUTHORIZATION,
        ),
        ModelErrorCode.RATE_LIMITED: ("MODEL_RATE_LIMITED", ErrorCategory.RATE_LIMITED),
        ModelErrorCode.TIMEOUT: ("MODEL_TIMEOUT", ErrorCategory.TIMEOUT),
        ModelErrorCode.UNAVAILABLE: (
            "MODEL_PROVIDER_UNAVAILABLE",
            ErrorCategory.UPSTREAM_UNAVAILABLE,
        ),
        ModelErrorCode.REFUSED: ("MODEL_REFUSED", ErrorCategory.UPSTREAM_UNAVAILABLE),
        ModelErrorCode.INCOMPLETE: ("MODEL_INCOMPLETE", ErrorCategory.UPSTREAM_UNAVAILABLE),
        ModelErrorCode.MALFORMED_OUTPUT: (
            "MODEL_OUTPUT_INVALID",
            ErrorCategory.UPSTREAM_UNAVAILABLE,
        ),
        ModelErrorCode.REQUEST_BUDGET_EXHAUSTED: (
            "MODEL_REQUEST_BUDGET_EXHAUSTED",
            ErrorCategory.RATE_LIMITED,
        ),
        ModelErrorCode.INPUT_BUDGET_EXCEEDED: (
            "MODEL_INPUT_BUDGET_EXCEEDED",
            ErrorCategory.VALIDATION,
        ),
        ModelErrorCode.DEADLINE_EXCEEDED: (
            "MODEL_DEADLINE_EXCEEDED",
            ErrorCategory.TIMEOUT,
        ),
    }
    code, category = code_and_category[failure.code]
    safe_details: dict[str, JsonValue] = {}
    if failure.retry_after_seconds is not None:
        safe_details["retry_after_seconds"] = failure.retry_after_seconds
    return SafeError(
        code=code,
        category=category,
        message=failure.message,
        retryable=failure.retryable,
        attempt_count=failure.attempt_count,
        safe_details=safe_details,
    )
