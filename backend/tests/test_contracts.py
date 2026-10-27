import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_finance_assistant.contracts.agents import AgentId, AgentRequest
from ai_finance_assistant.contracts.events import (
    EventStatus,
    EventType,
    RoutingMetadata,
    RunEvent,
)

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def base_event(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_id": "evt-1",
        "execution_id": "run-1",
        "trace_id": None,
        "trace_unavailable_reason": "Synthetic M0 fixture has no external trace.",
        "session_id": "session-1",
        "workflow_id": "workflow-foundation",
        "workflow_version": "1",
        "sequence": 1,
        "node_id": "router",
        "event_type": EventType.NODE_STARTED,
        "status": EventStatus.RUNNING,
        "started_at": NOW,
        "completed_at": None,
        "duration_ms": None,
        "duration_unavailable_reason": "The synthetic event is still running.",
        "summary": "Synthetic router start.",
    }
    payload.update(overrides)
    return payload


def test_all_six_agent_identifiers_are_stable() -> None:
    assert {agent.value for agent in AgentId} == {
        "finance_qa",
        "portfolio_analysis",
        "market_analysis",
        "goal_planning",
        "news_synthesizer",
        "tax_education",
    }


def test_agent_request_requires_timezone_aware_deadline() -> None:
    with pytest.raises(ValidationError):
        AgentRequest(
            execution_id="run-1",
            session_id="session-1",
            workflow_id="workflow-1",
            workflow_version="1",
            agent_id=AgentId.FINANCE_QA,
            message="What is an ETF?",
            deadline_at=datetime(2026, 10, 27, 12, 5),
        )


def test_run_event_requires_missing_measurement_reasons() -> None:
    payload = base_event()
    payload["duration_unavailable_reason"] = None
    with pytest.raises(ValidationError, match="missing duration"):
        RunEvent.model_validate(payload)


def test_route_event_requires_structured_routing_metadata() -> None:
    with pytest.raises(ValidationError, match="routing metadata"):
        RunEvent.model_validate(
            base_event(event_type=EventType.ROUTE_SELECTED, status=EventStatus.COMPLETED)
        )

    event = RunEvent.model_validate(
        base_event(
            event_type=EventType.ROUTE_SELECTED,
            status=EventStatus.COMPLETED,
            completed_at=NOW + timedelta(milliseconds=5),
            duration_ms=5,
            duration_unavailable_reason=None,
            routing=RoutingMetadata(
                selected_node_ids=("finance_qa",),
                outcome="Selected one educational agent.",
                reason_category="single_domain",
            ),
        )
    )
    assert event.routing is not None
    assert event.routing.selected_node_ids == ("finance_qa",)


def test_shared_synthetic_fixture_matches_backend_contract() -> None:
    fixture_path = (
        Path(__file__).parents[2] / "contracts" / "fixtures" / "run-events.synthetic.v1.json"
    )
    events = json.loads(fixture_path.read_text(encoding="utf-8"))

    validated = [RunEvent.model_validate(event) for event in events]

    assert [event.sequence for event in validated] == [1, 2]
    assert validated[1].routing is not None
    assert validated[1].routing.selected_node_ids == ("finance_qa",)
