import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict, cast

from ai_finance_assistant.contracts.agents import AgentId
from ai_finance_assistant.llm.fake import DeterministicModelAdapter
from ai_finance_assistant.llm.models import RoutingModelOutput, RoutingReason
from ai_finance_assistant.workflow.routing import IntentRouter


class RoutingCase(TypedDict, total=False):
    id: str
    message: str
    previous: list[str]
    expected: list[str]


def test_versioned_routing_dataset_meets_m4_gate() -> None:
    dataset_path = Path(__file__).parents[1] / "data/workflow/routing_cases.v1.json"
    payload = cast(dict[str, object], json.loads(dataset_path.read_text()))
    cases = cast(list[RoutingCase], payload["cases"])
    assert len(cases) >= 40

    responses = {
        case["message"]: RoutingModelOutput(
            selected_agent_ids=tuple(AgentId(item) for item in case["expected"]),
            reason_category=(
                RoutingReason.CHECKPOINT_FOLLOW_UP
                if case.get("previous")
                else RoutingReason.CLARIFICATION_REQUIRED
                if not case["expected"]
                else RoutingReason.SINGLE_DOMAIN
                if len(case["expected"]) == 1
                else RoutingReason.MULTI_DOMAIN
            ),
        )
        for case in cases
    }
    router = IntentRouter(model=DeterministicModelAdapter(routing_responses=responses))
    mismatches: list[str] = []
    for case in cases:
        decision = router.route(
            case["message"],
            previous_agent_ids=tuple(AgentId(item) for item in case.get("previous", [])),
            deadline_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        actual = [item.value for item in decision.selected_agent_ids]
        if actual != case["expected"]:
            mismatches.append(f"{case['id']}: expected {case['expected']}, got {actual}")

    assert not mismatches, "\n".join(mismatches)
