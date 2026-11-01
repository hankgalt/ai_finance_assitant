# M9 delivery report — product documentation, coursework packaging, and release

Date: 2026-10-31

Status: Complete; owner-only private-demo and coursework package qualified

Scope: PR-014, PR-015; CA-01 through CA-13; ADR-010, ADR-011

## Outcome

M9 packages the owner-only private demonstration without widening it into a public release. It adds
a concise user guide, clean-start/developer guide, operator runbook, eight-minute credential-free
demo, source/license and version registers, release notes, limitations, rollback guidance,
coursework evidence matrix, and signed completion checklist.

The official MCP Python SDK exposes four read-only stdio tools backed by the same active retrieval,
provider, deterministic Portfolio, and deterministic Goal modules used by the application. The
adapter stores no Portfolio input and exposes no Session, persistence mutation, administration,
credential, or trade interface. In-memory and external-subprocess clients verify discovery,
annotations, contracts, provenance, and deterministic results.

M9 also installs the Vitest V8 coverage provider. Frontend coverage is now measured at 80.25% lines,
78.43% statements, 64.47% branches, and 73.79% functions. The line result meets only the transcribed
80% fallback target. Backend coverage is 87.28%; neither suite is represented as meeting 90%.

## Delivered artifacts

- `docs/release/`: operating and demonstration bundle.
- `docs/evidence/m9/`: coursework matrix, clean-start record, MCP evidence, and checklist.
- `backend/data/evaluation/m9_release_manifest.v1.json`: machine-audited PR/CA/evidence map.
- `backend/artifacts/m9/frontend-coverage/coverage-summary.json`: measured frontend coverage.
- `ai_finance_assistant.mcp_adapter`: read-only stdio adapter.
- `backend/tests/test_mcp_adapter.py`: in-memory and external protocol/client tests.
- `backend/tests/test_m9_release_bundle.py`: path, requirement, link, checksum, coverage, and MCP
  release-surface audit.
- `make m9-check`: final qualification/package entry point.

## Verification

Locked Python and frontend dependency synchronization, Compose validation, and both active Qdrant
collection validations passed. `make m9-check` then passed frontend coverage, Ruff, strict mypy,
274 backend tests (1 skipped, 4 opt-in deselected), 35 frontend tests, the production build, nine
Chrome journeys, real Qdrant and Redis integration checks, and seven explicit MCP/release-bundle
tests. The regenerated report passes EVAL-01 through EVAL-18 with zero critical failures and zero
incomplete dimensions.

## Security, privacy, and release boundary

The MCP boundary reuses validation and deterministic authorities; tool failures are sanitized and
all annotations are read-only/non-destructive. It does not add authorization scope or network
listen sockets. The external-client test uses fake providers and a temporary local store.

The release remains loopback, owner-only, and suitable only for controlled private demonstration.
It does not implement public identity/multi-user authorization, managed storage/backup/HA, public
provider display rights, distributed quotas, WAF, or public capacity/SLO controls. External
telemetry remains optional, privacy-filtered, and operator/vendor-retention dependent.
