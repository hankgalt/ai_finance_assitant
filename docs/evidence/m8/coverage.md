# M8 coverage report

Backend full regression: 6,576 of 7,534 statements covered, **87.28%** line/statement coverage.
This passes the transcribed 80% coursework fallback target and is below the 90% “Excellent” target.
The exact machine report is `backend/artifacts/m8/backend-coverage.json`; generated code and
fixtures were not counted as application statements.

Frontend verification includes 35 Vitest tests across eight files, nine Chrome end-to-end journeys,
TypeScript checking, ESLint, Prettier, and a production build. M9 installed Vitest/V8 coverage and
reports 504/628 lines (**80.25%**), 531/677 statements (**78.43%**), 412/639 branches
(**64.47%**), and 183/248 functions (**73.79%**). Only the line measure meets the transcribed 80%
fallback; it remains below the 90% “Excellent” target.

Coverage does not average away critical gates. Arithmetic, access/isolation, cache false-hit,
redaction, citation, financial-safety, and Inspector fidelity retain their own pass/review status.
