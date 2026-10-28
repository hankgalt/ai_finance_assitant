# M2 deterministic finance calculation policy

Version 1.0 | Status: Implemented M2 policy | 2026-10-27

Scope: PR-003, PR-005, PR-009, PR-016; QR-001, QR-002, QR-006, QR-009, QR-010, QR-015; ADR-009, ADR-012, ADR-018, ADR-019, ADR-020, ADR-021

This document records the numerical and import decisions needed to reproduce M2. It does not replace the requirements or describe personalized investment advice.

## 1. Version identifiers

| Concern | Version |
| --- | --- |
| Portfolio import | `portfolio-import-v1` |
| Portfolio calculation | `finance-calculation-v1` |
| Diversification heuristic | `diversification-hhi-v1` |
| Goal projection | `goal-projection-v1` |

Changing a formula, rounding rule, accepted import interpretation, duplicate key, or heuristic requires a new version and new golden evidence.

## 2. Decimal and rounding policy

- Monetary, quantity, price, rate, percentage, and goal arithmetic uses Python `Decimal`; no LLM or binary floating-point value is an arithmetic authority.
- Import accepts decimal strings, `Decimal` values, or integers. Binary floats are rejected at the import seam because their original lexical precision cannot be recovered.
- Calculations use a local decimal precision of 34 significant digits where division or compounding occurs.
- Monetary outputs use a generic two-decimal quantum and round-half-even.
- Percentage outputs are percentages from 0 through 100 and use four decimal places.
- Ratio outputs, including expense ratios and HHI, use eight decimal places. Expense-ratio inputs are decimal fractions: `0.001` means 0.10%.
- Effective holding count uses four decimal places.
- The generic two-decimal money quantum is an initial-release limitation; currency-specific minor-unit rules require a later policy version.

## 3. Import and file safety

Manual, JSON, CSV, and XLSX inputs converge on one PortfolioImport interface and the same imported Portfolio, Account, and Holding contracts.

Initial limits are:

| Limit | Value |
| --- | ---: |
| Uploaded JSON/CSV/XLSX bytes | 2,000,000 |
| Rows | 10,000 |
| Columns | 32 |
| XLSX uncompressed bytes | 20,000,000 |
| XLSX archive members | 200 |
| General imported text | 512 characters |

JSON and CSV require UTF-8. XLSX runs in read-only mode after ZIP integrity, path, size, macro, external-link, and embedded-object checks. Formula cells and formula-like text are rejected and never echoed in a diagnostic. Uploaded bodies are parsed in memory and are not retained in the returned records; only the source-file SHA-256 is retained.

Required row fields are account ID/type, Holding ID, identifier type/value, quantity, and currency. Negative quantities are rejected because M2 has no approved short-position model. Zero quantities are preserved with a warning. Missing optional data stays missing.

Exact duplicate rows, duplicate Holding IDs, and the same normalized security identifier repeated within one Account are blocking findings. No merge is performed. Account metadata conflicts are also blocking. A caller must present a corrected dataset or a separately designed explicit merge decision.

## 4. Imported, enriched, and calculated data

Imported Portfolio records are immutable evidence. SecurityReference and HoldingQuote records are additive enrichment with provenance. PortfolioSnapshot is a time-specific calculated record and stores the quote-set identifier plus every SecurityReference identifier it used.

Provider classification or expense fields are selected for a snapshot when supplied, but conflicting imported values remain unchanged and generate warnings. A quote-set price is preferred. A user-supplied price is used only when no quote exists and is labeled as such. A quote whose currency differs from the imported Holding currency is not converted or used.

## 5. Portfolio calculations and coverage

Holding value is quantity multiplied by the selected price, rounded to the money quantum. Holdings without a usable price are excluded from value totals and listed explicitly.

- Total values and allocations are calculated independently per currency.
- `base_currency_total` is unavailable when the imported portfolio contains another currency and no approved FX set exists.
- Holding-count valuation coverage is priced Holding count divided by total Holding count for that currency.
- Expense ratio is value-weighted only across priced Holdings with a known expense ratio. Known-value coverage is reported against total priced value.
- Asset-class and sector concentration are calculated only over priced, classified value. Each result also reports classified-value coverage against priced value.

The pipeline never converts an unknown value to zero. An actual zero quantity can produce a zero market value; a missing price produces no market value.

## 6. Diversification heuristic

For each currency, `diversification-hhi-v1` calculates:

~~~text
holding_weight_i = priced_holding_value_i / priced_total
HHI = sum(holding_weight_i²)
effective_holding_count = 1 / HHI
~~~

It also returns the largest Holding percentage and priced Holding count. The heuristic describes observed holding-value concentration only. It does not measure cross-asset correlation, volatility, liquidity, tax exposure, suitability, expected return, or personalized risk, and it emits no good/bad rating.

## 7. Goal projection

Every scenario is supplied by the caller. Declared risk tolerance is returned as explanatory context and never chooses an assumption.

Annual nominal return, annual inflation, and annual fee inputs are decimal fractions. The v1 policy uses nominal monthly rates:

~~~text
monthly_net_return = (annual_return - annual_fee) / 12
monthly_inflation = annual_inflation / 12
~~~

The module iterates month by month. Beginning contributions are added before that month’s return; end contributions are added afterward on the requested monthly, quarterly, or annual schedule. Inflation-adjusted value is nominal value divided by the accumulated monthly inflation index. Modeled growth is nominal value minus the starting amount and explicit contributions. Goal shortfall or surplus compares the nominal result with the explicitly supplied nominal goal.

With zero return and no fee, nominal value equals starting value plus counted contributions. An authorized CashFlowSummary identifier may be carried as context, but it never silently changes contribution inputs.

## 8. Reserved cash-flow interface

M2 defines types only for bank/card imports, normalized transactions, versioned categorization, recurring-expense candidates, transfer/card-payment reconciliation, monthly/category summaries, trends, coverage, warnings, and a minimized CashFlowSummary. There is no CashFlowAnalysisService implementation, bank connection, PDF extraction, automatic transaction, or seventh agent in M2.
