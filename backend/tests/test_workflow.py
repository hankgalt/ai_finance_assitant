from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver

from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentRequest,
    AgentResult,
    AgentResultStatus,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.observability.memory import InMemoryObservability
from ai_finance_assistant.workflow.events import InMemoryRunEventRepository, RunEventRecorder
from ai_finance_assistant.workflow.graph import FinanceWorkflow
from ai_finance_assistant.workflow.models import WorkflowRequest, WorkflowStatus


class StubAgent:
    def __init__(
        self,
        agent_id: AgentId,
        *,
        status: AgentResultStatus = AgentResultStatus.OK,
        raises: bool = False,
        summary: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.status = status
        self.raises = raises
        self.summary = summary
        self.requests: list[AgentRequest] = []

    def invoke(self, request: AgentRequest) -> AgentResult:
        self.requests.append(request)
        if self.raises:
            raise RuntimeError("unsafe internal detail")
        errors = (
            (
                SafeError(
                    code="STUB_FAILED",
                    category=ErrorCategory.UPSTREAM_UNAVAILABLE,
                    message=f"{self.agent_id.value} was unavailable.",
                ),
            )
            if self.status == AgentResultStatus.ERROR
            else ()
        )
        return AgentResult(
            agent_id=self.agent_id,
            status=self.status,
            summary=self.summary or f"{self.agent_id.value} handled the request.",
            errors=errors,
        )


def workflow_request(
    *,
    execution_id: str,
    session_id: str = "session-1",
    message: str,
    deadline_at: datetime | None = None,
) -> WorkflowRequest:
    return WorkflowRequest(
        execution_id=execution_id,
        session_id=session_id,
        workflow_id="finance-assistant",
        workflow_version="1",
        message=message,
        deadline_at=deadline_at or datetime.now(UTC) + timedelta(minutes=1),
    )


def test_workflow_routes_finance_question_through_langgraph() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-finance-1",
            message="What is an ETF and how does diversification work?",
        )
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert [item.agent_id for item in result.agent_results] == [AgentId.FINANCE_QA]
    assert len(agents[AgentId.FINANCE_QA].requests) == 1
    assert all(
        not agent.requests for agent_id, agent in agents.items() if agent_id != AgentId.FINANCE_QA
    )
    recorded = events.list_for_run("run-finance-1", session_id="session-1")
    assert [event.sequence for event in recorded] == list(range(1, len(recorded) + 1))
    assert any(event.event_type.value == "route_selected" for event in recorded)
    assert recorded[-1].event_type.value == "run_completed"
    assert telemetry.spans


def test_workflow_result_preserves_response_while_run_events_exclude_it() -> None:
    private_response = "MODEL_RESPONSE_SENTINEL must remain outside persisted RunEvents."
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    agents[AgentId.FINANCE_QA] = StubAgent(
        AgentId.FINANCE_QA,
        summary=private_response,
    )
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-private-response-1",
            message="What is diversification?",
        )
    )

    assert private_response in result.summary
    recorded = events.list_for_run("run-private-response-1", session_id="session-1")
    assert all(private_response not in event.model_dump_json() for event in recorded)


def test_workflow_preserves_multi_agent_result_when_one_agent_fails() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    agents[AgentId.TAX_EDUCATION] = StubAgent(AgentId.TAX_EDUCATION, raises=True)
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-partial-1",
            message="Explain an ETF and capital gain tax.",
        )
    )

    assert result.status == WorkflowStatus.PARTIAL
    assert result.selected_agent_ids == (AgentId.FINANCE_QA, AgentId.TAX_EDUCATION)
    assert [item.status for item in result.agent_results] == [
        AgentResultStatus.OK,
        AgentResultStatus.ERROR,
    ]
    assert result.errors[0].code == "AGENT_EXECUTION_FAILED"
    recorded = events.list_for_run("run-partial-1", session_id="session-1")
    assert recorded[-1].event_type.value == "run_partial"


def test_workflow_requests_clarification_for_unroutable_message() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
    )

    result = workflow.run(
        workflow_request(execution_id="run-clarify-1", message="Please help me with this.")
    )

    assert result.status == WorkflowStatus.CLARIFICATION
    assert result.selected_agent_ids == ()
    assert all(not agent.requests for agent in agents.values())


def test_workflow_enforces_deadline_before_agent_execution() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=telemetry,
        ),
        observability=telemetry,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-deadline-1",
            message="What is an ETF?",
            deadline_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    assert result.status == WorkflowStatus.FAILED
    assert result.errors[0].code == "AGENT_DEADLINE_EXCEEDED"
    assert all(not agent.requests for agent in agents.values())


def test_checkpoint_restart_supports_follow_up_and_isolates_sessions() -> None:
    checkpointer = InMemorySaver()
    telemetry = InMemoryObservability()
    repository = InMemoryRunEventRepository()

    def make_workflow() -> FinanceWorkflow:
        return FinanceWorkflow(
            agents={agent_id: StubAgent(agent_id) for agent_id in AgentId},
            event_recorder=RunEventRecorder(
                repository=repository,
                observability=telemetry,
            ),
            observability=telemetry,
            checkpointer=checkpointer,
        )

    first = make_workflow().run(
        workflow_request(execution_id="run-checkpoint-1", message="What is an ETF?")
    )
    restarted = make_workflow().run(
        workflow_request(execution_id="run-checkpoint-2", message="Explain that another way.")
    )
    isolated = make_workflow().run(
        workflow_request(
            execution_id="run-checkpoint-3",
            session_id="session-2",
            message="Explain that another way.",
        )
    )

    assert first.selected_agent_ids == (AgentId.FINANCE_QA,)
    assert restarted.selected_agent_ids == (AgentId.FINANCE_QA,)
    assert restarted.status == WorkflowStatus.COMPLETED
    assert isolated.status == WorkflowStatus.CLARIFICATION


def test_workflow_fails_safely_when_graph_hop_bound_is_too_small() -> None:
    telemetry = InMemoryObservability()
    events = InMemoryRunEventRepository()
    workflow = FinanceWorkflow(
        agents={agent_id: StubAgent(agent_id) for agent_id in AgentId},
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        maximum_graph_hops=2,
    )

    result = workflow.run(workflow_request(execution_id="run-hop-1", message="What is an ETF?"))

    assert result.status == WorkflowStatus.FAILED
    assert result.errors[0].code == "WORKFLOW_EXECUTION_FAILED"
    recorded = events.list_for_run("run-hop-1", session_id="session-1")
    assert recorded[-1].event_type.value == "run_failed"
