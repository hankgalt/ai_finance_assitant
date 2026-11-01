"""Grounded multi-specialist synthesis behind one workflow-facing interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ai_finance_assistant.contracts.agents import AgentResult
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.contracts.events import (
    EventStatus,
    EventType,
    MeasurementAvailability,
    UsageMetadata,
)
from ai_finance_assistant.llm.errors import (
    ModelProviderError,
    model_failure_to_safe_error,
)
from ai_finance_assistant.llm.models import (
    SynthesisAgentInput,
    SynthesisModelOutput,
    SynthesisModelRequest,
)
from ai_finance_assistant.llm.ports import ModelAdapter
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.workflow.events import EventIdentity, RunEventRecorder


@dataclass(frozen=True)
class SynthesisFailure(Exception):
    error: SafeError


class MultiAgentSynthesizer:
    """Turn already-grounded specialist results into one bounded final narrative."""

    def __init__(
        self,
        *,
        model: ModelAdapter,
        event_recorder: RunEventRecorder,
        observability: Observability,
    ) -> None:
        self._model = model
        self._events = event_recorder
        self._observability = observability

    def synthesize(
        self,
        *,
        identity: EventIdentity,
        user_message: str,
        results: tuple[AgentResult, ...],
        deadline_at: datetime,
    ) -> SynthesisModelOutput:
        model_metadata = {
            "provider": self._model.provider_id,
            "model_id": self._model.model_id,
            "prompt_version": self._model.synthesis_prompt_version,
        }
        started = self._events.record(
            identity,
            event_type=EventType.MODEL_STARTED,
            status=EventStatus.RUNNING,
            node_id="synthesize",
            summary="Grounded multi-specialist synthesis started.",
            safe_metadata=model_metadata,
        )
        try:
            request = SynthesisModelRequest(
                user_message=user_message,
                agent_results=tuple(
                    SynthesisAgentInput(
                        agent_id=result.agent_id,
                        status=result.status,
                        summary=result.summary,
                        evidence=result.evidence[:20],
                        warnings=result.warnings[:20],
                    )
                    for result in results
                ),
                deadline_at=deadline_at,
            )
            with self._observability.span("model.synthesize", model_metadata):
                adapter_result = self._model.synthesize(request)
                output = SynthesisModelOutput.model_validate(adapter_result.payload)
        except ModelProviderError as exc:
            error = model_failure_to_safe_error(exc)
            self._record_failure(
                identity=identity,
                started_at=started.started_at,
                parent_event_id=started.event_id,
                metadata=model_metadata,
                error=error,
                summary="Grounded multi-specialist synthesis failed safely.",
            )
            raise SynthesisFailure(error) from exc
        except Exception as exc:
            error = SafeError(
                code="MODEL_OUTPUT_INVALID",
                category=ErrorCategory.UPSTREAM_UNAVAILABLE,
                message="The model returned an invalid structured synthesis result.",
                retryable=True,
            )
            self._record_failure(
                identity=identity,
                started_at=started.started_at,
                parent_event_id=started.event_id,
                metadata=model_metadata,
                error=error,
                summary="Grounded multi-specialist synthesis failed validation.",
            )
            raise SynthesisFailure(error) from exc

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
            node_id="synthesize",
            summary="Grounded multi-specialist synthesis completed.",
            usage=usage_metadata,
            safe_metadata=model_metadata,
            started_at=started.started_at,
            completed=True,
            parent_event_id=started.event_id,
        )
        return output

    def _record_failure(
        self,
        *,
        identity: EventIdentity,
        started_at: datetime,
        parent_event_id: str,
        metadata: dict[str, str],
        error: SafeError,
        summary: str,
    ) -> None:
        self._events.record(
            identity,
            event_type=EventType.MODEL_FAILED,
            status=EventStatus.FAILED,
            node_id="synthesize",
            summary=summary,
            error=error,
            safe_metadata=metadata,
            started_at=started_at,
            completed=True,
            parent_event_id=parent_event_id,
        )
