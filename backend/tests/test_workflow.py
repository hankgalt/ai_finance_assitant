from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver

from ai_finance_assistant.agents.context import (
    InMemoryAgentContextRepository,
    PortfolioAgentContext,
)
from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    EvidenceReference,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.contracts.events import EventType
from ai_finance_assistant.finance.models import ImportedPortfolio
from ai_finance_assistant.llm.errors import ModelErrorCode, ModelProviderError
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import (
    ModelAdapterResult,
    RoutingModelOutput,
    RoutingReason,
    SynthesisModelOutput,
    SynthesisModelRequest,
)
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
        evidence: tuple[EvidenceReference, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> None:
        self.agent_id = agent_id
        self.status = status
        self.raises = raises
        self.summary = summary
        self.evidence = evidence
        self.warnings = warnings
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
            evidence=self.evidence,
            warnings=self.warnings,
            errors=errors,
        )


class RecordingSynthesisModel(DeterministicModelAdapter):
    def __init__(
        self,
        *,
        routing_responses: dict[str, RoutingModelOutput],
        failure: ModelProviderError | None = None,
    ) -> None:
        super().__init__(routing_responses=routing_responses)
        self.synthesis_requests: list[SynthesisModelRequest] = []
        self.failure = failure

    def synthesize(self, request: SynthesisModelRequest) -> ModelAdapterResult:
        self.synthesis_requests.append(request)
        if self.failure is not None:
            raise self.failure
        output = SynthesisModelOutput(
            summary=(
                "Diversification describes investment-risk tradeoffs, while capital-gains "
                "tax treatment depends on the account and transaction facts."
            ),
            warnings=("Tax treatment is limited to the supplied U.S. federal evidence.",),
        )
        return ModelAdapterResult(payload=output.model_dump(mode="json"))


def model_for(
    message: str | None = None,
    *selected_agent_ids: AgentId,
    reason_category: RoutingReason | None = None,
) -> DeterministicModelAdapter:
    responses = {}
    if message is not None:
        responses[message] = RoutingModelOutput(
            selected_agent_ids=selected_agent_ids,
            reason_category=(
                reason_category or RoutingReason.CLARIFICATION_REQUIRED
                if not selected_agent_ids
                else reason_category
                or (
                    RoutingReason.SINGLE_DOMAIN
                    if len(selected_agent_ids) == 1
                    else RoutingReason.MULTI_DOMAIN
                )
            ),
        )
    return DeterministicModelAdapter(routing_responses=responses)


def workflow_request(
    *,
    execution_id: str,
    session_id: str = "session-1",
    message: str,
    deadline_at: datetime | None = None,
    context_references: tuple[str, ...] = (),
    continuation_of_execution_id: str | None = None,
    continuation_agent_ids: tuple[AgentId, ...] = (),
) -> WorkflowRequest:
    return WorkflowRequest(
        execution_id=execution_id,
        session_id=session_id,
        workflow_id="finance-assistant",
        workflow_version="1",
        message=message,
        context_references=context_references,
        continuation_of_execution_id=continuation_of_execution_id,
        continuation_agent_ids=continuation_agent_ids,
        deadline_at=deadline_at or datetime.now(UTC) + timedelta(minutes=1),
    )


def portfolio_contexts() -> InMemoryAgentContextRepository:
    contexts = InMemoryAgentContextRepository()
    contexts.put(
        "session-1",
        PortfolioAgentContext(
            context_id="portfolio-context",
            portfolio=ImportedPortfolio.model_validate(
                {
                    "portfolio_id": "portfolio-1",
                    "label": "Retirement portfolio",
                    "base_currency": "USD",
                    "imported_at": datetime.now(UTC),
                    "source_kind": "manual",
                    "source_file_hash": "a" * 64,
                    "accounts": [
                        {
                            "account_id": "account-1",
                            "portfolio_id": "portfolio-1",
                            "account_type": "taxable",
                            "holdings": [
                                {
                                    "holding_id": "holding-1",
                                    "account_id": "account-1",
                                    "source_row": 1,
                                    "security": {
                                        "identifier_type": "ticker",
                                        "value": "DEMO",
                                    },
                                    "quantity": "1",
                                    "currency": "USD",
                                }
                            ],
                        }
                    ],
                }
            ),
            calculated_at=datetime.now(UTC),
        ),
    )
    return contexts


