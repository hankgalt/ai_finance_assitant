# Provider evidence

`failure-matrix.v1.json` maps required provider states to automated tests. `demo-budget-transcript.v1.json` records the credential-free demonstration selection and the safe live-mode preflight refusal; it contains no credential or query value. Focused provider test and coverage reports live under `backend/artifacts/quality/`.

`live-test-harness.v1.json` records the later opt-in live-test marker, ordinary-suite exclusion proof, disabled-gate proof, explicit Alpha Vantage/Massive selection, maximum provider-call count, first-failure stop behavior, and incomplete live qualification. It contains no credentials or provider payloads.

`deployment/live-mode-<revision>.v1.json` is produced only after the owner completes the reviewed
staging activation and browser qualification. It records numeric secret-version identifiers,
configuration and boundary readback, provider-account attestations, and pass/fail outcomes. It never
records a credential, prompt, provider response, portfolio value, or other user content.

Provider response fixtures are hand-authored synthetic data under `backend/data/providers/` and are hash-indexed by `fixture-manifest.v1.json`.

Milestone delivery history remains in `docs/M3_delivery_report.md`.
