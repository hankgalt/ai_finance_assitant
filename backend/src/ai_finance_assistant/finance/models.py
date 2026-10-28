"""Versioned domain contracts for imports, enrichment, calculations, and goals."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier, ShortText
from ai_finance_assistant.contracts.market import ProviderProvenance
from ai_finance_assistant.contracts.portfolio import SecurityIdentifier

FiniteDecimal = Annotated[
    Decimal,
    Field(allow_inf_nan=False, max_digits=30, decimal_places=12),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False, max_digits=30, decimal_places=12),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=0, allow_inf_nan=False, max_digits=30, decimal_places=12),
]
RateDecimal = Annotated[
    Decimal,
    Field(ge=0, le=1, allow_inf_nan=False, max_digits=18, decimal_places=12),
]


class ImportSourceKind(StrEnum):
    MANUAL = "manual"
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"


class FindingSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class FindingScope(StrEnum):
    FILE = "file"
    ROW = "row"
    FIELD = "field"


class ImportFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=80)
    severity: FindingSeverity
    scope: FindingScope
    message: ShortText
    row_number: int | None = Field(default=None, ge=1)
    field: str | None = Field(default=None, max_length=64)


class RawFieldValue(BaseModel):
    """Safe diagnostic evidence; executable-looking values are replaced before storage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=512)


class PortfolioImportMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: Identifier
    label: str | None = Field(default=None, max_length=128)
    base_currency: CurrencyCode
    imported_at: AwareDatetime


class ManualImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[ImportSourceKind.MANUAL] = ImportSourceKind.MANUAL
    rows: tuple[dict[str, JsonValue], ...]


class JsonImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[ImportSourceKind.JSON] = ImportSourceKind.JSON
    content: bytes
    filename: str = Field(default="portfolio.json", min_length=1, max_length=255)


class CsvImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[ImportSourceKind.CSV] = ImportSourceKind.CSV
    content: bytes
    filename: str = Field(default="portfolio.csv", min_length=1, max_length=255)


class XlsxImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[ImportSourceKind.XLSX] = ImportSourceKind.XLSX
    content: bytes
    filename: str = Field(default="portfolio.xlsx", min_length=1, max_length=255)


ImportPayload = Annotated[
    ManualImportPayload | JsonImportPayload | CsvImportPayload | XlsxImportPayload,
    Field(discriminator="kind"),
]


class PortfolioImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    metadata: PortfolioImportMetadata
    payload: ImportPayload


class ImportedHolding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    holding_id: Identifier
    account_id: Identifier
    source_row: int = Field(ge=1)
    security: SecurityIdentifier
    quantity: NonNegativeDecimal
    currency: CurrencyCode
    asset_class: str | None = Field(default=None, max_length=128)
    cost_basis_amount: NonNegativeDecimal | None = None
    cost_basis_basis: Literal["total", "per_unit"] | None = None
    acquisition_date: date | None = None
    user_price: PositiveDecimal | None = None
    user_price_as_of: AwareDatetime | None = None
    user_price_provenance: str | None = Field(default=None, max_length=128)
    expense_ratio: RateDecimal | None = None
    sector: str | None = Field(default=None, max_length=128)
    raw_fields: tuple[RawFieldValue, ...] = ()

    @model_validator(mode="after")
    def validate_related_fields(self) -> "ImportedHolding":
        if (self.cost_basis_amount is None) != (self.cost_basis_basis is None):
            raise ValueError("cost basis amount and basis must be supplied together")
        if self.user_price is None and (
            self.user_price_as_of is not None or self.user_price_provenance is not None
        ):
            raise ValueError("price metadata requires a user price")
        return self


class ImportedAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_id: Identifier
    portfolio_id: Identifier
    account_type: str = Field(min_length=1, max_length=64)
    institution_label: str | None = Field(default=None, max_length=128)
    holdings: tuple[ImportedHolding, ...]

    @model_validator(mode="after")
    def validate_holdings(self) -> "ImportedAccount":
        if not self.holdings:
            raise ValueError("an imported account must contain at least one holding")
        if any(holding.account_id != self.account_id for holding in self.holdings):
            raise ValueError("holding account_id does not match its account")
        holding_ids = [holding.holding_id for holding in self.holdings]
        if len(holding_ids) != len(set(holding_ids)):
            raise ValueError("holding_id values must be unique within an account")
        return self


