"""Cost-basis unrealized performance under finance-calculation-v2."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ai_finance_assistant.contracts.market import CacheStatus, DelayStatus, ProviderProvenance
from ai_finance_assistant.finance.models import (
    HoldingQuote,
    ImportedPortfolio,
    JsonImportPayload,
    PortfolioAnalysisRequest,
    PortfolioImportMetadata,
    PortfolioImportRequest,
    PortfolioSnapshot,
    QuoteSet,
)
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport

DATA_DIR = Path(__file__).parents[1] / "data" / "calculations"
ARTIFACT_DIR = Path(__file__).parents[1] / "artifacts" / "calculations"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def _portfolio(path: Path = DATA_DIR / "portfolio-performance.v1.json") -> ImportedPortfolio:
    result = PortfolioImport().import_portfolio(
        PortfolioImportRequest(
            metadata=PortfolioImportMetadata(
                portfolio_id="portfolio-performance",
                base_currency="USD",
                imported_at=NOW,
            ),
            payload=JsonImportPayload(content=path.read_bytes()),
        )
    )
    assert result.portfolio is not None, result.findings
    return result.portfolio


def _with_holding(
    portfolio: ImportedPortfolio, holding_id: str, **update: object
) -> ImportedPortfolio:
    return portfolio.model_copy(
        update={
            "accounts": tuple(
                account.model_copy(
                    update={
                        "holdings": tuple(
                            holding.model_copy(update=update)
                            if holding.holding_id == holding_id
                            else holding
                            for holding in account.holdings
                        )
                    }
                )
                for account in portfolio.accounts
            )
        }
    )


def _analyze(
    portfolio: ImportedPortfolio, quotes: tuple[HoldingQuote, ...] = ()
) -> PortfolioSnapshot:
    return PortfolioAnalysis().analyze(
        PortfolioAnalysisRequest(
            snapshot_id="snapshot-performance",
            calculated_at=NOW,
            portfolio=portfolio,
            quote_set=QuoteSet(quote_set_id="quotes-performance", quotes=quotes),
        )
    )


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def test_hand_worked_performance_golden() -> None:
    golden = json.loads(
        (ARTIFACT_DIR / "portfolio-performance-goldens.v1.json").read_text(encoding="utf-8")
    )
    expected = golden["expected"]

    snapshot = _analyze(_portfolio())

    assert snapshot.calculation_policy_version == golden["calculation_policy_version"]
    holdings = {item.holding_id: item for item in snapshot.holding_valuations}
    for holding_id, values in expected["holdings"].items():
        valuation = holdings[holding_id]
        assert valuation.cost_basis_total == _decimal(values["cost_basis_total"])
        assert valuation.unrealized_gain == _decimal(values["unrealized_gain"])
        assert valuation.unrealized_return_percent == _decimal(values["unrealized_return_percent"])
        assert valuation.holding_period_days == values["holding_period_days"]
        assert valuation.annualized_return_percent == _decimal(values["annualized_return_percent"])
    (summary,) = snapshot.performance
    assert summary.version == golden["performance_policy_version"]
    for field, value in expected["summary"].items():
        actual = getattr(summary, field)
        assert (str(actual) if isinstance(actual, Decimal) else actual) == value
    assert "not a time-weighted" in summary.limitation
    assert snapshot.diversification[0].top_five_holding_percent == Decimal(
        expected["top_five_holding_percent"]
    )


def test_top_five_concentration_counts_only_the_five_largest_values(tmp_path: Path) -> None:
    rows = [
        {
            "account_id": "acct",
            "account_type": "taxable",
            "holding_id": f"holding-{index}",
            "identifier_type": "ticker",
            "identifier_value": f"T{index}",
            "quantity": "1",
            "currency": "USD",
            "user_price": str(index * 10),
        }
        for index in range(1, 7)
    ]
    path = tmp_path / "six-holdings.json"
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    snapshot = _analyze(_portfolio(path))

    heuristic = snapshot.diversification[0]
    assert heuristic.top_five_holding_percent == Decimal("95.2381")  # (20+...+60) / 210
    (summary,) = snapshot.performance
    assert summary.holdings_with_cost_basis == 0
    assert summary.unrealized_return_percent is None
    assert summary.cost_basis_value_coverage_percent == Decimal("0.0000")


def test_annualization_starts_at_exactly_one_year() -> None:
    portfolio = _with_holding(_portfolio(), "holding-loss", acquisition_date=date(2025, 10, 27))

    valuation = next(
        item for item in _analyze(portfolio).holding_valuations if item.holding_id == "holding-loss"
    )

    assert valuation.holding_period_days == 365
    assert valuation.annualized_return_percent == valuation.unrealized_return_percent


def test_future_acquisition_date_is_warned_and_not_annualized() -> None:
    portfolio = _with_holding(_portfolio(), "holding-gain", acquisition_date=date(2026, 11, 1))

    snapshot = _analyze(portfolio)

    valuation = next(
        item for item in snapshot.holding_valuations if item.holding_id == "holding-gain"
    )
    assert valuation.holding_period_days is None
    assert valuation.annualized_return_percent is None
    assert valuation.unrealized_gain == Decimal("500.00")
    assert any(
        warning.code == "ACQUISITION_DATE_AFTER_VALUATION" and warning.holding_id == "holding-gain"
        for warning in snapshot.warnings
    )


def test_zero_cost_basis_reports_gain_without_a_percentage() -> None:
    portfolio = _with_holding(_portfolio(), "holding-gain", cost_basis_amount=Decimal("0"))

    snapshot = _analyze(portfolio)

    valuation = next(
        item for item in snapshot.holding_valuations if item.holding_id == "holding-gain"
    )
    assert valuation.unrealized_gain == Decimal("1500.00")
    assert valuation.unrealized_return_percent is None
    assert valuation.annualized_return_percent is None
    assert any(warning.code == "ZERO_COST_BASIS" for warning in snapshot.warnings)
    (summary,) = snapshot.performance
    assert summary.cost_basis_total == Decimal("600.00")
    assert summary.unrealized_gain == Decimal("1400.00")


def test_total_loss_annualizes_to_minus_one_hundred_percent() -> None:
    portfolio = _with_holding(_portfolio(), "holding-gain", quantity=Decimal("0"))

    valuation = next(
        item for item in _analyze(portfolio).holding_valuations if item.holding_id == "holding-gain"
    )

    assert valuation.market_value == Decimal("0.00")
    assert valuation.unrealized_return_percent == Decimal("-100.0000")
    assert valuation.annualized_return_percent == Decimal("-100.0000")


def test_quote_set_price_drives_gain_and_currency_mismatch_removes_it() -> None:
    provenance = ProviderProvenance(
        provider="fixture",
        data_as_of=NOW,
        retrieved_at=NOW,
        delay_status=DelayStatus.END_OF_DAY,
        cache_status=CacheStatus.MISS,
    )
    quoted = _analyze(
        _portfolio(),
        (
            HoldingQuote(
                holding_id="holding-gain",
                price=Decimal("80"),
                currency="USD",
                provenance=provenance,
            ),
        ),
    )
    mismatched = _analyze(
        _portfolio(),
        (
            HoldingQuote(
                holding_id="holding-gain",
                price=Decimal("80"),
                currency="EUR",
                provenance=provenance,
            ),
        ),
    )

    gain = next(item for item in quoted.holding_valuations if item.holding_id == "holding-gain")
    assert gain.unrealized_gain == Decimal("-200.00")
    assert gain.unrealized_return_percent == Decimal("-20.0000")
    missing = next(
        item for item in mismatched.holding_valuations if item.holding_id == "holding-gain"
    )
    assert missing.unrealized_gain is None
    assert missing.cost_basis_total == Decimal("1000.00")


def test_performance_stays_partitioned_by_currency() -> None:
    portfolio = _with_holding(_portfolio(), "holding-loss", currency="EUR")

    snapshot = _analyze(portfolio)

    by_currency = {item.currency: item for item in snapshot.performance}
    assert set(by_currency) == {"EUR", "USD"}
    assert by_currency["EUR"].unrealized_gain == Decimal("-100.00")
    assert by_currency["USD"].unrealized_gain == Decimal("500.00")
    assert snapshot.base_currency_total is None


@pytest.mark.parametrize("version", ["finance-calculation-v1"])
def test_snapshots_persisted_under_v1_still_load(version: str) -> None:
    current = _analyze(_portfolio()).model_dump(mode="json")
    legacy = {
        **current,
        "calculation_policy_version": version,
        "holding_valuations": [
            {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "cost_basis_total",
                    "unrealized_gain",
                    "unrealized_return_percent",
                    "acquisition_date",
                    "holding_period_days",
                    "annualized_return_percent",
                }
            }
            for item in current["holding_valuations"]
        ],
        "diversification": [
            {key: value for key, value in item.items() if key != "top_five_holding_percent"}
            for item in current["diversification"]
        ],
    }
    legacy.pop("performance")

    restored = PortfolioSnapshot.model_validate(legacy)

    assert restored.calculation_policy_version == version
    assert restored.performance == ()
    assert restored.holding_valuations[0].unrealized_gain is None
