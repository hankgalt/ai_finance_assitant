# M8 qualification artifacts

- `qualification-report.v1.json` is the full-profile machine report for EVAL-01 through EVAL-18.
- `qualification-core.v1.json` records the credential-free backend/frontend core profile before
  local service and browser checks.
- `backend-junit.xml` is the backend regression JUnit report.
- `backend-coverage.json` is the backend line-coverage report.
- `dependency-scan.v1.json` records the production dependency audit and pypdf remediation.
- `environment-manifest.v1.json` records the local toolchain used for this run.

The reports contain no credentials, prompts, financial data, or raw provider/model payloads. A
non-passing release gate is intentional while the M8 human/live-model review remains pending.
