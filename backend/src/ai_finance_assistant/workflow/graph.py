"""Deep LangGraph workflow module for routing, execution, and synthesis."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Annotated, Any, Protocol, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentRequest,
    AgentResult,
    AgentResultStatus,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.contracts.events import EventStatus, EventType, RoutingMetadata
from ai_finance_assistant.observability.ports import Observability
from ai_finance_assistant.workflow.events import EventIdentity, RunEventRecorder
from ai_finance_assistant.workflow.models import (
    WorkflowRequest,
    WorkflowRunResult,
    WorkflowStatus,
)
from ai_finance_assistant.workflow.routing import IntentRouter


class SpecialistAgent(Protocol):
    agent_id: AgentId

    def invoke(self, request: AgentRequest) -> AgentResult: ...


def _merge_agent_results(
    current: dict[str, AgentResult], update: dict[str, AgentResult]
) -> dict[str, AgentResult]:
    return {**current, **update}


class FinanceState(TypedDict, total=False):
    execution_id: str
    session_id: str
    workflow_id: str
    workflow_version: str
    message: str
    context_references: tuple[str, ...]
    locale: str
    jurisdiction: str
    deadline_at: datetime
    selected_agent_ids: tuple[AgentId, ...]
    route_reason_category: str
    agent_results: Annotated[dict[str, AgentResult], _merge_agent_results]
    final_status: WorkflowStatus
    final_summary: str
    final_warnings: tuple[str, ...]
    final_errors: tuple[SafeError, ...]


class FinanceWorkflow:
    def __init__(
        self,
        *,
        agents: Mapping[AgentId, SpecialistAgent],
        event_recorder: RunEventRecorder,
        observability: Observability,
        router: IntentRouter | None = None,
        checkpointer: BaseCheckpointSaver[str] | None = None,
        maximum_graph_hops: int = 16,
    ) -> None:
        if set(agents) != set(AgentId):
            raise ValueError("FinanceWorkflow requires exactly the six specialist agents")
        self._agents = dict(agents)
        self._events = event_recorder
        self._observability = observability
        self._router = router or IntentRouter()
        self._checkpointer = checkpointer or InMemorySaver()
        self._maximum_graph_hops = maximum_graph_hops
        self._graph = self._build_graph()

    def run(self, request: WorkflowRequest) -> WorkflowRunResult:
        run_started_monotonic = monotonic()
        identity = EventIdentity(
            execution_id=request.execution_id,
            session_id=request.session_id,
            workflow_id=request.workflow_id,
            workflow_version=request.workflow_version,
        )
        attributes = {
            "workflow_version": request.workflow_version,
            "operation": "workflow_run",
        }
        with self._observability.span("finance.workflow.run", attributes) as trace:
            started = self._events.record(
                identity,
                event_type=EventType.RUN_STARTED,
                status=EventStatus.RUNNING,
                node_id="workflow",
                summary="Workflow execution started.",
            )
            try:
                raw_state = self._graph.invoke(
                    {
                        "execution_id": request.execution_id,
                        "session_id": request.session_id,
                        "workflow_id": request.workflow_id,
                        "workflow_version": request.workflow_version,
                        "message": request.message,
                        "context_references": request.context_references,
                        "locale": request.locale,
                        "jurisdiction": request.jurisdiction,
                        "deadline_at": request.deadline_at,
                    },
                    {
                        "configurable": {
                            "thread_id": f"{request.session_id}:{request.workflow_id}"
                        },
                        "recursion_limit": self._maximum_graph_hops,
                    },
                )
                state = cast(FinanceState, raw_state)
            except Exception:
                error = SafeError(
                    code="WORKFLOW_EXECUTION_FAILED",
                    category=ErrorCategory.INTERNAL,
                    message="The workflow could not complete safely.",
                    retryable=False,
                )
                self._events.record(
                    identity,
                    event_type=EventType.RUN_FAILED,
                    status=EventStatus.FAILED,
                    node_id="workflow",
                    summary="Workflow execution failed.",
                    error=error,
                    started_at=started.started_at,
                    completed=True,
                    parent_event_id=started.event_id,
                )
                self._observability.count(
                    "workflow.runs",
                    1,
                    {"result_status": WorkflowStatus.FAILED.value},
                )
                self._observability.observe(
                    "workflow.duration_ms",
                    (monotonic() - run_started_monotonic) * 1_000,
                    {"result_status": WorkflowStatus.FAILED.value},
                )
                return WorkflowRunResult(
                    execution_id=request.execution_id,
                    session_id=request.session_id,
                    workflow_id=request.workflow_id,
                    workflow_version=request.workflow_version,
                    status=WorkflowStatus.FAILED,
                    selected_agent_ids=(),
                    agent_results=(),
                    summary="The workflow could not complete safely.",
                    errors=(error,),
                    trace_id=trace.trace_id,
                    trace_unavailable_reason=(
                        None if trace.trace_id else "Observability trace is unavailable."
                    ),
                )

            status = state["final_status"]
            terminal_event_type = {
                WorkflowStatus.COMPLETED: EventType.RUN_COMPLETED,
                WorkflowStatus.PARTIAL: EventType.RUN_PARTIAL,
                WorkflowStatus.FAILED: EventType.RUN_FAILED,
                WorkflowStatus.CLARIFICATION: EventType.RUN_PARTIAL,
            }[status]
            terminal_event_status = {
                WorkflowStatus.COMPLETED: EventStatus.COMPLETED,
                WorkflowStatus.PARTIAL: EventStatus.PARTIAL,
                WorkflowStatus.FAILED: EventStatus.FAILED,
                WorkflowStatus.CLARIFICATION: EventStatus.PARTIAL,
            }[status]
            selected = state.get("selected_agent_ids", ())
            result_map = state.get("agent_results", {})
            results = tuple(result_map[agent_id.value] for agent_id in selected)
            errors = state.get("final_errors", ())
            self._events.record(
                identity,
                event_type=terminal_event_type,
                status=terminal_event_status,
                node_id="workflow",
                summary=f"Workflow finished with {status.value} status.",
                error=errors[0] if terminal_event_status == EventStatus.FAILED else None,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            self._observability.count(
                "workflow.runs",
                1,
                {"result_status": status.value},
            )
            self._observability.observe(
                "workflow.duration_ms",
                (monotonic() - run_started_monotonic) * 1_000,
                {"result_status": status.value},
            )
            return WorkflowRunResult(
                execution_id=request.execution_id,
                session_id=request.session_id,
                workflow_id=request.workflow_id,
                workflow_version=request.workflow_version,
                status=status,
                selected_agent_ids=selected,
                agent_results=results,
                summary=state["final_summary"],
                warnings=state.get("final_warnings", ()),
                errors=errors,
                trace_id=trace.trace_id,
                trace_unavailable_reason=(
                    None if trace.trace_id else "Observability trace is unavailable."
                ),
            )

    def mermaid_diagram(self) -> str:
        return self._graph.get_graph().draw_mermaid()

    def _build_graph(
        self,
    ) -> CompiledStateGraph[FinanceState, None, FinanceState, FinanceState]:
        builder: StateGraph[FinanceState, None, FinanceState, FinanceState] = StateGraph(
            FinanceState
        )
        builder.add_node("router", self._route_node)
        for agent_id, agent in self._agents.items():
            builder.add_node(agent_id.value, cast(Any, self._agent_node(agent)))
            builder.add_edge(agent_id.value, "synthesize")
        builder.add_node("synthesize", self._synthesize_node)
        builder.add_edge(START, "router")
        path_map: dict[Hashable, str] = {agent_id.value: agent_id.value for agent_id in AgentId}
        path_map["synthesize"] = "synthesize"
        builder.add_conditional_edges("router", self._next_nodes, path_map)
        builder.add_edge("synthesize", END)
        return builder.compile(checkpointer=self._checkpointer)

    def _route_node(self, state: FinanceState) -> FinanceState:
        identity = self._identity(state)
        decision = self._router.route(
            state["message"],
            previous_agent_ids=state.get("selected_agent_ids", ()),
        )
        self._events.record(
            identity,
            event_type=EventType.ROUTE_SELECTED,
            status=EventStatus.COMPLETED,
            node_id="router",
            summary="Routing decision recorded.",
            routing=RoutingMetadata(
                selected_node_ids=tuple(item.value for item in decision.selected_agent_ids),
                outcome=(
                    "Selected specialist agents."
                    if decision.selected_agent_ids
                    else "More information is required."
                ),
                reason_category=decision.reason_category,
            ),
            completed=True,
        )
        return {
            "selected_agent_ids": decision.selected_agent_ids,
            "route_reason_category": decision.reason_category,
        }

    @staticmethod
    def _next_nodes(state: FinanceState) -> list[str]:
        selected = state.get("selected_agent_ids", ())
        return [item.value for item in selected] if selected else ["synthesize"]

    def _agent_node(
        self,
        agent: SpecialistAgent,
    ) -> Callable[[FinanceState], FinanceState]:
        def invoke(state: FinanceState) -> FinanceState:
            identity = self._identity(state)
            started = self._events.record(
                identity,
                event_type=EventType.NODE_STARTED,
                status=EventStatus.RUNNING,
                node_id=agent.agent_id.value,
                agent_id=agent.agent_id,
                summary=f"{agent.agent_id.value} started.",
            )
            if state["deadline_at"] <= datetime.now(UTC):
                error = SafeError(
                    code="AGENT_DEADLINE_EXCEEDED",
                    category=ErrorCategory.TIMEOUT,
                    message="The workflow deadline expired before agent execution.",
                    retryable=True,
                )
                result = AgentResult(
                    agent_id=agent.agent_id,
                    status=AgentResultStatus.ERROR,
                    summary=error.message,
                    errors=(error,),
                )
            else:
                request = AgentRequest(
                    execution_id=state["execution_id"],
                    session_id=state["session_id"],
                    workflow_id=state["workflow_id"],
                    workflow_version=state["workflow_version"],
                    agent_id=agent.agent_id,
                    message=state["message"],
                    context_references=state.get("context_references", ()),
                    locale=state["locale"],
                    jurisdiction=state["jurisdiction"],
                    deadline_at=state["deadline_at"],
                )
                try:
                    with self._observability.span(
                        f"agent.{agent.agent_id.value}",
                        {"agent_id": agent.agent_id.value},
                    ):
                        result = agent.invoke(request)
                except Exception:
                    error = SafeError(
                        code="AGENT_EXECUTION_FAILED",
                        category=ErrorCategory.INTERNAL,
                        message=f"{agent.agent_id.value} could not complete safely.",
                        retryable=False,
                    )
                    result = AgentResult(
                        agent_id=agent.agent_id,
                        status=AgentResultStatus.ERROR,
                        summary=error.message,
                        errors=(error,),
                    )
            failed = result.status == AgentResultStatus.ERROR
            self._events.record(
                identity,
                event_type=EventType.NODE_FAILED if failed else EventType.NODE_COMPLETED,
                status=EventStatus.FAILED if failed else EventStatus.COMPLETED,
                node_id=agent.agent_id.value,
                agent_id=agent.agent_id,
                summary=f"{agent.agent_id.value} finished with {result.status.value} status.",
                error=result.errors[0] if failed else None,
                started_at=started.started_at,
                completed=True,
                parent_event_id=started.event_id,
            )
            return {"agent_results": {agent.agent_id.value: result}}

        return invoke

    @staticmethod
    def _synthesize_node(state: FinanceState) -> FinanceState:
        selected = state.get("selected_agent_ids", ())
        if not selected:
            return {
                "final_status": WorkflowStatus.CLARIFICATION,
                "final_summary": (
                    "Please clarify whether you need finance education, portfolio analysis, "
                    "market data, goal planning, news, or U.S. tax education."
                ),
                "final_warnings": (),
                "final_errors": (),
            }
        result_map = state.get("agent_results", {})
        results = tuple(result_map[item.value] for item in selected)
        ok_results = tuple(item for item in results if item.status == AgentResultStatus.OK)
        partial_results = tuple(
            item for item in results if item.status == AgentResultStatus.PARTIAL
        )
        clarification_results = tuple(
            item for item in results if item.status == AgentResultStatus.CLARIFICATION
        )
        errors = tuple(error for item in results for error in item.errors)
        if len(ok_results) == len(results):
            status = WorkflowStatus.COMPLETED
        elif ok_results or partial_results:
            status = WorkflowStatus.PARTIAL
        elif clarification_results and not errors:
            status = WorkflowStatus.CLARIFICATION
        else:
            status = WorkflowStatus.FAILED
        summary = " ".join(item.summary for item in results)[:512]
        warnings = tuple(warning for item in results for warning in item.warnings)
        return {
            "final_status": status,
            "final_summary": summary,
            "final_warnings": warnings,
            "final_errors": errors,
        }

    @staticmethod
    def _identity(state: FinanceState) -> EventIdentity:
        return EventIdentity(
            execution_id=state["execution_id"],
            session_id=state["session_id"],
            workflow_id=state["workflow_id"],
            workflow_version=state["workflow_version"],
        )
