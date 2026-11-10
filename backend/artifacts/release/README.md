# Release qualification artifacts

- `qualification-report.v1.json` is the full-profile machine report for EVAL-01 through EVAL-18.
- `qualification-core.v1.json` records the credential-free backend/frontend core profile before
  local service and browser checks.
- `backend/artifacts/quality/backend-junit.xml` is the backend regression JUnit report.
- `backend/artifacts/quality/backend-coverage.json` is the backend line-coverage report.
- `backend/artifacts/quality/dependency-scan.v1.json` records the production dependency audit and pypdf remediation.
- `environment-manifest.v1.json` records the local toolchain used for this run.
- `live-model-review.v1.json` records the bounded selected-model observations and owner-decision
  state without retaining prompts or generated answers.
- `deployment/delivery-controls.v1.json` records locally qualified repository delivery controls and
  the GitHub/GCP activation evidence that remains pending.

The reports contain no credentials, prompts, financial data, or raw provider/model payloads. The
final full-profile report records all dimensions passed and `release_gate_passed: true`.
