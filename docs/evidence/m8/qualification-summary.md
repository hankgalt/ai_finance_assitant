# M8 qualification summary

Dataset: `m8-release-qualification-v1` | Status: automated qualification passed; review pending

The fixed runner covers EVAL-01 through EVAL-18 and writes the machine-readable report to
`backend/artifacts/m8/qualification-report.v1.json`. Its test environment strips live provider,
model, and tracing variables and explicitly uses `backend/.test.env`.

Full-profile results on the recorded environment:

- backend format/lint/strict mypy passed;
- backend regression: 264 passed, 1 opt-in Qdrant test skipped in the ordinary suite, 4 live/Redis
  tests deselected; 87.39% coverage;
- frontend: Prettier, ESLint, TypeScript, 35 Vitest tests, and production build passed;
- Chrome: 9 of 9 journeys passed, including accessibility alternatives, responsive layout,
  archive/delete lifecycle, Inspector success/partial/failure, and portfolio context;
- real local Qdrant integration: 1 passed; real local Redis/RedisVL integration: 1 passed;
- dependency scans: frontend clean; backend `pypdf` findings remediated and repeat scan clean;
- automated critical failures: 0.

The browser run exposed stale Vite optimizer reuse from a separate developer server on port 5173.
Playwright now uses isolated strict port 4173, disables reuse, and forces dependency optimization;
the minimized regression loop and full suite pass.

Six dimensions remain `review_required`: EVAL-01 current live routing, EVAL-03 live synthesis,
EVAL-08 claim/citation support, EVAL-10 groundedness, EVAL-12 financial safety, and EVAL-17
selected-model latency/cost. They are not converted to automated passes. No external provider,
OpenAI, or new LangSmith call was made.
