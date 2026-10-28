import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook

from ai_finance_assistant.finance.models import (
    CsvImportPayload,
    JsonImportPayload,
    ManualImportPayload,
    PortfolioImportMetadata,
    PortfolioImportRequest,
    PortfolioImportResult,
    XlsxImportPayload,
)
from ai_finance_assistant.finance.portfolio_import import (
    MAX_COLUMNS,
    MAX_FILE_BYTES,
    MAX_ROWS,
    PortfolioImport,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "finance"
IMPORTED_AT = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def metadata() -> PortfolioImportMetadata:
    return PortfolioImportMetadata(
        portfolio_id="portfolio-golden",
        label="Golden portfolio",
        base_currency="USD",
        imported_at=IMPORTED_AT,
    )


def valid_rows() -> list[dict[str, object]]:
    raw = json.loads((DATA_DIR / "portfolio_rows.valid.v1.json").read_text(encoding="utf-8"))
    return list(raw["rows"])


def make_xlsx(rows: list[dict[str, object]]) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Portfolio")
    headers = list(rows[0])
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def import_request(payload: object) -> PortfolioImportRequest:
    return PortfolioImportRequest(metadata=metadata(), payload=payload)


def normalized_positions(result: PortfolioImportResult) -> set[tuple[str, str, str, str]]:
    assert result.portfolio is not None
    return {
        (
            account.account_id,
            holding.holding_id,
            holding.security.value,
            str(holding.quantity),
        )
        for account in result.portfolio.accounts
        for holding in account.holdings
    }


def test_all_four_import_modes_share_one_validated_domain_result() -> None:
    rows = valid_rows()
    json_content = (DATA_DIR / "portfolio_rows.valid.v1.json").read_bytes()
    csv_content = (DATA_DIR / "portfolio_rows.valid.v1.csv").read_bytes()
    payloads = (
        ManualImportPayload(rows=tuple(rows)),
        JsonImportPayload(content=json_content),
        CsvImportPayload(content=csv_content),
        XlsxImportPayload(content=make_xlsx(rows)),
    )

    results = tuple(
        PortfolioImport().import_portfolio(import_request(payload)) for payload in payloads
    )

    assert all(result.accepted for result in results)
    expected = normalized_positions(results[0])
    assert all(normalized_positions(result) == expected for result in results[1:])
    assert {len(result.portfolio.accounts) for result in results if result.portfolio} == {2}
    assert all(
        any(finding.code == "MISSING_PRICE" for finding in result.findings) for result in results
    )


def test_import_aggregates_adversarial_findings_and_performs_no_merge() -> None:
    payload = JsonImportPayload(
        content=(DATA_DIR / "portfolio_rows.adversarial.v1.json").read_bytes()
    )

    result = PortfolioImport().import_portfolio(import_request(payload))

    assert not result.accepted
    assert result.portfolio is None
    codes = {finding.code for finding in result.findings}
    assert {"DUPLICATE_ROW", "DUPLICATE_HOLDING_ID", "UNSAFE_FORMULA"} <= codes
    assert "SHORT_POSITION_UNSUPPORTED" in codes
    assert all("HYPERLINK" not in finding.message for finding in result.findings)


def test_likely_duplicate_position_requires_explicit_merge_decision() -> None:
    rows = valid_rows()[:1]
    duplicate_position = {**rows[0], "holding_id": "holding-second-lot", "quantity": "2"}
    payload = ManualImportPayload(rows=(rows[0], duplicate_position))

    result = PortfolioImport().import_portfolio(import_request(payload))

    assert not result.accepted
    assert result.portfolio is None
    assert any(finding.code == "LIKELY_DUPLICATE_HOLDING" for finding in result.findings)


def test_manual_float_nonfinite_and_missing_fields_are_reported_together() -> None:
    payload = ManualImportPayload(
        rows=(
            {
                "account_id": "acct-1",
                "account_type": "taxable",
                "holding_id": "holding-1",
                "identifier_type": "ticker",
                "identifier_value": "AAA",
                "quantity": 1.25,
                "currency": "USD",
            },
            {
                "account_id": "acct-2",
                "account_type": "roth_ira",
                "holding_id": "holding-2",
                "identifier_type": "ticker",
                "identifier_value": "BBB",
                "quantity": "NaN",
                "currency": "",
            },
        )
    )

    result = PortfolioImport().import_portfolio(import_request(payload))

    codes = {finding.code for finding in result.findings}
    assert {"INEXACT_NUMERIC_TYPE", "NONFINITE_NUMBER", "MISSING_REQUIRED_FIELD"} <= codes
    assert not result.accepted


def test_csv_rejects_formula_like_content_without_exposing_it() -> None:
    content = (
        b"account_id,account_type,holding_id,identifier_type,identifier_value,quantity,currency\n"
        b"acct-1,taxable,holding-1,ticker,=2+2,10,USD\n"
    )

    result = PortfolioImport().import_portfolio(import_request(CsvImportPayload(content=content)))

    assert not result.accepted
    assert any(finding.code == "UNSAFE_FORMULA" for finding in result.findings)
    assert "=2+2" not in result.model_dump_json()


def test_xlsx_rejects_formulas_and_macro_like_archive_members() -> None:
    formula_rows = valid_rows()[:1]
    formula_rows[0] = {**formula_rows[0], "identifier_value": "=2+2"}
    formula_result = PortfolioImport().import_portfolio(
        import_request(XlsxImportPayload(content=make_xlsx(formula_rows)))
    )
    assert not formula_result.accepted
    assert any(finding.code == "UNSAFE_FORMULA" for finding in formula_result.findings)

    workbook_bytes = make_xlsx(valid_rows())
    modified = io.BytesIO(workbook_bytes)
    with zipfile.ZipFile(modified, mode="a") as archive:
        archive.writestr("xl/vbaProject.bin", b"not executable in this test")
    macro_result = PortfolioImport().import_portfolio(
        import_request(XlsxImportPayload(content=modified.getvalue()))
    )
    assert not macro_result.accepted
    assert [finding.code for finding in macro_result.findings] == ["UNSAFE_XLSX_CONTAINER"]


def test_file_and_row_limits_are_enforced_before_domain_construction() -> None:
    oversized = b" " * (MAX_FILE_BYTES + 1)
    oversized_result = PortfolioImport().import_portfolio(
        import_request(JsonImportPayload(content=oversized))
    )
    assert [finding.code for finding in oversized_result.findings] == ["FILE_SIZE_LIMIT"]

    row = valid_rows()[0]
    row_limit_result = PortfolioImport().import_portfolio(
        import_request(ManualImportPayload(rows=tuple(row for _ in range(MAX_ROWS + 1))))
    )
    assert [finding.code for finding in row_limit_result.findings] == ["ROW_LIMIT"]


def test_column_limit_is_enforced_for_all_four_import_modes() -> None:
    oversized_row: dict[str, object] = {
        f"field_{index}": "value" for index in range(MAX_COLUMNS + 1)
    }
    headers = ",".join(oversized_row)
    values = ",".join(str(value) for value in oversized_row.values())
    payloads = (
        ManualImportPayload(rows=(oversized_row,)),
        JsonImportPayload(content=json.dumps([oversized_row]).encode()),
        CsvImportPayload(content=f"{headers}\n{values}\n".encode()),
        XlsxImportPayload(content=make_xlsx([oversized_row])),
    )

    results = tuple(
        PortfolioImport().import_portfolio(import_request(payload)) for payload in payloads
    )

    assert all(not result.accepted for result in results)
    assert all(
        any(finding.code in {"COLUMN_LIMIT", "XLSX_DIMENSION_LIMIT"} for finding in result.findings)
        for result in results
    )


def test_import_serialization_retains_hash_and_records_but_not_uploaded_bytes() -> None:
    content = json.dumps({"rows": valid_rows()}, indent=7).encode()

    result = PortfolioImport().import_portfolio(import_request(JsonImportPayload(content=content)))
    restored = PortfolioImportResult.model_validate_json(result.model_dump_json())

    assert restored == result
    assert restored.source_file_hash
    assert "content" not in restored.model_dump_json()
    assert result.portfolio is not None
    assert result.portfolio.source_file_hash == result.source_file_hash


def test_versioned_sample_manifest_hashes_match_the_evidence_files() -> None:
    manifest = json.loads((DATA_DIR / "sample_manifest.v1.json").read_text(encoding="utf-8"))

    for dataset in manifest["datasets"]:
        actual = hashlib.sha256((DATA_DIR / dataset["path"]).read_bytes()).hexdigest()
        assert actual == dataset["sha256"]
    golden_path = (DATA_DIR / manifest["golden_artifact"]).resolve()
    assert (
        hashlib.sha256(golden_path.read_bytes()).hexdigest() == manifest["golden_artifact_sha256"]
    )