def test_workflow_routes_finance_question_through_langgraph() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        model=model_for(
            "What is an ETF and how does diversification work?",
            AgentId.FINANCE_QA,
        ),
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
    private_response = " ".join(
        ["MODEL_RESPONSE_SENTINEL must remain outside persisted RunEvents."] * 20
    )
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
        model=model_for("What is diversification?", AgentId.FINANCE_QA),
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
        model=model_for(
            "Explain an ETF and capital gain tax.",
            AgentId.FINANCE_QA,
            AgentId.TAX_EDUCATION,
        ),
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


def test_workflow_uses_grounded_synthesis_for_multiple_successful_agents() -> None:
    message = "Explain diversification and the related capital-gains tax considerations."
    source = EvidenceReference(
        evidence_id="finance-source-1",
        title="Diversification bulletin",
        publisher="Investor Education Test Publisher",
        canonical_url="https://example.invalid/diversification",
    )
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    agents[AgentId.FINANCE_QA] = StubAgent(
        AgentId.FINANCE_QA,
        summary="Diversification can reduce concentration risk but cannot prevent loss.",
        evidence=(source,),
    )
    agents[AgentId.TAX_EDUCATION] = StubAgent(
        AgentId.TAX_EDUCATION,
        summary="Capital-gains treatment depends on the account and transaction facts.",
        warnings=("State and local taxes are outside the supplied evidence.",),
    )
    model = RecordingSynthesisModel(
        routing_responses={
            message: RoutingModelOutput(
                selected_agent_ids=(AgentId.FINANCE_QA, AgentId.TAX_EDUCATION),
                reason_category=RoutingReason.MULTI_DOMAIN,
            )
        }
    )
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        model=model,
    )

    result = workflow.run(workflow_request(execution_id="run-synthesis-1", message=message))

    assert result.status == WorkflowStatus.COMPLETED
    assert result.summary.startswith("Diversification describes investment-risk tradeoffs")
    assert [item.agent_id for item in result.agent_results] == [
        AgentId.FINANCE_QA,
        AgentId.TAX_EDUCATION,
    ]
    assert result.agent_results[0].evidence == (source,)
    assert len(model.synthesis_requests) == 1
    assert [item.agent_id for item in model.synthesis_requests[0].agent_results] == [
        AgentId.FINANCE_QA,
        AgentId.TAX_EDUCATION,
    ]
    assert result.warnings == (
        "State and local taxes are outside the supplied evidence.",
        "Tax treatment is limited to the supplied U.S. federal evidence.",
    )
    recorded = events.list_for_run("run-synthesis-1", session_id="session-1")
    assert any(
        event.event_type == EventType.MODEL_COMPLETED and event.node_id == "synthesize"
        for event in recorded
    )


def test_workflow_preserves_specialist_results_when_synthesis_fails() -> None:
    message = "Explain diversification and capital-gains tax."
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    agents[AgentId.FINANCE_QA] = StubAgent(
        AgentId.FINANCE_QA,
        summary="Finance specialist result.",
    )
    agents[AgentId.TAX_EDUCATION] = StubAgent(
        AgentId.TAX_EDUCATION,
        summary="Tax specialist result.",
    )
    model = RecordingSynthesisModel(
        routing_responses={
            message: RoutingModelOutput(
                selected_agent_ids=(AgentId.FINANCE_QA, AgentId.TAX_EDUCATION),
                reason_category=RoutingReason.MULTI_DOMAIN,
            )
        },
        failure=ModelProviderError(
            code=ModelErrorCode.RATE_LIMITED,
            message="The model provider rate limit was reached.",
            retryable=True,
        ),
    )
    events = InMemoryRunEventRepository()
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(repository=events, observability=telemetry),
        observability=telemetry,
        model=model,
    )

    result = workflow.run(workflow_request(execution_id="run-synthesis-failure-1", message=message))

    assert result.status == WorkflowStatus.PARTIAL
    assert result.summary == "Finance specialist result.\n\nTax specialist result."
    assert len(result.agent_results) == 2
    assert result.errors[-1].code == "MODEL_RATE_LIMITED"
    assert "unified multi-domain summary is unavailable" in result.warnings[-1]
    recorded = events.list_for_run("run-synthesis-failure-1", session_id="session-1")
    assert any(
        event.event_type == EventType.MODEL_FAILED and event.node_id == "synthesize"
        for event in recorded
    )


