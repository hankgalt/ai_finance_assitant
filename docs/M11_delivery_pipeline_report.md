# M11 delivery report — Delivery pipeline and short-lived identity boundary

Status: Slice 4 repository controls, GitHub scans, protected environments, and keyless GCP identity
qualified | 2026-11-10

## Scope and decisions

This report implements the repository-controlled portion of M11 slice 4 for PR-017 under ADR-019,
ADR-029, and proposed ADR-030. It advances QR-003, QR-005–QR-007, QR-010–QR-011, and
QR-014–QR-015 and adds EVAL-20 evidence. The controls were subsequently exercised on GitHub and the
slice 5 foundation activated WIF and protected environments. The separate
[`M11_staging_infrastructure_report.md`](M11_staging_infrastructure_report.md) is authoritative for
cloud mutations, Terraform drift, and the remaining workload/no-bypass stop gates. DNS remains
unchanged and no application workload is deployed.

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
  Docker patch/digest refreshes remain automated, while Python, Node, and NGINX runtime-line
  upgrades are held for explicit compatibility qualification against the supported Python 3.12,
  Node 24, and NGINX 1.30 lines.
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
| Initial `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py -k supported_runtime_patch_updates` | expected red: the container policy hard-coded qualified patch versions and digests |
| `backend/.venv/bin/python -m pytest -q backend/tests/test_delivery_workflows.py` | 14 passed |
| `backend/.venv/bin/ruff format --check backend/src backend/tests` | 156 files already formatted |
| `backend/.venv/bin/ruff check backend/src backend/tests` | passed |
| `backend/.venv/bin/mypy` | passed for 156 source/test files |
| `backend/.venv/bin/python -m pytest -q` (from `backend/`) | 387 passed, 6 skipped, 4 deselected in 5.91 s |
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

The 2026-11-12 advisory refresh subsequently identified GHSA-mmhr-3c5m-f64f in the locked
`soupsieve 3.0.4` transitive dependency. The project Python floor is now 3.11.5, matching the
minimum supported by the patched Soup Sieve line, and the lock selects `soupsieve 4.1` for every
supported runtime. The identical pinned `pip-audit` command then reported no known vulnerabilities;
the HTML-selection smoke and complete backend suite remained green.

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
revision and explicitly pin Trivy v0.76.2; the generated binary URL returns HTTP 200. Main-branch
run `42887806684` subsequently passed Gitleaks, Python and JavaScript CodeQL, dependency audits, and
the repository scan at commit `7f880028`; pull-request run `42887435575` also passed dependency
review and the complete security matrix.

The subsequent GitHub Container images run `42758880644` built both images and reached the image
scan, then failed because the digest-pinned runtime bases had aged past the workflow's
HIGH/CRITICAL threshold. The backend scan reported 41 Debian findings (34 HIGH and 7 CRITICAL) and
one critical uv finding; reproducing the gate locally also found 24 Alpine findings (22 HIGH and 2
CRITICAL) in the frontend runtime. The repaired backend uses a clean Python 3.12.16 / Debian 12.15
runtime stage and uv 0.13.4 only in its discarded builder stage. The frontend uses Node 24.22.2 for
the discarded builder and the current official unprivileged NGINX 1.30.6 / Alpine 3.24 runtime.
Both rebuilt artifacts pass the exact Trivy gate locally with zero HIGH/CRITICAL findings. A
replacement GitHub-hosted Container images run (`42761838064`) subsequently passed on main for
commit `ae079ef`, including the push-only GHCR publication and provenance-attestation path.

The later consolidated dependency merge at commit `7f880028` passed Deterministic CI run
`42887806884`, Security checks run `42887806684`, and Container images run `42887806753`. The image
run rebuilt, scanned, published, and attested both immutable-revision images. Staging and production
WIF providers and GitHub environments are now configured without credential payloads. The first
staging identity-smoke run `42903648350` reached the required-reviewer gate, then failed closed when
the name-only subject condition rejected GitHub's immutable-ID subject for this repository. A
reviewed Terraform remediation changed only the two provider conditions in place (`0` add, `2`
change, `0` destroy), using
`repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT`; its final plan was drift-free. After
required review, replacement staging run `42906846762` and production run `42903653548` both
exchanged short-lived credentials, returned `comfforts-369117` from the read-only project check,
cleaned up their temporary credential files, and passed.

Dependabot then opened Python 3.15 and Node 26 runtime-line PRs (`#2` and `#3`). Deterministic CI
correctly exposed that the container-policy test had encoded exact qualified patch versions rather
than the durable boundary. The test now permits patch and digest refreshes within the CI-qualified
Python 3.12, Node 24, Alpine 3.24, and NGINX 1.30 lines, continues to reject unqualified runtime-line
changes, and records that behavior with positive and negative regression fixtures. Dependabot now
suppresses those runtime-line jumps; adopting a later line requires an explicit compatibility and
container qualification change rather than an automated Dockerfile-only PR.

## Security and privacy impact

CI jobs start with read-only repository permissions and grant write scopes only to the image
publication job. Cloud identity uses short-lived OIDC federation and environment-owned non-secret
resource identifiers; no long-lived GCP credential is accepted by the workflow, contract, or
repository. Images run without root, API fallback fails closed in the static server, model downloads
are excluded from backend runtime, and immutable references reduce dependency substitution risk.
This slice does not broaden any provider entitlement or retention right.

## Stop gate and remaining evidence

- Merge and run `.github/workflows/terraform.yml`; retain its static-validation and read-only staging
  plan evidence.
- Automated GCP deployment remains disabled. Real-service recovery, workload deployment, IAP,
  no-direct-workload-bypass, promotion, rollback, and production/demo cutover remain later gates.
- Retain final published image digests with the integrated release evidence.
- Proposed ADR-030 remains Proposed until the complete M11 qualification passes.

## Artifact paths

- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/images.yml`
- `.github/workflows/cloud-identity-smoke.yml`
- `.github/workflows/terraform.yml`
- `infrastructure/container/backend/Dockerfile`
- `infrastructure/container/frontend/Dockerfile`
- `contracts/deployment/delivery-policy.v1.json`
- `backend/artifacts/release/deployment/delivery-controls.v1.json`
- `backend/artifacts/release/deployment/staging-foundation.v1.json`
- `backend/tests/test_delivery_workflows.py`
