# Calculation evidence

`portfolio-analysis-goldens.v1.json` records the hand-worked portfolio arithmetic checked by the calculation test suite. Goal goldens and valid/adversarial source samples live under `backend/data/calculations/` and are indexed by `fixture-manifest.v1.json`.

`backend/artifacts/quality/calculations-coverage.json` and `calculations-test-results.json` summarize the focused qualification commands. The uploaded source bodies used by import tests are fixtures; the PortfolioImport result retains only normalized records and a SHA-256 file hash. Milestone delivery history remains in `docs/M2_delivery_report.md`.
