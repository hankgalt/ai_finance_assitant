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
  the `/finance_assistant` production build. Both pnpm callers use the immutable
  `pnpm/action-setup` v6.1.0 revision, whose action runtime is Node.js 24.
- Every third-party GitHub Action reference is pinned to a full commit SHA. Dependabot covers
  GitHub Actions, Python/uv, pnpm, and both Dockerfiles; delivery paths are owned by `@hankgalt`.
- Scheduled and change-triggered security checks cover dependency review/audits, secret scanning,
  CodeQL, and repository vulnerability/secret/misconfiguration scanning. Image publication also
  blocks on high/critical Trivy findings. Repository and image scans use the immutable Trivy Action
  v0.36.0 revision and explicitly pin the Trivy v0.76.2 security-fix release.
- Backend and frontend images use current, digest-pinned base images and explicit non-root
  identities. The backend uses separate builder/runtime stages, preloads its frozen dense/sparse
  embedding models, runs Hugging Face access offline, and excludes uv and its build cache from the
  runtime image. The frontend uses the maintained official `nginx/nginx-unprivileged` namespace,
  serves only `/finance_assistant`, refuses to turn missed API paths into SPA HTML, and returns 404
  at the root path.
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
| Initial `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py -k trivy` | expected red: workflows used the Trivy Action v0.33.1 default scanner |
| Initial `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py -k pnpm_setup` | expected red: workflows used the Node.js 20-based pnpm Action v4 |
| Initial `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py -k container_builds` after the GitHub image-scan failure | expected red: stale backend/frontend bases and the single-stage backend runtime did not satisfy the repaired image boundary |
| `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py` | 11 passed |
| `backend/.venv/bin/ruff format --check backend/src backend/tests` | 156 files already formatted |
| `backend/.venv/bin/ruff check backend/src backend/tests` | passed |
| `backend/.venv/bin/mypy` | passed for 156 source/test files |
| `backend/.venv/bin/python -m pytest -q` (from `backend/`) | 375 passed, 6 skipped, 4 deselected in 6.35 s |
| Trivy installer URL check for v0.65.0 / v0.76.2 | HTTP 404 / HTTP 200 |
| PostgreSQL 17.11 managed-state qualification | 5 passed, 2 deselected in 1.75 s |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache uv lock --check --offline` | 136 packages resolved; lock current |
| `frontend/pnpm format:check`, `lint`, `typecheck` | passed |
| `frontend/pnpm test` | 14 files and 72 tests passed |
| `frontend/pnpm build` | passed; generated assets use `/finance_assistant` |
| Backend Docker build and network-disabled encoder smoke | passed as UID/GID `10001:10001`; dense vector 384 dimensions; uv and its build cache absent from runtime |
| Trivy v0.76.2 backend image gate (`vuln,secret,misconfig`; HIGH/CRITICAL; ignore unfixed) | passed; Debian 12.15 and Python packages reported zero findings |
| Frontend Docker build and HTTP smoke | passed as UID/GID `101:101`; base path and health returned 200; root returned 404 |
| Trivy v0.76.2 frontend image gate (`vuln,secret,misconfig`; HIGH/CRITICAL; ignore unfixed) | passed; Alpine 3.24.4 reported zero findings |
| `pip-audit==2.9.0` against locked runtime export | no known vulnerabilities |
| `pnpm audit --prod --audit-level high` | no known vulnerabilities |
| `docker compose config --quiet` | passed |
| `git diff --check` | passed |

The first Docker frontend build exposed a missing repository-level `contracts/` build input; the
Dockerfile now copies that shared contract without duplicating it. The first local PostgreSQL test
attempt was denied by the managed sandbox's loopback boundary; the identical test passed after the
test process received loopback permission. The first GitHub dependency-audit run also showed that
`pnpm/action-setup` cannot discover `frontend/package.json` from the repository root; both workflow
callers now pass the locked pnpm version explicitly. The next GitHub-hosted Deterministic CI run
completed successfully but warned that the pnpm Action v4 runtime targeted deprecated Node.js 20;
both callers now pin the Node.js 24-based pnpm Action v6.1.0 revision. The first Gitleaks
pull-request run required GitHub's automatic token to be mapped explicitly; the secret-scan job now
has read-only PR metadata access with commenting disabled. The first repository-scan run then
exposed an upstream installer compatibility failure: the Trivy Action v0.33.1 defaulted to Trivy
v0.65.0, while the installer it
checked out from the current Trivy `main` branch returned HTTP 404 for that release's generated
`get.trivy.dev` binary URL. Repository and image scans now use the immutable Trivy Action v0.36.0
revision and explicitly pin Trivy v0.76.2; the generated binary URL returns HTTP 200. No successful
GitHub-hosted Gitleaks, CodeQL, Trivy, GHCR, or attestation run is claimed by this local record.

The subsequent GitHub Container images run `42758880644` built both images and reached the image
scan, then failed because the digest-pinned runtime bases had aged past the workflow's
HIGH/CRITICAL threshold. The backend scan reported 41 Debian findings (34 HIGH and 7 CRITICAL) and
one critical uv finding; reproducing the gate locally also found 24 Alpine findings (22 HIGH and 2
CRITICAL) in the frontend runtime. The repaired backend uses a clean Python 3.12.16 / Debian 12.15
runtime stage and uv 0.13.4 only in its discarded builder stage. The frontend uses Node 24.22.2 for
the discarded builder and the current official unprivileged NGINX 1.30.6 / Alpine 3.24 runtime.
Both rebuilt artifacts pass the exact Trivy gate locally with zero HIGH/CRITICAL findings. A
successful replacement GitHub-hosted run remains pending.

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
