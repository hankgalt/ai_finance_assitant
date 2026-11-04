import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from ai_finance_assistant.finance.cash_flow import CashFlowSummary, MonthlyCashFlow
from ai_finance_assistant.finance.goal_projection import GoalProjection
from ai_finance_assistant.finance.models import (
    ContributionFrequency,
    ContributionTiming,
    GoalProjectionRequest,
    GoalScenario,
    RiskTolerance,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "calculations"


def request_for(
    *, contribution: str = "100", scenarios: tuple[GoalScenario, ...]
) -> GoalProjectionRequest:
    return GoalProjectionRequest(
        projection_id="goal-1",
        currency="USD",
        starting_amount=Decimal("1000"),
        goal_amount=Decimal("2500"),
        contribution_amount=Decimal(contribution),
        contribution_frequency=ContributionFrequency.MONTHLY,
        contribution_timing=ContributionTiming.END,
        horizon_months=12,
        risk_tolerance=RiskTolerance.MODERATE,
        scenarios=scenarios,
    )


def test_versioned_hand_worked_goal_goldens_reproduce_exactly() -> None:
    raw = json.loads((DATA_DIR / "goal-projection-cases.v1.json").read_text(encoding="utf-8"))
    for case in raw["cases"]:
        request = GoalProjectionRequest(
            projection_id=case["case_id"],
            currency="USD",
            starting_amount=Decimal(case["starting_amount"]),
            goal_amount=Decimal(case["goal_amount"]),
            contribution_amount=Decimal(case["contribution_amount"]),
            contribution_frequency=ContributionFrequency(case["contribution_frequency"]),
            contribution_timing=ContributionTiming(case["contribution_timing"]),
            horizon_months=case["horizon_months"],
            scenarios=(GoalScenario.model_validate(case["scenario"]),),
        )

        actual = GoalProjection().project(request).scenarios[0]

        for field, expected in case["expected"].items():
            assert getattr(actual, field) == Decimal(expected), (case["case_id"], field)


def test_zero_return_and_no_fees_equals_start_plus_contributions() -> None:
    scenario = GoalScenario(
        label="zero",
        annual_return_rate=Decimal("0"),
        annual_inflation_rate=Decimal("0"),
    )

    result = GoalProjection().project(request_for(scenarios=(scenario,))).scenarios[0]

    assert result.nominal_future_value == Decimal("2200.00")
    assert result.total_contributions == Decimal("1200.00")
    assert result.modeled_growth == Decimal("0.00")


def test_increasing_positive_contribution_cannot_reduce_nonnegative_scenario_value() -> None:
    scenarios = tuple(
        GoalScenario(
            label=f"return-{rate}",
            annual_return_rate=Decimal(rate),
            annual_inflation_rate=Decimal("0.02"),
            annual_fee_rate=Decimal("0.001"),
        )
        for rate in ("0.001", "0.03", "0.07", "0.15")
    )

    low = GoalProjection().project(request_for(contribution="50", scenarios=scenarios))
    high = GoalProjection().project(request_for(contribution="150", scenarios=scenarios))

    assert all(
        high_result.nominal_future_value >= low_result.nominal_future_value
        for low_result, high_result in zip(low.scenarios, high.scenarios, strict=True)
    )


def test_nominal_and_inflation_adjusted_results_remain_distinct() -> None:
    scenario = GoalScenario(
        label="inflation",
        annual_return_rate=Decimal("0.06"),
        annual_inflation_rate=Decimal("0.03"),
    )

    result = GoalProjection().project(request_for(scenarios=(scenario,))).scenarios[0]

    assert result.nominal_future_value > result.inflation_adjusted_value


def test_beginning_contributions_receive_one_more_period_of_growth() -> None:
    scenario = GoalScenario(
        label="positive",
        annual_return_rate=Decimal("0.12"),
        annual_inflation_rate=Decimal("0"),
    )
    end_request = request_for(scenarios=(scenario,))
    beginning_request = end_request.model_copy(
        update={"contribution_timing": ContributionTiming.BEGINNING}
    )

    end = GoalProjection().project(end_request).scenarios[0]
    beginning = GoalProjection().project(beginning_request).scenarios[0]

    assert beginning.contribution_count == end.contribution_count == 12
    assert beginning.nominal_future_value > end.nominal_future_value


def test_cash_flow_summary_is_minimized_context_and_cannot_change_contribution() -> None:
    summary = CashFlowSummary(
        summary_id="cash-summary-1",
        import_ids=("cash-import-1",),
        currency="USD",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        monthly=(
            MonthlyCashFlow(
                month="2026-01",
                income=Decimal("5000"),
                spending=Decimal("4000"),
                surplus=Decimal("1000"),
            ),
        ),
        average_monthly_income=Decimal("5000"),
        average_monthly_spending=Decimal("4000"),
        average_monthly_surplus=Decimal("1000"),
        categorized_coverage_ratio=Decimal("1"),
        unresolved_duplicate_count=0,
        unresolved_transfer_count=0,
    )
    scenario = GoalScenario(
        label="zero",
        annual_return_rate=Decimal("0"),
        annual_inflation_rate=Decimal("0"),
    )
    request = request_for(scenarios=(scenario,)).model_copy(
        update={"cash_flow_summary_id": summary.summary_id}
    )

    result = GoalProjection().project(request)

    assert result.scenarios[0].total_contributions == Decimal("1200.00")
    assert result.cash_flow_summary_id == "cash-summary-1"
    assert any("does not silently change" in warning for warning in result.warnings)
    assert "description" not in summary.model_dump_json()