class ImportedPortfolio(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    portfolio_id: Identifier
    label: str | None = Field(default=None, max_length=128)
    base_currency: CurrencyCode
    imported_at: AwareDatetime
    source_kind: ImportSourceKind
    source_file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    accounts: tuple[ImportedAccount, ...]

    @model_validator(mode="after")
    def validate_accounts(self) -> "ImportedPortfolio":
        if not self.accounts:
            raise ValueError("an imported portfolio must contain at least one account")
        if any(account.portfolio_id != self.portfolio_id for account in self.accounts):
            raise ValueError("account portfolio_id does not match its portfolio")
        account_ids = [account.account_id for account in self.accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("account_id values must be unique within a portfolio")
        return self


class PortfolioImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    source_kind: ImportSourceKind
    source_file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted: bool
    portfolio: ImportedPortfolio | None
    findings: tuple[ImportFinding, ...]

    @model_validator(mode="after")
    def validate_acceptance(self) -> "PortfolioImportResult":
        has_blocking = any(
            finding.severity in {FindingSeverity.ERROR, FindingSeverity.FATAL}
            for finding in self.findings
        )
        if self.accepted == has_blocking:
            raise ValueError("accepted must be true exactly when no blocking findings exist")
        if self.accepted != (self.portfolio is not None):
            raise ValueError(
                "an accepted result must contain a portfolio and a rejected result must not"
            )
        return self


class SecurityFieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1, max_length=64)
    provider: ShortText
    retrieved_at: AwareDatetime


class EnrichmentConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1, max_length=64)
    imported_value: str = Field(max_length=128)
    provider_value: str = Field(max_length=128)


