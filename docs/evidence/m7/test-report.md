# M7 test report

Date: 2026-10-30

| Command | Result |
| --- | --- |
| `backend/.venv/bin/ruff format --check .` | Passed; 119 files formatted |
| `backend/.venv/bin/ruff check .` | Passed |
| `backend/.venv/bin/mypy` | Passed; 111 source files |
| `backend/.venv/bin/pytest --cov=ai_finance_assistant --cov-report=term-missing` | Passed; 192 passed, 1 skipped, 3 deselected, 88% coverage |
| `backend/.venv/bin/pytest tests/test_m7_contract_manifest.py tests/test_m5_api.py tests/test_m5_persistence.py -q` | Passed; 20 tests |
| `pnpm format:check` | Passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm test` | Passed; 30 tests in 8 files |
| `pnpm build` | Passed; Vite production build |
| `pnpm exec playwright test e2e/m7.spec.ts` | Passed; 1 Chrome journey |
| `UV_CACHE_DIR=/tmp/ai-finance-uv-cache make m7-check` | Passed; all frontend gates, 31 focused backend tests, and 1 Chrome journey |

The Qdrant integration test was skipped because no explicitly configured service was requested.
Three credential-gated live provider/model tests were deselected by the ordinary test marker.
Playwright required permission to bind the local Vite development server to `127.0.0.1:5173`.
No external account or network provider was used.

## Sequence-label maintenance — 2026-10-31

| Command | Result |
| --- | --- |
| `pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build` through `make m7-check` | Passed; 32 Vitest tests in 8 files and production build |
| M7 focused backend gate through `make m7-check` | Passed; Ruff, strict mypy, and 31 tests |
| Sandboxed `pnpm exec playwright test e2e/m7.spec.ts` through `make m7-check` | Local Vite bind denied with `EPERM` after preceding gates passed |
| Approved local-browser `pnpm exec playwright test e2e/m7.spec.ts` | Passed; 1 Chrome journey in 3.3 seconds |
| Approved `UV_CACHE_DIR=/tmp/aifa-uv-cache make m7-check` | Passed complete gate; 32 frontend tests, production build, 31 backend tests, and 1 Chrome journey in 3.0 seconds |

The browser journey asserts nonconsecutive Workflow positions (`#0, #5`) and the consecutive
Finance Q&A range (`#2–#4`), regenerates success/partial/failure screenshots, and retains the Axe
and prompt-redaction assertions. No external account or network provider was used.
