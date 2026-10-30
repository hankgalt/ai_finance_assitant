# M6 evidence index

All screenshots use deterministic API fixtures and visibly label synthetic provider data. They are
product-state evidence, not evidence of a live market-data call.

- `playwright-report/` — locally generated and ignored HTML report; recreate with
  `cd frontend && pnpm test:e2e`. Durable results are recorded in `test-report.md`.
- `assistant-empty.png` — Assistant empty/successful Session state.
- `portfolio-validation.png` — accepted import awaiting explicit save approval.
- `market-success.png` — synthetic provider quote/history with provenance and table alternative.
- `goals-success.png` — backend scenario chart, assumptions, warning, and table alternative.
- `mobile-market.png` — 390 px navigation and responsive stale-data market result.
- `session-clear-confirmation.png` — focused confirmation before the Active Session is archived and replaced.
- `session-history.png` — Archived Session history with view and separately destructive delete actions.
- `accessibility-review.md` — automated and manual review scope.
- `test-report.md` — commands and actual results.
- `contract-version-record.md` — OpenAPI/frontend contract authority.
- `telemetry-sample.json` — bounded sample with no product payload.
- `browser-fastapi-correlation.md` — W3C and request-correlation evidence.
