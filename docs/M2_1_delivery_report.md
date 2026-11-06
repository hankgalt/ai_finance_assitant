# M2.1 cost-basis unrealized performance delivery report

Status: **complete**  
Completed: 2026-11-05  
Implements: PR-003, PR-009, PR-010, PR-015; QR-001, QR-006; ADR-009, ADR-018, ADR-021

## Outcome

Portfolio Snapshots now report how priced holdings have moved against their imported cost basis,
using only data the user already imports. The arithmetic is defined in
[calculation policy §6a](M2_calculation_policy.md).

- Per Holding: cost basis total (total or per-unit basis), unrealized gain/loss, return on cost,
  acquisition date, holding period, and Actual/365 annualized return when held at least one year.
- Per currency: combined cost basis, covered market value, unrealized gain/loss, return on cost, and
  cost-basis value coverage. Currencies are never combined.
- Diversification adds the combined share of the five largest priced Holdings. HHI arithmetic is
  unchanged.
- The Portfolio Analysis agent receives the summaries as facts and is instructed to state coverage
  and limitation and not to recalculate or forecast. The read-only MCP `analyze_portfolio` tool
  returns the same Snapshot fields.
- The Portfolio Dashboard adds an "Unrealized gain and loss" section (signed summary metrics,
  coverage, limitation, a single-currency bar chart, and an accessible per-Holding table) and a
  "Top 5 holdings" metric. When several Portfolios are saved, the analyzed one is highlighted in the
  library with a "Shown below" tag and named in both result sections.

All three bundled example portfolios already carry cost basis and acquisition dates, so the demo
shows the new section without data changes. For example, `balanced_multi_account.json` valued at
its synthetic prices reports $30,100.00 cost, $11,496.00 unrealized gain (38.19%), and 100% cost-
basis coverage.

## Files and interfaces changed

- `backend/src/ai_finance_assistant/finance/models.py`: additive `HoldingValuation` fields,
  `UnrealizedPerformance`, `DiversificationHeuristic.top_five_holding_percent`, and
  `PortfolioSnapshot.performance`. `calculation_policy_version` accepts v1 and v2 and defaults to v2.
- `backend/src/ai_finance_assistant/finance/portfolio_analysis.py` and `precision.py`.
- `backend/src/ai_finance_assistant/agents/specialists.py`: performance facts and instructions.
- `frontend/src/types/contracts.ts`, `frontend/src/features/portfolio/PerformanceSection.tsx`,
  `PortfolioExperience.tsx`, and `frontend/src/styles.css`.
- Data and evidence: `backend/data/calculations/portfolio-performance.v1.json`,
  `backend/artifacts/calculations/portfolio-performance-goldens.v1.json`, and the fixture manifest.
- Authority updates: PR-009, the system-design Portfolio Analysis row, calculation policy, the
  implementation plan, the glossary, the version register, and the example-portfolio guide.

The public `/api/v1` paths are unchanged; the Snapshot response gains optional fields. No migration
is required because Snapshots are stored as validated JSON and the new fields have defaults.

## Requirement and ADR mapping

- ADR-009: all figures come from the deterministic module; agents only interpret them.
- ADR-018: imported cost basis is read but never rewritten; results live only on the Snapshot.
- ADR-021: Decimal arithmetic, half-even rounding, explicit coverage, and per-currency partitioning
  are preserved. No volatility, correlation, or risk score is introduced.

## Commands and results

| Command | Result |
|---|---|
| `cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy` | Passed; 152 files formatted, 142 source files type-checked |
| `cd backend && uv run pytest --cov=ai_finance_assistant` | 334 passed, 1 skipped, 4 opt-in deselected; 6,974/7,625 statements (91.46%) |
| `cd frontend && pnpm format:check && pnpm lint && pnpm typecheck` | Passed |
| `cd frontend && pnpm test:coverage` | 70 passed; lines 93.85%, statements 92.98%, branches 78.53%, functions 92.38% |
| `cd frontend && pnpm build` | Passed |
| `make qualification-check` equivalent, written to a scratch path | `release_gate_passed: true`; 18 of 18 dimensions passed, no checks not run |

The committed `backend/artifacts/release/qualification-report.v1.json` remains the
`private-demo-2026-10-31` record and was not replaced.

## Tests added

- `backend/tests/test_portfolio_performance.py`: hand-worked golden; top-five concentration;
  one-year annualization boundary; future acquisition date; zero cost basis; total loss; quote-set
  price and quote-currency mismatch; currency partitioning; v1 Snapshot deserialization.
- `backend/tests/test_portfolio_import.py`: the fixture manifest also verifies the performance
  golden checksum.
- `backend/tests/test_agents.py`: Portfolio facts carry `finance-calculation-v2` and performance.
- `frontend/src/features/portfolio/PerformanceSection.test.tsx`: signed values and classes,
  coverage, missing cost basis, mixed-currency chart suppression, no usable price, and v1 Snapshots.
- `frontend/src/features/portfolio/PortfolioImport.test.tsx`: the analyzed Portfolio is marked in
  the saved list (`aria-current`, "Shown below") and named in the Snapshot context, and the mark
  moves when another Portfolio is analyzed.

Not run: Playwright browser journeys (require a running backend) and opt-in live model, live
provider, Qdrant, and Redis tests.

## Security, privacy, and limitations

No new input, provider call, persistence location, or telemetry attribute is added. Cost basis
already passed through import validation; the new facts sent to the model contain the same class of
user portfolio data the Portfolio agent already received.

- Price return only: dividends, distributions, separately paid fees, taxes, and cash flows are
  excluded, and the figure is neither time-weighted nor money-weighted.
- One cost basis and acquisition date per Holding; lot-level basis is not modeled.
- Holding period is reported in days and is not a tax holding-period determination.
- History-based volatility, drawdown, and risk-adjusted return remain out of scope; they need
  per-holding history beyond the private-demo market request budget and a new ADR.

## Unresolved decisions and next milestone

Whether to add history-based risk metrics, and under what request budget, is undecided. M10 and M11
remain independently permitted.
