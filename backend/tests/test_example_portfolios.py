import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ai_finance_assistant.finance.models import (
    CsvImportPayload,
    JsonImportPayload,
    PortfolioAnalysisRequest,
    PortfolioImportMetadata,
    PortfolioImportRequest,
    QuoteSet,
    XlsxImportPayload,
)
from ai_finance_assistant.finance.portfolio_analysis import PortfolioAnalysis
from ai_finance_assistant.finance.portfolio_import import PortfolioImport

EXAMPLE_DIR = Path(__file__).parents[2] / "examples" / "portfolios"


def _payload(path: Path) -> JsonImportPayload | CsvImportPayload | XlsxImportPayload:
    content = path.read_bytes()
    if path.suffix == ".json":
        return JsonImportPayload(content=content, filename=path.name)
    if path.suffix == ".csv":
        return CsvImportPayload(content=content, filename=path.name)
    return XlsxImportPayload(content=content, filename=path.name)


@pytest.mark.parametrize(
    ("filename", "account_count", "holding_count"),
    (
        ("balanced_multi_account.json", 3, 7),
        ("concentrated_technology.csv", 1, 5),
        ("retirement_income.xlsx", 3, 7),
    ),
)
def test_example_portfolios_are_importable_and_dashboard_ready(
    filename: str,
    account_count: int,
    holding_count: int,
) -> None:
    result = PortfolioImport().import_portfolio(
        PortfolioImportRequest(
            metadata=PortfolioImportMetadata(
                portfolio_id=f"example-{Path(filename).stem}",
                label=Path(filename).stem.replace("_", " ").title(),
                base_currency="USD",
                imported_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
            ),
            payload=_payload(EXAMPLE_DIR / filename),
        )
    )

    assert result.accepted
    assert result.portfolio is not None
    assert not result.findings
    assert len(result.portfolio.accounts) == account_count
    holdings = tuple(
        holding for account in result.portfolio.accounts for holding in account.holdings
    )
    assert len(holdings) == holding_count
    assert all(holding.user_price is not None for holding in holdings)
    assert all(holding.user_price_provenance == "Synthetic example price" for holding in holdings)
    assert all(
        holding.asset_class is not None and holding.sector is not None for holding in holdings
    )

    snapshot = PortfolioAnalysis().analyze(
        PortfolioAnalysisRequest(
            snapshot_id=f"snapshot-{Path(filename).stem}",
            calculated_at=datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
            portfolio=result.portfolio,
            quote_set=QuoteSet(quote_set_id=f"quotes-{Path(filename).stem}"),
        )
    )
    assert snapshot.base_currency_total is not None
    assert snapshot.base_currency_total > 0
    assert not snapshot.unpriced_holding_ids
    assert snapshot.totals_by_currency[0].holding_count_coverage_percent == Decimal("100.0000")
    assert len(snapshot.holding_valuations) == holding_count
    allocation_total = sum(
        (
            valuation.allocation_percent
            for valuation in snapshot.holding_valuations
            if valuation.allocation_percent is not None
        ),
        Decimal("0"),
    )
    assert abs(allocation_total - Decimal("100.0000")) <= Decimal("0.0005")
    assert {warning.code for warning in snapshot.warnings} == {"USER_PRICE_USED"}


def test_example_portfolio_manifest_matches_files() -> None:
    manifest = json.loads((EXAMPLE_DIR / "manifest.v1.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "1"
    for dataset in manifest["datasets"]:
        content = (EXAMPLE_DIR / dataset["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == dataset["sha256"]
