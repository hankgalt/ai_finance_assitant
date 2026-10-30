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
| `cd backend && uv run pytest --cov=ai_finance_assistant --cov-report=term-missing` | Passed; 175 passed, 1 skipped, 3 deselected, 87% |
| `cd frontend && pnpm format:check` | Passed |
| `cd frontend && pnpm lint` | Passed |
| `cd frontend && pnpm typecheck` | Passed |
| `cd frontend && pnpm test` | Passed; 15 tests in 5 files |
| `cd frontend && pnpm build` | Passed |
| `cd frontend && pnpm test:e2e` | Passed; 3 Chrome tests |
| `make m6-check` | Passed; frontend gates, 12 focused backend tests, and 3 Chrome tests |

The skipped test is the existing opt-in live-Qdrant integration test. The three deselected tests are
the opt-in live provider/model tests. No paid credential was used.

One first browser pass found a WCAG color-contrast failure on the sidebar label (4.18:1 versus the
required 4.5:1); the foreground token was darkened and the final multi-state Axe review passed.
The first browser launch also lacked Playwright's optional FFmpeg artifact; video recording was
disabled because M6 evidence uses screenshots. Neither issue was a product-test skip.

The browser server logged expected failed telemetry sends after mocked pages closed and the first-
party backend was intentionally absent. All journeys still passed, providing additional evidence
that unavailable telemetry has no user-visible effect.

Session lifecycle coverage proves that Cancel performs no transition, confirmation archives the
Active backend Session, the old opaque browser identifier is replaced, and the Assistant opens
empty. History then lists the Archived Session and exposes permanent deletion only after a second
confirmation. Separate component tests prove archive failure retains the original Active Session
identifier and History deletion removes only the selected Archived Session.

The component suite also proves that a complete 1,399-character educational narrative renders in
the Assistant without a generation-warning banner. Its maintained regression now verifies that the
narrative, each canonical source link, and each supplemental warning render once even when the
stored Workflow/Agent and chunk-level inputs overlap. The corresponding backend regression
preserves the complete narrative through persistence, REST recovery, and SSE.

Post-completion deduplication verification passed Prettier, ESLint, TypeScript, all 15 Vitest tests,
the Vite production build, and 13 focused backend M5/M6 tests. A Playwright rerun was attempted
twice: the archive/history journey passed, while Portfolio and Market navigation reached the
interface error boundary after Vite returned `504 Outdated Optimize Dep` for Recharts during lazy
module loading. This is retained as an honest environmental gate failure; it did not affect the
focused Assistant regression or production build.

The maintained Run-card regression additionally verifies that the stored question appears in bold
before the answer, GFM emphasis and tables render as semantic elements, and raw model-authored HTML
is not interpreted. API and restart tests verify the submitted message across Run create/get/list
and process reconstruction; schema version 3 keeps the field nullable for legacy Runs.

The responsive Run-card follow-up adds a 390 px browser assertion at the rendered application seam.
The first correction stopped the 895 px document overflow but left wide Markdown tables internally
scrollable. The revised acceptance behavior keeps every column visible: at 390 px the table and all
cell bounds remain inside the Run card, cell content has no horizontal overflow, and long values use
normal line wrapping with `overflow-wrap: anywhere` to expand row height. `pnpm format:check`,
`pnpm lint`, `pnpm typecheck`, all 15 Vitest tests, `pnpm build`, and the focused Playwright test pass.
The latest full four-test Playwright attempt produced two passes (Run-card containment and Session
archive/history) and two pre-existing development-server failures: Portfolio and Market lazy routes
entered the error boundary after Vite invalidated optimized Recharts dependencies. Those unrelated
journeys are not represented as passing in this maintenance run.

The persistent-sidebar regression serves a saved conversation taller than 1,440 px in a 720 px
desktop viewport. Before the correction, the Clear Active Session action had a zero viewport
intersection until the user reached the end of the conversation. The maintained browser test now
verifies that the action starts in view, stays in view after scrolling halfway down the page, keeps
the same vertical viewport coordinate, and remains above the viewport bottom.

The Run-card spacing regression renders an Agent result with no saved request message, one citation,
and one supplemental warning. It verifies at least 16 px between Run metadata and the agent divider,
and at least 24 px between the citation list and the first supplemental message. The pre-correction
metadata-to-divider measurement was 0 px.