class SecurityReference(BaseModel):
    """Provider enrichment remains separate from imported Holding evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    reference_id: Identifier
    holding_id: Identifier
    canonical_identifiers: tuple[SecurityIdentifier, ...] = ()
    display_name: str | None = Field(default=None, max_length=256)
    asset_class: str | None = Field(default=None, max_length=128)
    sector: str | None = Field(default=None, max_length=128)
    trading_currency: CurrencyCode | None = None
    expense_ratio: RateDecimal | None = None
    field_provenance: tuple[SecurityFieldProvenance, ...] = ()
    retrieved_at: AwareDatetime
    conflicts: tuple[EnrichmentConflict, ...] = ()


class HoldingQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    holding_id: Identifier
    price: PositiveDecimal
    currency: CurrencyCode
    provenance: ProviderProvenance


class QuoteSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quote_set_id: Identifier
    quotes: tuple[HoldingQuote, ...] = ()

    @model_validator(mode="after")
    def validate_quotes(self) -> "QuoteSet":
        holding_ids = [quote.holding_id for quote in self.quotes]
        if len(holding_ids) != len(set(holding_ids)):
            raise ValueError("a quote set may contain only one quote per holding")
        return self


class CalculationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=80)
    message: ShortText
    holding_id: Identifier | None = None


class HoldingValuation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    holding_id: Identifier
    account_id: Identifier
    currency: CurrencyCode
    quantity: NonNegativeDecimal
    price: PositiveDecimal | None = None
    price_source: Literal["quote_set", "user_import"] | None = None
    market_value: NonNegativeDecimal | None = None
    allocation_percent: NonNegativeDecimal | None = None
    asset_class: str | None = None
    asset_class_source: Literal["provider", "user_import"] | None = None
    sector: str | None = None
    sector_source: Literal["provider", "user_import"] | None = None
    expense_ratio: RateDecimal | None = None
    expense_ratio_source: Literal["provider", "user_import"] | None = None


class CurrencyTotal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: CurrencyCode
    priced_value: NonNegativeDecimal
    priced_holding_count: int = Field(ge=0)
    total_holding_count: int = Field(ge=0)
    holding_count_coverage_percent: NonNegativeDecimal


class ClassificationConcentration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    classification: Literal["asset_class", "sector"]
    currency: CurrencyCode
    category: str = Field(min_length=1, max_length=128)
    market_value: NonNegativeDecimal
    percent_of_classified_value: NonNegativeDecimal
    classified_value_coverage_percent: NonNegativeDecimal


class ExpenseMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: CurrencyCode
    weighted_expense_ratio: RateDecimal | None = None
    covered_value: NonNegativeDecimal
    known_value_coverage_percent: NonNegativeDecimal


class DiversificationHeuristic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["diversification-hhi-v1"] = "diversification-hhi-v1"
    currency: CurrencyCode
    holding_hhi: RateDecimal | None = None
    effective_holding_count: NonNegativeDecimal | None = None
    top_holding_percent: NonNegativeDecimal | None = None
    priced_holding_count: int = Field(ge=0)
    limitation: str = Field(min_length=1, max_length=512)


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    snapshot_id: Identifier
    portfolio_id: Identifier
    calculated_at: AwareDatetime
    calculation_policy_version: Literal["finance-calculation-v1"] = "finance-calculation-v1"
    quote_set_id: Identifier
    security_reference_ids: tuple[Identifier, ...]
    base_currency: CurrencyCode
    base_currency_total: NonNegativeDecimal | None = None
    totals_by_currency: tuple[CurrencyTotal, ...]
    holding_valuations: tuple[HoldingValuation, ...]
    concentrations: tuple[ClassificationConcentration, ...]
    expense_metrics: tuple[ExpenseMetric, ...]
    diversification: tuple[DiversificationHeuristic, ...]
    unpriced_holding_ids: tuple[Identifier, ...]
    warnings: tuple[CalculationWarning, ...]


class PortfolioAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: Identifier
    calculated_at: AwareDatetime
    portfolio: ImportedPortfolio
    security_references: tuple[SecurityReference, ...] = ()
    quote_set: QuoteSet


class ContributionFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"

    @property
    def months(self) -> int:
        return {self.MONTHLY: 1, self.QUARTERLY: 3, self.ANNUAL: 12}[self]


class ContributionTiming(StrEnum):
    BEGINNING = "beginning"
    END = "end"


class RiskTolerance(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    NOT_DECLARED = "not_declared"


class GoalScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=64)
    annual_return_rate: FiniteDecimal = Field(ge=Decimal("-0.999999"), le=10)
    annual_inflation_rate: FiniteDecimal = Field(ge=Decimal("-0.999999"), le=10)
    annual_fee_rate: RateDecimal = Decimal("0")

    @model_validator(mode="after")
    def validate_net_return(self) -> "GoalScenario":
        if self.annual_return_rate - self.annual_fee_rate <= Decimal("-1"):
            raise ValueError("return after modeled fees must be greater than -100%")
        return self


class GoalProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    projection_id: Identifier
    currency: CurrencyCode
    starting_amount: NonNegativeDecimal
    goal_amount: NonNegativeDecimal | None = None
    contribution_amount: NonNegativeDecimal
    contribution_frequency: ContributionFrequency
    contribution_timing: ContributionTiming
    horizon_months: int = Field(ge=1, le=1_200)
    risk_tolerance: RiskTolerance = RiskTolerance.NOT_DECLARED
    cash_flow_summary_id: Identifier | None = None
    scenarios: tuple[GoalScenario, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_scenarios(self) -> "GoalProjectionRequest":
        labels = [scenario.label.casefold() for scenario in self.scenarios]
        if len(labels) != len(set(labels)):
            raise ValueError("scenario labels must be unique")
        return self


class GoalScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    nominal_future_value: FiniteDecimal
    inflation_adjusted_value: FiniteDecimal
    total_contributions: NonNegativeDecimal
    modeled_growth: FiniteDecimal
    nominal_shortfall_or_surplus: FiniteDecimal | None = None
    contribution_count: int = Field(ge=0)
    annual_return_rate: FiniteDecimal
    annual_inflation_rate: FiniteDecimal
    annual_fee_rate: RateDecimal


class GoalProjectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", pattern=r"^1$")
    projection_id: Identifier
    calculation_policy_version: Literal["goal-projection-v1"] = "goal-projection-v1"
    currency: CurrencyCode
    horizon_months: int
    contribution_frequency: ContributionFrequency
    contribution_timing: ContributionTiming
    risk_tolerance: RiskTolerance
    cash_flow_summary_id: Identifier | None = None
    scenarios: tuple[GoalScenarioResult, ...]
    warnings: tuple[str, ...]
