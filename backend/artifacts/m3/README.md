# M3 evidence bundle

`test-results.json` records the final focused and repository qualification. `coverage.json` is the machine-generated full-backend coverage report. `failure-matrix.v1.json` maps required provider states to automated tests. `demo-budget-transcript.v1.json` records the credential-free demonstration selection and the safe live-mode preflight refusal; it contains no credential or query value.

`live-test-harness.v1.json` records the later opt-in live-test marker, ordinary-suite exclusion proof, disabled-gate proof, explicit Alpha Vantage/Massive selection, maximum provider-call count, first-failure stop behavior, and incomplete live qualification. It contains no credentials or provider payloads.

Provider response fixtures are hand-authored synthetic data under `backend/data/providers/` and are hash-indexed by `fixture_manifest.v1.json`.
