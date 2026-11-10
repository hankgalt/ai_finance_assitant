# M11 delivery report — Delivery pipeline and short-lived identity boundary

Status: Slice 4 repository controls implemented and locally qualified; GitHub/GCP activation pending | 2026-11-09

## Scope and decisions

This slice implements the repository-controlled portion of M11 slice 4 for PR-017 under ADR-019,
ADR-029, and proposed ADR-030. It advances QR-003, QR-005–QR-007, QR-010–QR-011, and
QR-014–QR-015 and adds source-side EVAL-20 evidence. It does not provision GCP, modify DNS, change
GitHub repository settings, publish an image, or claim that Workload Identity Federation or any
deployment control is operational.

The owner-approved single-operator boundary remains explicit: the public GitHub Pro repository uses
`hankgalt` as the required staging and production reviewer, permits self-review, and has no
independent backup approver. The machine-readable boundary is
[`contracts/deployment/delivery-policy.v1.json`](../contracts/deployment/delivery-policy.v1.json).

## Delivered implementation

- Deterministic backend CI uses the locked Python environment, formatting, lint, typing, the
  credential-free suite, and a digest-pinned PostgreSQL 17.11 service for the managed-state
  qualification. Frontend CI runs the frozen pnpm install, formatting, lint, typing, unit tests, and
  the `/finance_assistant` production build.
- Every third-party GitHub Action reference is pinned to a full commit SHA. Dependabot covers
  GitHub Actions, Python/uv, pnpm, and both Dockerfiles; delivery paths are owned by `@hankgalt`.
- Scheduled and change-triggered security checks cover dependency review/audits, secret scanning,
  CodeQL, and repository vulnerability/secret/misconfiguration scanning. Image publication also
  blocks on high/critical Trivy findings.
- Backend and frontend images use digest-pinned base images and explicit non-root identities. The
  backend preloads its frozen dense/sparse embedding models and runs Hugging Face access offline.
  The frontend serves only `/finance_assistant`, refuses to turn missed API paths into SPA HTML,
  and returns 404 at the root path.
- Main-branch image publication uses immutable Git-SHA tags in GHCR and emits GitHub build
  provenance attestations. Manual workflow dispatch builds and scans but does not publish.
- A manual, protected-environment workflow requests a GitHub OIDC token, exchanges it through GCP
  Workload Identity Federation, and performs only `gcloud projects describe`. It accepts no service
  account key or other credential payload.
- All Compose image references are now digest pinned. `delivery-check` and `container-build` expose
  the capability checks without introducing a milestone-owned implementation path.

## Verification record

| Command/check | Actual result |
| --- | --- |
| Initial `pytest -q -x backend/tests/test_delivery_workflows.py` | expected red: delivery policy did not exist |
| `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py` | 8 passed |
| `backend/.venv/bin/ruff format --check backend/src backend/tests` | 156 files already formatted |
| `backend/.venv/bin/ruff check backend/src backend/tests` | passed |
| `backend/.venv/bin/mypy` | passed for 156 source/test files |
| `backend/.venv/bin/python -m pytest -q` | 372 passed, 6 skipped, 4 deselected in 6.30 s |
| PostgreSQL 17.11 managed-state qualification | 5 passed, 2 deselected in 1.75 s |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache uv lock --check --offline` | 136 packages resolved; lock current |
| `frontend/pnpm format:check`, `lint`, `typecheck` | passed |
| `frontend/pnpm test` | 14 files and 72 tests passed |
| `frontend/pnpm build` | passed; generated assets use `/finance_assistant` |
| Backend Docker build and network-disabled encoder smoke | passed as UID/GID `10001:10001`; dense vector 384 dimensions |
| Frontend Docker build and HTTP smoke | passed as UID/GID `101:101`; base path served; API/root returned 404 |
| `pip-audit==2.9.0` against locked runtime export | no known vulnerabilities |
| `pnpm audit --prod --audit-level high` | no known vulnerabilities |
| `docker compose config --quiet` | passed |
| `git diff --check` | passed |

The first Docker frontend build exposed a missing repository-level `contracts/` build input; the
Dockerfile now copies that shared contract without duplicating it. The first local PostgreSQL test
attempt was denied by the managed sandbox's loopback boundary; the identical test passed after the
test process received loopback permission. No GitHub-hosted CodeQL, Gitleaks, Trivy, GHCR, or
attestation run is claimed by this local record.

## Security and privacy impact

CI jobs start with read-only repository permissions and grant write scopes only to the image
publication job. Cloud identity uses short-lived OIDC federation and environment-owned non-secret
resource identifiers; no long-lived GCP credential is accepted by the workflow, contract, or
repository. Images run without root, API fallback fails closed in the static server, model downloads
are excluded from backend runtime, and immutable references reduce dependency substitution risk.
This slice does not broaden any provider entitlement or retention right.

## Stop gate and remaining evidence

- Create the `staging` and `production` GitHub environments and configure `hankgalt` as the required
  reviewer only when the repository settings are ready to be activated.
- Slice 5 must provision separate environment-specific Workload Identity Federation providers and
  service accounts through reviewed Terraform. Only then can the three non-secret GitHub
  environment variables be populated and the read-only identity smoke executed.
- Execute the workflows on GitHub and retain actual CodeQL, dependency-review, Gitleaks, Trivy,
  image-digest, and build-attestation evidence. Local source qualification is not a substitute.
- Automated GCP deployment remains disabled. Terraform plan/apply, migration, staging smoke,
  no-direct-workload-bypass, promotion, rollback, and production/demo cutover belong to later slices.
- Proposed ADR-030 remains Proposed until the complete M11 qualification passes.

## Artifact paths

- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/images.yml`
- `.github/workflows/cloud-identity-smoke.yml`
- `infrastructure/container/backend/Dockerfile`
- `infrastructure/container/frontend/Dockerfile`
- `contracts/deployment/delivery-policy.v1.json`
- `backend/artifacts/release/deployment/delivery-controls.v1.json`
- `backend/tests/test_delivery_workflows.py`
