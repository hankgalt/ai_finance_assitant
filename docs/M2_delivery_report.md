# M2 delivery report — Deterministic financial calculation modules

Status: Complete

Completed: 2026-10-27

Scope: PR-003, PR-005, PR-009, PR-016; QR-001, QR-002, QR-006, QR-009, QR-010, QR-015; EV-03, EV-04, EV-06; CA-07, CA-08; ADR-009, ADR-012, ADR-018, ADR-019, ADR-020, ADR-021

## Outcome

M2 delivers safe manual, JSON, CSV, and XLSX portfolio import through one interface; immutable imported portfolio contracts; separate provider-enrichment and calculated snapshot contracts; deterministic portfolio analysis; deterministic multi-scenario goal projection; and the types-only cash-flow seam reserved by ADR-020. It uses no LLM and makes no external provider calls.

The implementation resolves the three M2 policy decisions conservatively: negative quantities are rejected until a short-position model is approved, currencies remain partitioned without an identified FX set, and diversification is reported as holding-value HHI plus effective holding count rather than as a risk score. The authoritative formulas, limits, rounding, coverage behavior, and limitations are in [M2 calculation policy](M2_calculation_policy.md).

## Delivered interfaces and artifacts

- `PortfolioImport.import_portfolio(PortfolioImportRequest) -> PortfolioImportResult` validates all four input modes through the same domain construction path and returns aggregate, safe findings.
- `PortfolioAnalysis.analyze(PortfolioAnalysisRequest) -> PortfolioSnapshot` performs valuation, allocation, expense coverage, classification concentration, and the versioned diversification heuristic.
- `GoalProjection.project(GoalProjectionRequest) -> GoalProjectionResult` projects explicit, user-controlled scenarios month by month with recurring contributions, inflation, and modeled fees.
- `CashFlowAnalysisService` is a Protocol with request, normalized transaction, categorization, recurring-expense, reconciliation, and minimized `CashFlowSummary` contracts. M2 intentionally supplies no implementation.
- `backend/data/finance/` contains versioned valid, adversarial, and goal fixtures plus their SHA-256 manifest.
- `examples/portfolios/` contains user-importable synthetic JSON, CSV, and XLSX portfolios plus a checksum manifest and usage guide.
- `backend/artifacts/m2/` contains calculation goldens, privacy-safe qualification results, and coverage evidence.
- `openpyxl` 3.1.5 is locked for bounded, read-only XLSX parsing.

These interfaces are deliberately deep: callers use one import entry point, one portfolio-analysis entry point, and one goal-projection entry point. File-format parsing, precision, coverage, and partial-result rules remain internal to those modules.

## Frozen calculation and import versions

| Concern | Version |
| --- | --- |
| Portfolio import | `portfolio-import-v1` |
| Portfolio calculation | `finance-calculation-v1` |
| Diversification heuristic | `diversification-hhi-v1` |
| Goal projection | `goal-projection-v1` |

Any incompatible formula, rounding rule, duplicate interpretation, accepted import representation, or heuristic change requires a new version and new golden evidence.

## Acceptance evidence

| Acceptance statement | Result and evidence |
| --- | --- |
| Approved goldens reproduce exactly | Portfolio and goal hand-worked cases pass under the Decimal/round-half-even policy. Versioned inputs and expected results are in `backend/artifacts/m2/calculation-goldens.v1.json` and `backend/data/finance/goal_cases.v1.json`. |
| Four import modes converge | Manual, JSON, CSV, and generated XLSX representations produce the same normalized portfolio in `test_all_four_import_modes_share_one_validated_domain_result`. |
| User-importable examples remain valid | Three synthetic JSON/CSV/XLSX examples pass the real importer and deterministic Portfolio analysis with complete price and classification coverage in `test_example_portfolios.py`. |
| Errors aggregate safely | Adversarial fixtures report multiple row/field findings without echoing formula-like content. A rejected import returns no partial Portfolio. |
| Duplicates are not silently merged | Exact duplicate rows, duplicate Holding IDs, and likely duplicate security positions are blocking findings requiring a corrected import or future explicit merge decision. |
| Missing data remains missing | Missing or currency-mismatched prices produce no market value and reduce valuation coverage. Missing classification reduces classification coverage rather than creating an `unknown` value. |
| Mixed currencies are explicit | Each currency receives independent totals and metrics; `base_currency_total` is unavailable and a warning is returned when another currency is present without FX evidence. |
| Malicious and oversized files fail safely | Tests cover formula-like CSV, XLSX formulas, macro-like archive members, file limits, row limits, and nonfinite values. No formula or embedded content executes. |
| Arithmetic invariants hold | Tests cover quantity scaling, allocation totals, unpriced-Holding coverage, contribution monotonicity, zero-return identity, beginning/end contribution timing, and nominal versus real separation. |
| Import serialization and lifecycle are bounded | Serialized results contain normalized records and a source SHA-256 but no uploaded body. Parsing uses memory only and creates no temporary or durable upload artifact, including on failure, so M2 has no parser-owned file requiring cleanup. Durable Portfolio deletion belongs to the M5 persistence/API lifecycle and is not claimed here. |
| Cash-flow rework seam exists without later scope | Contract tests prove a minimized summary can be serialized without raw transaction descriptions. There is no cash-flow analysis implementation or seventh agent. |