def test_single_specialist_run_does_not_consume_synthesis_request() -> None:
    message = "What is diversification?"
    model = RecordingSynthesisModel(
        routing_responses={
            message: RoutingModelOutput(
                selected_agent_ids=(AgentId.FINANCE_QA,),
                reason_category=RoutingReason.SINGLE_DOMAIN,
            )
        }
    )
    telemetry = InMemoryObservability()
    workflow = FinanceWorkflow(
        agents={agent_id: StubAgent(agent_id) for agent_id in AgentId},
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=telemetry,
        ),
        observability=telemetry,
        model=model,
    )

    result = workflow.run(
        workflow_request(execution_id="run-single-no-synthesis-1", message=message)
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert model.synthesis_requests == []


def test_workflow_requests_clarification_for_unroutable_message() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(),
    )

    result = workflow.run(
        workflow_request(execution_id="run-clarify-1", message="Please help me with this.")
    )

    assert result.status == WorkflowStatus.CLARIFICATION
    assert result.selected_agent_ids == ()
    assert all(not agent.requests for agent in agents.values())


def test_workflow_returns_bounded_response_for_out_of_scope_question() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(
            "How's the weather?",
            reason_category=RoutingReason.OUT_OF_SCOPE,
        ),
    )

    result = workflow.run(
        workflow_request(execution_id="run-out-of-scope-1", message="How's the weather?")
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.selected_agent_ids == ()
    assert "can't answer unrelated general-knowledge questions" in result.summary
    assert all(not agent.requests for agent in agents.values())


def test_portfolio_route_conditionally_requests_context_before_agent_execution() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    events = InMemoryRunEventRepository()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=events,
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(
            "How many holdings have usable prices?",
            AgentId.PORTFOLIO_ANALYSIS,
        ),
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-portfolio-context-required",
            message="How many holdings have usable prices?",
        )
    )

    assert result.status == WorkflowStatus.CLARIFICATION
    assert result.required_input is not None
    assert result.required_input.kind.value == "portfolio_selection"
    assert not agents[AgentId.PORTFOLIO_ANALYSIS].requests
    recorded = events.list_for_run(
        "run-portfolio-context-required",
        session_id="session-1",
    )
    assert any(event.node_id == "context_gate" for event in recorded)
    assert any(event.node_id == "portfolio_context_required" for event in recorded)


def test_portfolio_route_resolves_unique_explicitly_quoted_session_label() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    events = InMemoryRunEventRepository()
    message = (
        "Using my saved \u201cRetirement portfolio,\u201d provide an educational "
        "diversification review."
    )
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=events,
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(message, AgentId.PORTFOLIO_ANALYSIS),
        contexts=portfolio_contexts(),
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-portfolio-explicit-label",
            message=message,
        )
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.required_input is None
    assert len(agents[AgentId.PORTFOLIO_ANALYSIS].requests) == 1
    assert agents[AgentId.PORTFOLIO_ANALYSIS].requests[0].context_references == (
        "portfolio-context",
    )
    recorded = events.list_for_run(
        "run-portfolio-explicit-label",
        session_id="session-1",
    )
    assert not any(event.node_id == "portfolio_context_required" for event in recorded)


def test_portfolio_route_keeps_selection_for_ambiguous_explicit_label() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    contexts = portfolio_contexts()
    existing = contexts.get("session-1", "portfolio-context")
    assert isinstance(existing, PortfolioAgentContext)
    contexts.put(
        "session-1",
        existing.model_copy(
            update={
                "context_id": "portfolio-context-duplicate",
                "portfolio": existing.portfolio.model_copy(
                    update={"portfolio_id": "portfolio-duplicate"}
                ),
            }
        ),
    )
    message = 'Analyze my saved "Retirement portfolio".'
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(message, AgentId.PORTFOLIO_ANALYSIS),
        contexts=contexts,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-portfolio-ambiguous-label",
            message=message,
        )
    )

    assert result.status == WorkflowStatus.CLARIFICATION
    assert result.required_input is not None
    assert not agents[AgentId.PORTFOLIO_ANALYSIS].requests


