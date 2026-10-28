import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus, ProviderProvenance
from ai_finance_assistant.finance.models import (
    HoldingQuote,
    ImportedPortfolio,
    JsonImportPayload,
    PortfolioAnalysisRequest,
    PortfolioImportMetadata,
    PortfolioImportRequest,
    QuoteSet,
    SecurityReference,
)
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport

DATA_DIR = Path(__file__).parents[1] / "data" / "finance"
ARTIFACT_DIR = Path(__file__).parents[1] / "artifacts" / "m2"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def imported_portfolio() -> ImportedPortfolio:
    result = PortfolioImport().import_portfolio(
        PortfolioImportRequest(
            metadata=PortfolioImportMetadata(
                portfolio_id="portfolio-golden",
                label="Golden portfolio",
                base_currency="USD",
                imported_at=NOW,
            ),
            payload=JsonImportPayload(
                content=(DATA_DIR / "portfolio_rows.valid.v1.json").read_bytes()
            ),
        )
    )
    assert result.portfolio is not None
    return result.portfolio


def request_for(
    portfolio: ImportedPortfolio | None = None,
    *,
    references: tuple[SecurityReference, ...] = (),
    quotes: tuple[HoldingQuote, ...] = (),
) -> PortfolioAnalysisRequest:
    return PortfolioAnalysisRequest(
        snapshot_id="snapshot-1",
        calculated_at=NOW,
        portfolio=portfolio or imported_portfolio(),
        security_references=references,
        quote_set=QuoteSet(quote_set_id="quotes-1", quotes=quotes),
    )


def test_hand_worked_portfolio_golden_reports_partial_coverage() -> None:
    expected = json.loads(
        (ARTIFACT_DIR / "calculation-goldens.v1.json").read_text(encoding="utf-8")
    )["expected"]
    snapshot = PortfolioAnalysis().analyze(request_for())

    assert snapshot.base_currency_total == Decimal(expected["base_currency_total"])
    assert snapshot.unpriced_holding_ids == tuple(expected["unpriced_holding_ids"])
    assert snapshot.totals_by_currency[0].holding_count_coverage_percent == Decimal(
        expected["holding_count_coverage_percent"]
    )
    values = {item.holding_id: item for item in snapshot.holding_valuations}
    assert values["holding-stock"].market_value == Decimal(expected["stock_value"])
    assert values["holding-stock"].allocation_percent == Decimal(
        expected["stock_allocation_percent"]
    )
    assert values["holding-bond"].market_value == Decimal(expected["bond_value"])
    assert values["holding-bond"].allocation_percent == Decimal(expected["bond_allocation_percent"])
    assert values["holding-unpriced"].market_value is None

    expense = snapshot.expense_metrics[0]
    assert expense.weighted_expense_ratio == Decimal(expected["weighted_expense_ratio"])
    assert expense.known_value_coverage_percent == Decimal(expected["expense_coverage_percent"])
    heuristic = snapshot.diversification[0]
    assert heuristic.holding_hhi == Decimal(expected["holding_hhi"])
    assert heuristic.effective_holding_count == Decimal(expected["effective_holding_count"])
    assert heuristic.top_holding_percent == Decimal("66.6667")
    assert "do not measure" in heuristic.limitation


def test_allocation_and_classification_concentrations_use_only_covered_value() -> None:
    snapshot = PortfolioAnalysis().analyze(request_for())

    priced_allocations = [
        item.allocation_percent
        for item in snapshot.holding_valuations
        if item.allocation_percent is not None
    ]
    assert sum(priced_allocations, Decimal("0")) == Decimal("100.0000")
    asset = {
        item.category: item
        for item in snapshot.concentrations
        if item.classification == "asset_class"
    }
    assert asset["Equity"].percent_of_classified_value == Decimal("66.6667")
    assert asset["Fixed Income"].percent_of_classified_value == Decimal("33.3333")
    assert all(
        item.classified_value_coverage_percent == Decimal("100.0000") for item in asset.values()
    )


def test_missing_classification_reduces_coverage_without_inventing_a_category() -> None:
    portfolio = imported_portfolio()
    updated_accounts = tuple(
        account.model_copy(
            update={
                "holdings": tuple(
                    holding.model_copy(update={"asset_class": None})
                    if holding.holding_id == "holding-bond"
                    else holding
                    for holding in account.holdings
                )
            }
        )
        for account in portfolio.accounts
    )

    snapshot = PortfolioAnalysis().analyze(
        request_for(portfolio.model_copy(update={"accounts": updated_accounts}))
    )

    asset = [item for item in snapshot.concentrations if item.classification == "asset_class"]
    assert {item.category for item in asset} == {"Equity"}
    assert all(item.classified_value_coverage_percent == Decimal("66.6667") for item in asset)


