from pathlib import Path

from ai_finance_assistant.knowledge.representations import DeterministicTestEncoder
from ai_finance_assistant.response_cache.evaluation import evaluate_dataset, load_dataset


def test_frozen_calibration_set_covers_both_rags_and_critical_exclusions() -> None:
    path = Path(__file__).parents[1] / "data/response_cache/calibration.v1.json"
    dataset = load_dataset(path)

    assert len(dataset.cases) >= 16
    assert {item.agent_id.value for item in dataset.cases if item.route_eligible} >= {
        "finance_qa",
        "tax_education",
    }
    assert {item.relationship.value for item in dataset.cases} == {
        "exact",
        "safe_paraphrase",
        "near_miss",
        "adversarial",
    }
    assert any(item.critical and not item.route_eligible for item in dataset.cases)


def test_calibration_report_cannot_enable_unreviewed_semantic_hits() -> None:
    path = Path(__file__).parents[1] / "data/response_cache/calibration.v1.json"
    report = evaluate_dataset(
        load_dataset(path),
        encoder=DeterministicTestEncoder(),
        minimum_similarity=0.0,
    )

    assert report.proposed_semantic_hit_count > 0
    assert report.unreviewed_proposed_hit_count > 0
    assert report.serving_gate_passed is False
