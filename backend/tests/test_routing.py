import json
from pathlib import Path
from typing import TypedDict, cast

from ai_finance_assistant.contracts.agents import AgentId
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

    router = IntentRouter()
    mismatches: list[str] = []
    for case in cases:
        decision = router.route(
            case["message"],
            previous_agent_ids=tuple(AgentId(item) for item in case.get("previous", [])),
        )
        actual = [item.value for item in decision.selected_agent_ids]
        if actual != case["expected"]:
            mismatches.append(f"{case['id']}: expected {case['expected']}, got {actual}")

    assert not mismatches, "\n".join(mismatches)
