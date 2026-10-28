"""Versioned Decimal precision and rounding policy for deterministic finance modules."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

CALCULATION_POLICY_VERSION = "finance-calculation-v1"
GOAL_POLICY_VERSION = "goal-projection-v1"
DIVERSIFICATION_POLICY_VERSION = "diversification-hhi-v1"

MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.0001")
RATIO_QUANTUM = Decimal("0.00000001")
COUNT_QUANTUM = Decimal("0.0001")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_EVEN)


def percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0").quantize(PERCENT_QUANTUM)
    with localcontext() as context:
        context.prec = 34
        return ((numerator / denominator) * HUNDRED).quantize(
            PERCENT_QUANTUM, rounding=ROUND_HALF_EVEN
        )


def count_value(value: Decimal) -> Decimal:
    return value.quantize(COUNT_QUANTUM, rounding=ROUND_HALF_EVEN)