## Verification record

Final qualification commands:

~~~bash
UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m2-check
UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify
cd backend && UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run pytest -q --cov=ai_finance_assistant --cov-report=json:artifacts/m2/coverage.json --cov-report=term tests
~~~

Final observed results:

- Focused M2 suite: 25 passed.
- Backend formatting, Ruff, and strict mypy: pass.
- Full backend suite: 44 passed and 1 skipped; overall measured coverage 83%.
- The only skip is the existing live-Qdrant integration test because `AIFA_TEST_QDRANT_URL` was not configured; M1 separately records its live pass. It does not exercise M2 behavior.
- Frontend formatting, lint, typecheck, 3 tests, and production build: pass.
- Failing or quarantined M2 cases: none.
- Manually verified M2 cases: none; acceptance evidence is automated.

Machine-readable results are `backend/artifacts/m2/test-results.json` and `backend/artifacts/m2/coverage.json`. The JSON test summary deliberately excludes local hostnames and absolute user paths. The sample manifest verifies hashes for all committed source fixtures and the hand-worked golden artifact.

Post-completion example-data verification on 2026-10-30: `uv run pytest tests/test_example_portfolios.py -q` passed 4 tests; Ruff and Ruff formatting checks passed for the new contract test. The example manifest verifies every end-user import file by SHA-256.

## Security, privacy, and observability impact

- Import bodies are untrusted. JSON and CSV require UTF-8; all file modes enforce byte, row, column, and text limits. XLSX additionally enforces archive member and decompressed-size bounds and rejects path traversal, macros, external links, embedded objects, formulas, and formula-like content.
- Unsafe values are replaced before they can enter diagnostic evidence. Findings contain bounded messages and locations rather than raw executable-looking content.
- Imported records, provider enrichment, and calculated snapshots remain separate and immutable. Provenance identifiers and unavailable states are explicit.
- M2 adds no database, network request, log payload, trace exporter, REST endpoint, authentication behavior, or retention job. Consequently it places no financial rows into RunEvents, OpenTelemetry, or LangSmith. M4 and M5 must instrument the module boundaries using only approved, minimized attributes.
- All committed samples are synthetic. No user financial data or paid credential is required for continuous integration.

## Limitations and unresolved decisions

- Money currently uses a generic two-decimal quantum; currency-specific minor-unit rules need a future policy version.
- M2 performs no FX conversion, short-position accounting, tax-lot accounting, performance measurement, derivative modeling, or suitability assessment.
- The HHI heuristic observes only holding-value concentration. It does not model correlation, volatility, liquidity, expected return, or personal risk.
- Goal scenarios use nominal monthly rates derived by dividing annual return, inflation, and fees by 12. They are illustrations supplied by the caller, not forecasts or selected investments.
- XLSX import accepts one worksheet and rejects formulas, hyperlinks/external links, macros, and embedded objects. Legacy XLS and macro-enabled XLSM are not supported.
- Market enrichment remains deterministic input at M2; no result is described as live provider data.
- Portfolio persistence, authorization, retention, durable cascade deletion, REST resources, and user-facing import flows belong to M5 and M6.
- Cash-flow analysis remains a planned enhancement; only its types and authorization-minimized summary seam are present.

No unresolved decision blocks M2 completion. M3 external market/news provider work is now permitted. M4 LangGraph and observability implementation remains dependent on completed M1, M2, and M3 provider contracts.
