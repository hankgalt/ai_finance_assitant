"""Conceptual planned cash-flow contracts; no M2 analysis implementation exists."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier
from ai_finance_assistant.finance.models import FiniteDecimal, NonNegativeDecimal


class CashFlowSourceType(StrEnum):
    BANK = "bank"
    CREDIT_CARD = "credit_card"


class TransactionDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class CashFlowTransactionRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_row_id: Identifier
    transaction_date: date
    posted_date: date | None = None
    description: str = Field(min_length=1, max_length=512)
    amount: NonNegativeDecimal
    direction: TransactionDirection
    merchant: str | None = Field(default=None, max_length=256)
    source_category: str | None = Field(default=None, max_length=128)


class CategoryOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_row_id: Identifier
    category: str = Field(min_length=1, max_length=128)


class ReconciliationHint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_row_id: Identifier
    possible_match_source_row_id: Identifier


class CashFlowAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    import_id: Identifier
    account_id: Identifier
    source_type: CashFlowSourceType
    source_schema_version: str = Field(min_length=1, max_length=32)
    currency: CurrencyCode
    rows: tuple[CashFlowTransactionRow, ...]
    category_overrides: tuple[CategoryOverride, ...] = ()
    reconciliation_hints: tuple[ReconciliationHint, ...] = ()


class MonthlyCashFlow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    income: NonNegativeDecimal
    spending: NonNegativeDecimal
    surplus: FiniteDecimal


class CashFlowSummary(BaseModel):
    """Minimized summary safe for separately authorized Goal Planning consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    summary_id: Identifier
    import_ids: tuple[Identifier, ...]
    currency: CurrencyCode
    period_start: date
    period_end: date
    monthly: tuple[MonthlyCashFlow, ...]
    average_monthly_income: NonNegativeDecimal
    average_monthly_spending: NonNegativeDecimal
    average_monthly_surplus: FiniteDecimal
    categorized_coverage_ratio: Decimal = Field(
        ge=0, le=1, allow_inf_nan=False, max_digits=18, decimal_places=12
    )
    unresolved_duplicate_count: int = Field(ge=0)
    unresolved_transfer_count: int = Field(ge=0)
    warnings: tuple[str, ...] = ()


class NormalizedCashFlowTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: Identifier
    source_row_id: Identifier
    transaction_date: date
    amount: NonNegativeDecimal
    direction: TransactionDirection
    category: str = Field(min_length=1, max_length=128)
    category_rule_version: str = Field(min_length=1, max_length=64)
    category_confidence: Decimal = Field(
        ge=0, le=1, allow_inf_nan=False, max_digits=18, decimal_places=12
    )
    category_overridden: bool
    reconciled_match_id: Identifier | None = None


class CategoryMonthlyCashFlow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    category: str = Field(min_length=1, max_length=128)
    income: NonNegativeDecimal
    spending: NonNegativeDecimal


class RecurringExpenseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: Identifier
    normalized_description: str = Field(min_length=1, max_length=256)
    transaction_ids: tuple[Identifier, ...]
    approximate_period_days: int = Field(ge=1, le=366)
    average_amount: NonNegativeDecimal
    confidence: Decimal = Field(ge=0, le=1, allow_inf_nan=False, max_digits=18, decimal_places=12)
    detection_version: str = Field(min_length=1, max_length=64)


class ReconciliationKind(StrEnum):
    TRANSFER = "transfer"
    CREDIT_CARD_PAYMENT = "credit_card_payment"


class ReconciledCashFlowPair(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reconciliation_id: Identifier
    first_transaction_id: Identifier
    second_transaction_id: Identifier
    kind: ReconciliationKind
    reconciliation_version: str = Field(min_length=1, max_length=64)


class CashFlowAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    import_id: Identifier
    normalized_transactions: tuple[NormalizedCashFlowTransaction, ...]
    category_monthly: tuple[CategoryMonthlyCashFlow, ...]
    recurring_expenses: tuple[RecurringExpenseCandidate, ...]
    reconciled_pairs: tuple[ReconciledCashFlowPair, ...]
    summary: CashFlowSummary
    warnings: tuple[str, ...]


class CashFlowAnalysisService(Protocol):
    """Planned seam; an implementation belongs to a separately approved milestone."""

    def analyze(self, request: CashFlowAnalysisRequest) -> CashFlowAnalysisResult: ...
