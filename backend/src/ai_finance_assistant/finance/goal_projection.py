"""Pure deterministic multi-scenario goal projections."""

from decimal import Decimal, localcontext

from ai_finance_assistant.finance.models import (
    ContributionTiming,
    GoalProjectionRequest,
    GoalProjectionResult,
    GoalScenario,
    GoalScenarioResult,
)
from ai_finance_assistant.finance.precision import money

_MONTHS_PER_YEAR = Decimal("12")


class GoalProjection:
    """Project explicit user scenarios without selecting or predicting a return."""

    def project(self, request: GoalProjectionRequest) -> GoalProjectionResult:
        results = tuple(self._project_scenario(request, scenario) for scenario in request.scenarios)
        warnings = [
            "Scenarios are user-controlled illustrations, not forecasts or guarantees.",
            "Declared risk tolerance is context only and does not select returns or investments.",
        ]
        if request.cash_flow_summary_id is not None:
            warnings.append(
                "The authorized cash-flow summary is referenced for context only; it does not "
                "silently change the explicit contribution amount."
            )
        return GoalProjectionResult(
            projection_id=request.projection_id,
            currency=request.currency,
            horizon_months=request.horizon_months,
            contribution_frequency=request.contribution_frequency,
            contribution_timing=request.contribution_timing,
            risk_tolerance=request.risk_tolerance,
            cash_flow_summary_id=request.cash_flow_summary_id,
            scenarios=results,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _project_scenario(
        request: GoalProjectionRequest, scenario: GoalScenario
    ) -> GoalScenarioResult:
        with localcontext() as context:
            context.prec = 34
            monthly_return = (
                scenario.annual_return_rate - scenario.annual_fee_rate
            ) / _MONTHS_PER_YEAR
            monthly_inflation = scenario.annual_inflation_rate / _MONTHS_PER_YEAR
            balance = request.starting_amount
            inflation_index = Decimal("1")
            contribution_count = 0
            frequency_months = request.contribution_frequency.months

            for month_number in range(1, request.horizon_months + 1):
                if (
                    request.contribution_timing == ContributionTiming.BEGINNING
                    and (month_number - 1) % frequency_months == 0
                ):
                    balance += request.contribution_amount
                    contribution_count += 1
                balance *= Decimal("1") + monthly_return
                inflation_index *= Decimal("1") + monthly_inflation
                if (
                    request.contribution_timing == ContributionTiming.END
                    and month_number % frequency_months == 0
                ):
                    balance += request.contribution_amount
                    contribution_count += 1

            total_contributions = request.contribution_amount * contribution_count
            nominal = money(balance)
            inflation_adjusted = money(balance / inflation_index)
            modeled_growth = money(balance - request.starting_amount - total_contributions)
            shortfall_or_surplus = (
                None if request.goal_amount is None else money(balance - request.goal_amount)
            )
        return GoalScenarioResult(
            label=scenario.label,
            nominal_future_value=nominal,
            inflation_adjusted_value=inflation_adjusted,
            total_contributions=money(total_contributions),
            modeled_growth=modeled_growth,
            nominal_shortfall_or_surplus=shortfall_or_surplus,
            contribution_count=contribution_count,
            annual_return_rate=scenario.annual_return_rate,
            annual_inflation_rate=scenario.annual_inflation_rate,
            annual_fee_rate=scenario.annual_fee_rate,
        )
