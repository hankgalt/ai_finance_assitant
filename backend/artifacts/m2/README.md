# M2 evidence bundle

`calculation-goldens.v1.json` records the hand-worked portfolio arithmetic checked by the M2 test suite. Goal goldens and valid/adversarial source samples live under `backend/data/finance/` and are indexed by `sample_manifest.v1.json`.

`coverage.json` and the privacy-safe `test-results.json` summarize the final qualification commands recorded in `docs/M2_delivery_report.md`. The uploaded source bodies used by import tests are fixtures; the PortfolioImport result retains only normalized records and a SHA-256 file hash.
