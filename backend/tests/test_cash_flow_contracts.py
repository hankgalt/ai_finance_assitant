from datetime import date
from decimal import Decimal

from ai_finance_assistant.finance.cash_flow import (
    CashFlowAnalysisRequest,
    CashFlowAnalysisResult,
    CashFlowSummary,
    CashFlowTransactionRow,
    CategoryMonthlyCashFlow,
    MonthlyCashFlow,
    NormalizedCashFlowTransaction,
    ReconciledCashFlowPair,
    RecurringExpenseCandidate,
)


def test_cash_flow_interface_preserves_raw_rows_outside_minimized_summary() -> None:
    request = CashFlowAnalysisRequest(
        import_id="cash-import-1",
        account_id="checking-1",
        source_type="bank",
        source_schema_version="bank-csv-v1",
        currency="USD",
        rows=(
            CashFlowTransactionRow(
                source_row_id="row-1",
                transaction_date=date(2026, 1, 2),
                description="Sensitive merchant description",
                amount="100",
                direction="outflow",
            ),
        ),
    )
    summary = CashFlowSummary(
        summary_id="cash-summary-1",
        import_ids=(request.import_id,),
        currency="USD",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        monthly=(
            MonthlyCashFlow(
                month="2026-01",
                income="0",
                spending="100",
                surplus="-100",
            ),
        ),
        average_monthly_income="0",
        average_monthly_spending="100",
        average_monthly_surplus="-100",
        categorized_coverage_ratio="1",
        unresolved_duplicate_count=0,
        unresolved_transfer_count=0,
    )
    result = CashFlowAnalysisResult(
        import_id=request.import_id,
        normalized_transactions=(
            NormalizedCashFlowTransaction(
                transaction_id="transaction-1",
                source_row_id="row-1",
                transaction_date=date(2026, 1, 2),
                amount="100",
                direction="outflow",
                category="housing",
                category_rule_version="cash-category-v1",
                category_confidence="1",
                category_overridden=False,
            ),
        ),
        category_monthly=(
            CategoryMonthlyCashFlow(
                month="2026-01",
                category="housing",
                income="0",
                spending="100",
            ),
        ),
        recurring_expenses=(
            RecurringExpenseCandidate(
                candidate_id="recurring-1",
                normalized_description="rent",
                transaction_ids=("transaction-1",),
                approximate_period_days=30,
                average_amount="100",
                confidence="0.5",
                detection_version="recurrence-v1",
            ),
        ),
        reconciled_pairs=(
            ReconciledCashFlowPair(
                reconciliation_id="reconciliation-1",
                first_transaction_id="transaction-1",
                second_transaction_id="transaction-2",
                kind="transfer",
                reconciliation_version="reconciliation-v1",
            ),
        ),
        summary=summary,
        warnings=("Conceptual M2 fixture only.",),
    )

    restored = CashFlowAnalysisResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert "Sensitive merchant description" in request.model_dump_json()
    assert "Sensitive merchant description" not in result.summary.model_dump_json()
    assert result.summary.average_monthly_surplus == Decimal("-100")
