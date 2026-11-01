# M8 coverage report

Backend full regression: 6,501 of 7,439 statements covered, **87.39%** line/statement coverage.
This passes the transcribed 80% coursework fallback target and is below the 90% “Excellent” target.
The exact machine report is `backend/artifacts/m8/backend-coverage.json`; generated code and
fixtures were not counted as application statements.

Frontend verification includes 35 Vitest tests across eight files, nine Chrome end-to-end journeys,
TypeScript checking, ESLint, Prettier, and a production build. Frontend line/branch instrumentation
is not installed, so frontend numerical coverage is explicitly unavailable and remains in the
known-risk register rather than being estimated.

Coverage does not average away critical gates. Arithmetic, access/isolation, cache false-hit,
redaction, citation, financial-safety, and Inspector fidelity retain their own pass/review status.
