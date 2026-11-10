# Product-oriented repository layout

Status: Authoritative under ADR-029; proposed deployment additions under ADR-030

Updated: 2026-11-05

The repository is organized by durable product capability and interface. Milestones describe
delivery history in `docs/`; they are not ownership boundaries for current machine-readable assets.

## Ownership rules

- `backend/data/` contains committed, versioned inputs and deterministic fixtures. A capability owns
  each directory. Ignored runtime databases are outside this committed-data contract.
- `backend/artifacts/` contains generated or reviewed evidence owned by a capability. Whole-product
  reports belong to `quality/` or `release/`.
- `contracts/` is organized by the interface a caller consumes.
- `backend/tests/` names the behavior or capability under test. A delivery milestone is not a test
  subject.
- `docs/*_delivery_report.md` and `docs/evidence/` retain milestone history and coursework evidence.
- `infrastructure/`, `.github/workflows/`, deployment contracts, and their tests are owned by the
  infrastructure, identity/access, delivery, or release capability. They never live under a
  milestone-named implementation directory.
- A path move is complete only when code defaults, Make targets, manifests, checksums, tests,
  documentation, and release audits all resolve to the new path.

## Current capability map

| Path | Owner |
| --- | --- |
| `backend/data/knowledge/` | Finance and Tax knowledge source governance and retrieval cases |
| `backend/data/calculations/` | Portfolio import and Goal Projection deterministic fixtures |
| `backend/data/providers/` | Market-data and news adapter fixtures |
| `backend/data/assistant/` | Assistant routing evaluation inputs |
| `backend/data/response-cache/` | Evidence-bound response-cache calibration |
| `backend/data/qualification/` | Cross-product release and security qualification inputs |
| `backend/artifacts/knowledge/` | Collection manifests, evaluations, activation, and rollback evidence |
| `backend/artifacts/calculations/` | Deterministic calculation goldens and focused evidence |
| `backend/artifacts/providers/` | Provider policy, failure, budget, and live-harness evidence |
| `backend/artifacts/assistant/` | Workflow graph, routing, and failure evidence |
| `backend/artifacts/models/` | Model/prompt inventory and adapter qualification evidence |
| `backend/artifacts/persistence/` | Lifecycle, migrations, streaming, and durable-cache evidence |
| `backend/artifacts/observability/` | RunEvent, trace-correlation, and metric evidence |
| `backend/artifacts/quality/` | Cross-product test, coverage, dependency, and JUnit reports |
| `backend/artifacts/release/` | Environment, selected-model review, and qualification decision |
| `contracts/api/` | Versioned FastAPI/REST interface manifest |
| `contracts/frontend/` | React-to-backend consumption manifest |
| `contracts/inspector/` | Measured Inspector interface manifest |
| `contracts/fixtures/` | Shared versioned contract fixtures |
| `frontend/e2e/` | Behavior-named product-experience and capability browser journeys; generated output stays in ignored test-report directories |

Capability directories may contain internal subdirectories when they improve locality, such as one
directory per knowledge base. Do not duplicate an artifact across capability and milestone trees;
the delivery report links to its single current location.

## Private multi-user deployment ownership

Proposed ADR-030 and M11 use the following capability-owned paths as their slices are approved and
implemented. The table defines ownership; the presence of a path or artifact is not evidence that
the complete cloud deployment is operational.

| Path | Owner |
| --- | --- |
| `backend/src/ai_finance_assistant/identity/` | Verified external identity, Application Principal, roles, and per-resource authorization policy |
| `contracts/deployment/` | Base-path, identity-claim, readiness, migration, and deployment interface contracts |
| `backend/data/qualification/deployment/` | Deterministic identity, isolation, migration, recovery, and deployment qualification inputs |
| `backend/artifacts/quality/security/` | Cross-product identity, isolation, threat, scan, and penetration evidence |
| `backend/artifacts/release/deployment/` | Terraform plans, image attestations, migration/rollback, staging, production, and release-decision evidence |
| `infrastructure/terraform/` | Reusable GCP infrastructure modules and environment composition without committed secrets or state |
| `.github/workflows/` | Capability checks, supply-chain validation, infrastructure plan, approval-gated deployment, and rollback orchestration |

Tests continue to live under behavior-named backend/frontend/infrastructure test paths. For example,
an IAP assertion test is named for signed-identity validation, not `test_m11`. Terraform state,
runtime databases, credentials, downloaded collections, and environment-specific secret values are
runtime/deployment state and are never committed as capability artifacts.
