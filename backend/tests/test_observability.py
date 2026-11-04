from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime, timedelta

from langchain_core.tracers.context import collect_runs
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import JsonValue
from pytest import MonkeyPatch

from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentRequest,
    AgentResult,
    AgentResultStatus,
)
from ai_finance_assistant.contracts.events import EventStatus, EventType
from ai_finance_assistant.core.config import Settings, get_settings
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.observability.factory import (
    observability_from_settings,
    telemetry_runtime_from_settings,
)
from ai_finance_assistant.observability.langsmith import LangSmithTracing
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.observability.opentelemetry import OpenTelemetryObservability
from ai_finance_assistant.observability.ports import TraceContext
from ai_finance_assistant.observability.safe import SafeObservability
from ai_finance_assistant.workflow.events import (
    EventIdentity,
    InMemoryRunEventRepository,
    RunEventRecorder,
)
from ai_finance_assistant.workflow.graph import FinanceWorkflow
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowStatus


class SuccessfulAgent:
    def __init__(self, agent_id: AgentId) -> None:
        self.agent_id = agent_id

    def invoke(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            status=AgentResultStatus.OK,
            summary=f"{request.agent_id.value} completed.",
        )


class FailingTelemetry:
    def span(
        self,
        name: str,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> AbstractContextManager[TraceContext]:
        del name, attributes
        raise RuntimeError("exporter unavailable")

    def count(
        self,
        name: str,
        value: int,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        del name, value, attributes
        raise RuntimeError("exporter unavailable")

    def observe(
        self,
        name: str,
        value: float,
        attributes: Mapping[str, JsonValue] | None = None,
    ) -> None:
        del name, value, attributes
        raise RuntimeError("exporter unavailable")

    def current_trace_id(self) -> str | None:
        raise RuntimeError("exporter unavailable")


def _request(execution_id: str) -> WorkflowRequest:
    return WorkflowRequest(
        execution_id=execution_id,
        session_id="session-observability",
        workflow_id=get_settings().workflow_id,
        workflow_version="1",
        message="What is an ETF?",
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


def _agents() -> dict[AgentId, SuccessfulAgent]:
    return {agent_id: SuccessfulAgent(agent_id) for agent_id in AgentId}


def test_run_events_correlate_with_exported_opentelemetry_trace() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    telemetry = SafeObservability(OpenTelemetryObservability(tracer=provider.get_tracer("m4-test")))
    events = InMemoryRunEventRepository()
    workflow = FinanceWorkflow(
        agents=_agents(),
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        model=DeterministicModelAdapter(),
    )

    result = workflow.run(_request("run-otel-1"))

    spans = exporter.get_finished_spans()
    assert result.status == WorkflowStatus.COMPLETED
    assert result.trace_id is not None
    assert spans
    span_trace_ids: set[str] = set()
    for span in spans:
        assert span.context is not None
        span_trace_ids.add(format(span.context.trace_id, "032x"))
    assert span_trace_ids == {result.trace_id}
    recorded = events.list_for_run("run-otel-1", session_id="session-observability")
    event_trace_ids: set[str] = set()
    for event in recorded:
        assert event.trace_id is not None
        event_trace_ids.add(event.trace_id)
    assert event_trace_ids == {result.trace_id}
    assert all("message" not in (span.attributes or {}) for span in spans)


def test_langgraph_root_trace_uses_workflow_name() -> None:
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=_agents(),
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=telemetry,
        ),
        observability=telemetry,
        model=DeterministicModelAdapter(),
    )

    with collect_runs() as collected:
        result = workflow.run(_request("run-langsmith-name-1"))

    root_runs = [run for run in collected.traced_runs if run.parent_run_id is None]
    assert result.status == WorkflowStatus.COMPLETED
    assert [run.name for run in root_runs] == [get_settings().workflow_id]


def test_failed_observability_adapter_does_not_change_product_behavior() -> None:
    telemetry = SafeObservability(FailingTelemetry())
    events = InMemoryRunEventRepository()
    workflow = FinanceWorkflow(
        agents=_agents(),
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        model=DeterministicModelAdapter(),
    )

    result = workflow.run(_request("run-exporter-failure-1"))

    assert result.status == WorkflowStatus.COMPLETED
    assert result.trace_id is None
    assert result.trace_unavailable_reason is not None
    recorded = events.list_for_run(
        "run-exporter-failure-1",
        session_id="session-observability",
    )
    assert all(event.trace_id is None for event in recorded)


def test_event_and_telemetry_metadata_are_redacted_and_allow_listed() -> None:
    telemetry = InMemoryObservability()
    events = InMemoryRunEventRepository()
    recorder = RunEventRecorder(repository=events, observability=telemetry)
    identity = EventIdentity(
        execution_id="run-redaction-1",
        session_id="session-observability",
        workflow_id=get_settings().workflow_id,
        workflow_version="1",
    )

    with telemetry.span(
        "privacy.test",
        {
            "provider": "fixture",
            "prompt": "private portfolio details",
            "message": "my holdings",
            "token": "secret",
        },
    ):
        recorder.record(
            identity,
            event_type=EventType.NODE_COMPLETED,
            status=EventStatus.COMPLETED,
            node_id="privacy-test",
            summary="authorization: Bearer super-secret",
            safe_metadata={
                "provider": "fixture",
                "prompt": "private portfolio details",
                "token": "secret",
            },
            completed=True,
        )

    event = events.list_for_run(
        "run-redaction-1",
        session_id="session-observability",
    )[0]
    assert "super-secret" not in event.summary
    assert event.safe_metadata == {"provider": "fixture"}
    assert telemetry.spans[0].attributes == {"provider": "fixture"}


def test_langsmith_context_hides_inputs_and_outputs_by_default(
    monkeypatch: MonkeyPatch,
) -> None:
    client_options: dict[str, object] = {}
    context_options: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

    @contextmanager
    def fake_context(**kwargs: object) -> Generator[None, None, None]:
        context_options.update(kwargs)
        yield

    monkeypatch.setattr("ai_finance_assistant.observability.langsmith.Client", FakeClient)
    monkeypatch.setattr(
        "ai_finance_assistant.observability.langsmith.tracing_context",
        fake_context,
    )

    with LangSmithTracing(
        enabled=True,
        project="m4-private",
        api_key="not-a-real-key",
    ).activate():
        pass

    assert client_options["hide_inputs"] is True
    assert client_options["hide_outputs"] is True
    assert context_options["enabled"] is True
    assert context_options["metadata"] == {"privacy_mode": "inputs_outputs_hidden"}


def test_langsmith_client_failure_does_not_change_product_behavior(
    monkeypatch: MonkeyPatch,
) -> None:
    class FailingClient:
        def __init__(self, **kwargs: object) -> None:
            del kwargs
            raise RuntimeError("LangSmith is unavailable")

    monkeypatch.setattr("ai_finance_assistant.observability.langsmith.Client", FailingClient)

    reached_product_code = False
    with LangSmithTracing(
        enabled=True,
        project="m4-private",
        api_key="not-a-real-key",
    ).activate():
        reached_product_code = True

    assert reached_product_code is True


def test_observability_modes_are_configuration_owned_and_safe_without_exporter() -> None:
    disabled = observability_from_settings(Settings(mode="test", observability_mode="disabled"))
    in_memory = observability_from_settings(Settings(mode="test", observability_mode="in_memory"))
    open_telemetry = observability_from_settings(
        Settings(mode="test", observability_mode="opentelemetry")
    )

    with disabled.span("disabled") as disabled_trace:
        pass
    with in_memory.span("in-memory") as memory_trace:
        pass
    with open_telemetry.span("open-telemetry") as otel_trace:
        pass

    assert disabled_trace.trace_id is None
    assert memory_trace.trace_id is not None
    assert otel_trace.trace_id is not None


def test_opentelemetry_resource_uses_configured_service_name() -> None:
    settings = Settings(
        mode="test",
        observability_mode="opentelemetry",
        otel_service_name="configured-telemetry-service",
    )
    runtime = telemetry_runtime_from_settings(settings)

    try:
        assert runtime.tracer_provider is not None
        assert (
            runtime.tracer_provider.resource.attributes["service.name"]
            == "configured-telemetry-service"
        )
    finally:
        runtime.shutdown()