def test_adding_an_unpriced_holding_does_not_increase_valued_total_or_coverage() -> None:
    portfolio = imported_portfolio()
    priced_only_accounts = tuple(
        account
        for account in portfolio.accounts
        if any(holding.user_price is not None for holding in account.holdings)
    )
    priced_only = portfolio.model_copy(update={"accounts": priced_only_accounts})

    before = PortfolioAnalysis().analyze(request_for(priced_only))
    after = PortfolioAnalysis().analyze(request_for(portfolio))

    assert before.base_currency_total == after.base_currency_total == Decimal("1500.00")
    assert before.totals_by_currency[0].holding_count_coverage_percent == Decimal("100.0000")
    assert after.totals_by_currency[0].holding_count_coverage_percent == Decimal("66.6667")


def test_doubling_quantity_doubles_that_holding_value() -> None:
    portfolio = imported_portfolio()
    taxable = next(
        account for account in portfolio.accounts if account.account_id == "acct-taxable"
    )
    updated_holdings = tuple(
        holding.model_copy(update={"quantity": holding.quantity * 2})
        if holding.holding_id == "holding-stock"
        else holding
        for holding in taxable.holdings
    )
    updated_accounts = tuple(
        account.model_copy(update={"holdings": updated_holdings})
        if account.account_id == taxable.account_id
        else account
        for account in portfolio.accounts
    )
    doubled = portfolio.model_copy(update={"accounts": updated_accounts})

    original_snapshot = PortfolioAnalysis().analyze(request_for(portfolio))
    doubled_snapshot = PortfolioAnalysis().analyze(request_for(doubled))
    original = next(
        item for item in original_snapshot.holding_valuations if item.holding_id == "holding-stock"
    )
    changed = next(
        item for item in doubled_snapshot.holding_valuations if item.holding_id == "holding-stock"
    )

    assert original.market_value is not None
    assert changed.market_value == original.market_value * 2


def test_mixed_currency_is_partitioned_without_implicit_fx_conversion() -> None:
    portfolio = imported_portfolio()
    updated_accounts = tuple(
        account.model_copy(
            update={
                "holdings": tuple(
                    holding.model_copy(update={"currency": "EUR"})
                    if holding.holding_id == "holding-bond"
                    else holding
                    for holding in account.holdings
                )
            }
        )
        for account in portfolio.accounts
    )
    mixed = portfolio.model_copy(update={"accounts": updated_accounts})

    snapshot = PortfolioAnalysis().analyze(request_for(mixed))

    assert snapshot.base_currency_total is None
    assert {item.currency: item.priced_value for item in snapshot.totals_by_currency} == {
        "EUR": Decimal("500.00"),
        "USD": Decimal("1000.00"),
    }
    assert any(warning.code == "MIXED_CURRENCY_NO_FX" for warning in snapshot.warnings)


def test_provider_enrichment_is_separate_and_conflicts_are_visible() -> None:
    reference = SecurityReference(
        reference_id="reference-stock-v1",
        holding_id="holding-stock",
        asset_class="Provider Equity",
        sector="Technology",
        expense_ratio=Decimal("0.002"),
        retrieved_at=NOW,
    )
    quote = HoldingQuote(
        holding_id="holding-stock",
        price=Decimal("101"),
        currency="USD",
        provenance=ProviderProvenance(
            provider="fake-m2-provider",
            data_as_of=NOW,
            retrieved_at=NOW,
            delay_status=DelayStatus.DELAYED,
            cache_status=CacheStatus.STALE,
            is_stale=True,
        ),
    )

    snapshot = PortfolioAnalysis().analyze(request_for(references=(reference,), quotes=(quote,)))

    imported = imported_portfolio()
    original = next(
        holding
        for account in imported.accounts
        for holding in account.holdings
        if holding.holding_id == "holding-stock"
    )
    selected = next(
        value for value in snapshot.holding_valuations if value.holding_id == "holding-stock"
    )
    assert original.asset_class == "Equity"
    assert original.expense_ratio == Decimal("0.001")
    assert selected.asset_class == "Provider Equity"
    assert selected.expense_ratio == Decimal("0.002")
    assert snapshot.security_reference_ids == ("reference-stock-v1",)
    assert {warning.code for warning in snapshot.warnings} >= {
        "ENRICHMENT_CONFLICT",
        "STALE_QUOTE",
    }


def test_quote_currency_mismatch_reduces_valuation_coverage() -> None:
    quote = HoldingQuote(
        holding_id="holding-stock",
        price=Decimal("100"),
        currency="EUR",
        provenance=ProviderProvenance(
            provider="fake-m2-provider",
            data_as_of=NOW,
            retrieved_at=NOW,
        ),
    )

    snapshot = PortfolioAnalysis().analyze(request_for(quotes=(quote,)))

    assert "holding-stock" in snapshot.unpriced_holding_ids
    assert snapshot.base_currency_total == Decimal("500.00")
    assert any(warning.code == "QUOTE_CURRENCY_MISMATCH" for warning in snapshot.warnings)
