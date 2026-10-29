# M6 test report

Date: 2026-10-29  
Browser: Google Chrome 156.0.8078.73  
Runner: Playwright 1.64.1

## Final results

| Command | Result |
| --- | --- |
| `cd backend && uv run ruff format --check .` | Passed; 117 files formatted |
| `cd backend && uv run ruff check .` | Passed |
| `cd backend && uv run mypy` | Passed; 109 source files |
| `cd backend && uv run pytest --cov=ai_finance_assistant --cov-report=term-missing` | Passed; 167 passed, 1 skipped, 3 deselected, 87% |
| `cd frontend && pnpm format:check` | Passed |
| `cd frontend && pnpm lint` | Passed |
| `cd frontend && pnpm typecheck` | Passed |
| `cd frontend && pnpm test` | Passed; 9 tests in 4 files |
| `cd frontend && pnpm build` | Passed |
| `cd frontend && pnpm test:e2e` | Passed; 2 Chrome tests |
| `make m6-check` | Passed; frontend gates, 12 focused backend tests, and 2 Chrome tests |

The skipped test is the existing opt-in live-Qdrant integration test. The three deselected tests are
the opt-in live provider/model tests. No paid credential was used.

One first browser pass found a WCAG color-contrast failure on the sidebar label (4.18:1 versus the
required 4.5:1); the foreground token was darkened and the final multi-state Axe review passed.
The first browser launch also lacked Playwright's optional FFmpeg artifact; video recording was
disabled because M6 evidence uses screenshots. Neither issue was a product-test skip.

The browser server logged expected failed telemetry sends after mocked pages closed and the first-
party backend was intentionally absent. Both journeys still passed, providing additional evidence
that unavailable telemetry has no user-visible effect.