def test_portfolio_route_never_resolves_a_label_from_another_session() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    contexts = portfolio_contexts()
    existing = contexts.get("session-1", "portfolio-context")
    assert isinstance(existing, PortfolioAgentContext)
    contexts = InMemoryAgentContextRepository()
    contexts.put("another-session", existing)
    message = 'Analyze my saved "Retirement portfolio".'
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(message, AgentId.PORTFOLIO_ANALYSIS),
        contexts=contexts,
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-portfolio-cross-session-label",
            message=message,
        )
    )

    assert result.status == WorkflowStatus.CLARIFICATION
    assert result.required_input is not None
    assert not agents[AgentId.PORTFOLIO_ANALYSIS].requests


def test_portfolio_continuation_enters_context_gate_without_reclassification() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    events = InMemoryRunEventRepository()
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=events,
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(),
        contexts=portfolio_contexts(),
    )

    result = workflow.run(
        workflow_request(
            execution_id="run-portfolio-continuation",
            message="How many holdings have usable prices?",
            context_references=("portfolio-context",),
            continuation_of_execution_id="run-portfolio-context-required",
            continuation_agent_ids=(AgentId.PORTFOLIO_ANALYSIS,),
        )
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.continuation_of_execution_id == "run-portfolio-context-required"
    assert result.portfolio_context_references == ("portfolio-context",)
    assert len(agents[AgentId.PORTFOLIO_ANALYSIS].requests) == 1
    recorded = events.list_for_run("run-portfolio-continuation", session_id="session-1")
    assert not any(event.node_id == "router" for event in recorded)
    assert any(event.node_id == "context_gate" for event in recorded)


def test_portfolio_follow_up_reuses_scope_but_executes_a_new_agent_result() -> None:
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(
            "How many holdings have usable prices?",
            AgentId.PORTFOLIO_ANALYSIS,
        ),
        contexts=portfolio_contexts(),
    )

    completed = workflow.run(
        workflow_request(
            execution_id="run-portfolio-with-context",
            message="How many holdings have usable prices?",
            context_references=("portfolio-context",),
        )
    )
    follow_up = workflow.run(
        workflow_request(
            execution_id="run-portfolio-follow-up",
            message="How many holdings have usable prices?",
        )
    )

    assert completed.status == WorkflowStatus.COMPLETED
    assert len(completed.agent_results) == 1
    assert completed.portfolio_context_references == ("portfolio-context",)
    assert follow_up.status == WorkflowStatus.COMPLETED
    assert follow_up.required_input is None
    assert follow_up.portfolio_context_references == ("portfolio-context",)
    assert len(follow_up.agent_results) == 1
    assert len(agents[AgentId.PORTFOLIO_ANALYSIS].requests) == 2
    assert agents[AgentId.PORTFOLIO_ANALYSIS].requests[1].execution_id == (
        "run-portfolio-follow-up"
    )


def test_portfolio_follow_up_can_switch_scope_with_a_unique_quoted_label() -> None:
    first_message = "Analyze my portfolio."
    second_message = 'Now analyze my saved "Taxable portfolio".'
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    contexts = portfolio_contexts()
    existing = contexts.get("session-1", "portfolio-context")
    assert isinstance(existing, PortfolioAgentContext)
    contexts.put(
        "session-1",
        existing.model_copy(
            update={
                "context_id": "taxable-context",
                "portfolio": existing.portfolio.model_copy(
                    update={
                        "portfolio_id": "taxable-portfolio",
                        "label": "Taxable portfolio",
                    }
                ),
            }
        ),
    )
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=DeterministicModelAdapter(
            routing_responses={
                first_message: RoutingModelOutput(
                    selected_agent_ids=(AgentId.PORTFOLIO_ANALYSIS,),
                    reason_category=RoutingReason.SINGLE_DOMAIN,
                ),
                second_message: RoutingModelOutput(
                    selected_agent_ids=(AgentId.PORTFOLIO_ANALYSIS,),
                    reason_category=RoutingReason.SINGLE_DOMAIN,
                ),
            }
        ),
        contexts=contexts,
    )

    first = workflow.run(
        workflow_request(
            execution_id="run-portfolio-active-first",
            message=first_message,
            context_references=("portfolio-context",),
        )
    )
    switched = workflow.run(
        workflow_request(
            execution_id="run-portfolio-active-switch",
            message=second_message,
        )
    )

    assert first.portfolio_context_references == ("portfolio-context",)
    assert switched.status == WorkflowStatus.COMPLETED
    assert switched.portfolio_context_references == ("taxable-context",)
    assert agents[AgentId.PORTFOLIO_ANALYSIS].requests[-1].context_references == (
        "taxable-context",
    )


