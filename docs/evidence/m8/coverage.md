# Coverage report

## Current (2026-11-05)

Backend full regression: 6,974 of 7,625 statements covered, **91.46%** line/statement coverage
(`uv run pytest --cov=ai_finance_assistant`; 334 passed, 1 skipped, 4 opt-in tests deselected).
The exact machine report is `backend/artifacts/quality/backend-coverage.json`.

Frontend Vitest/V8 coverage now measures every application module under `frontend/src` (tests,
test setup, and type declarations excluded), including modules no test imports. With 71 Vitest
tests it reports 718/765 lines (**93.85%**), 769/827 statements (**92.98%**), 280/303 functions
(**92.40%**), and 622/792 branches (**78.53%**). These figures include the M2.1 performance work.
`frontend/vite.config.ts` enforces 90% line and statement thresholds;
`backend/tests/test_release_bundle.py` checks the recorded artifacts.

Both suites meet the transcribed 90% "Excellent" target by lines and statements. Frontend branch
coverage remains below it and is reported separately rather than averaged in.

The coverage increase came from deterministic tests at existing interfaces, not product changes:

- `backend/tests/test_qdrant_store.py`: candidate writes, manifest metadata, dense/sparse/hybrid
  RRF retrieval, filters, activation/rollback, and every `validate_active` failure reason against
  Qdrant's real in-process engine. A thin wrapper reproduces only the server's HTTP 404 and payload
  index reporting, which local mode lacks.
- `backend/tests/test_response_cache_redis_adapter.py`: route TTL/expiry/schema recovery, session
  and filter scoping, exact/semantic mapping, purge, and readiness with in-memory Redis/RedisVL
  fakes.
- `backend/tests/test_knowledge_cli.py` and `backend/tests/test_knowledge_source_fetch.py`: the
  explicit run/rollback/validate commands, evaluation gating of activation, and HTTPS, host,
  media-type, size, and cache-integrity defenses.
- `frontend/src/features/market/MarketExperience.test.tsx`, `frontend/src/app/AppSession.test.tsx`,
  `frontend/src/features/portfolio/PortfolioImport.test.tsx`, and `frontend/src/lib/apiClient.test.ts`:
  market provenance/stale/error states, session restore and recovery, navigation, manual and file
  import flows, and API error/telemetry classification.

The opt-in `qdrant` and `redis` marked tests remain the authority for real-service behavior; the
fakes above do not replace them.

## Historical (M8/M9, 2026-10-31)

Backend coverage was 6,576/7,534 statements (87.28%). Frontend coverage counted only modules a test
imported and reported 504/628 lines (80.25%), 531/677 statements (78.43%), 412/639 branches
(64.47%), and 183/248 functions (73.79%).

Coverage does not average away critical gates. Arithmetic, access/isolation, cache false-hit,
redaction, citation, financial-safety, and Inspector fidelity retain their own pass/review status.