def test_invalid_explicit_portfolio_switch_does_not_fall_back_to_active_scope() -> None:
    message = "Analyze my portfolio."
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(message, AgentId.PORTFOLIO_ANALYSIS),
        contexts=portfolio_contexts(),
    )

    first = workflow.run(
        workflow_request(
            execution_id="run-portfolio-active-valid",
            message=message,
            context_references=("portfolio-context",),
        )
    )
    invalid_switch = workflow.run(
        workflow_request(
            execution_id="run-portfolio-active-invalid-switch",
            message=message,
            context_references=("deleted-or-cross-session-context",),
        )
    )

    assert first.status == WorkflowStatus.COMPLETED
    assert invalid_switch.status == WorkflowStatus.CLARIFICATION
    assert invalid_switch.portfolio_context_references == ()
    assert len(agents[AgentId.PORTFOLIO_ANALYSIS].requests) == 1


def test_portfolio_override_is_not_disclosed_to_an_unrelated_specialist() -> None:
    portfolio_message = "Analyze my portfolio."
    finance_message = "What is diversification?"
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=DeterministicModelAdapter(
            routing_responses={
                portfolio_message: RoutingModelOutput(
                    selected_agent_ids=(AgentId.PORTFOLIO_ANALYSIS,),
                    reason_category=RoutingReason.SINGLE_DOMAIN,
                ),
                finance_message: RoutingModelOutput(
                    selected_agent_ids=(AgentId.FINANCE_QA,),
                    reason_category=RoutingReason.SINGLE_DOMAIN,
                ),
            }
        ),
        contexts=portfolio_contexts(),
    )

    workflow.run(
        workflow_request(
            execution_id="run-portfolio-scope-established",
            message=portfolio_message,
            context_references=("portfolio-context",),
        )
    )
    finance_result = workflow.run(
        workflow_request(
            execution_id="run-finance-with-pending-portfolio-switch",
            message=finance_message,
            context_references=("portfolio-context",),
        )
    )

    assert finance_result.status == WorkflowStatus.COMPLETED
    assert agents[AgentId.FINANCE_QA].requests[-1].context_references == ()


def test_portfolio_active_scope_never_crosses_sessions() -> None:
    message = "Analyze my portfolio."
    agents = {agent_id: StubAgent(agent_id) for agent_id in AgentId}
    workflow = FinanceWorkflow(
        agents=agents,
        event_recorder=RunEventRecorder(
            repository=InMemoryRunEventRepository(),
            observability=InMemoryObservability(),
        ),
        observability=InMemoryObservability(),
        model=model_for(message, AgentId.PORTFOLIO_ANALYSIS),
        contexts=portfolio_contexts(),
    )

    session_one = workflow.run(
        workflow_request(
            execution_id="run-portfolio-session-one",
            message=message,
            context_references=("portfolio-context",),
        )
    )
    session_two = workflow.run(
        workflow_request(
            execution_id="run-portfolio-session-two",
            session_id="session-2",
            message=message,
        )
    )

    assert session_one.status == WorkflowStatus.COMPLETED
    assert session_two.status == WorkflowStatus.CLARIFICATION
    assert session_two.portfolio_context_references == ()


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
        model=model_for("What is an ETF?", AgentId.FINANCE_QA),
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
            model=model_for("What is an ETF?", AgentId.FINANCE_QA),
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
        model=model_for("What is an ETF?", AgentId.FINANCE_QA),
        maximum_graph_hops=2,
    )

    result = workflow.run(workflow_request(execution_id="run-hop-1", message="What is an ETF?"))

    assert result.status == WorkflowStatus.FAILED
    assert result.errors[0].code == "WORKFLOW_EXECUTION_FAILED"
    recorded = events.list_for_run("run-hop-1", session_id="session-1")
    assert recorded[-1].event_type.value == "run_failed"
