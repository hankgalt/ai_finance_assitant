# M11 delivery report — Managed-state adapter and operating contract

Status: PostgreSQL adapter and recovery procedure qualified locally; staging foundation provisioned;
Cloud SQL live recovery stop gate pending | 2026-11-10

## Scope and decisions

This slice advances the managed-state portion of PR-017 under ADR-019, ADR-029, and proposed
ADR-030. It implements QR-005–QR-007, QR-010–QR-011, and QR-014–QR-015 adapter behavior and adds
EVAL-18/EVAL-20 test seams. The real PostgreSQL adapter, least-privilege role boundary, synthetic
recovery-marker harness, and repeatable recovery procedure now pass local qualification. It does not
claim that the complete M11 slice 3, EVAL-20, Cloud SQL backup/PITR, or the private multi-user
deployment is qualified or operational.

The owner-approved topology is recorded in
[`contracts/deployment/managed-state.v1.json`](../contracts/deployment/managed-state.v1.json).
It selects single-zone Cloud SQL PostgreSQL 17 Enterprise `db-f1-micro` with the 10 GiB service
minimum SSD, seven daily backups, three-day PITR, no deployed response cache, same-project staging,
Google-managed encryption, regional Secret Manager, and credential-free deployed providers. The
Qdrant Free `us-central1` topology and sole GitHub approver are explicit private-demo limitations.

## Delivered implementation

- Backend-neutral application database ports and capability-named repositories preserve the
  existing Principal/Session authorization behavior for SQLite and PostgreSQL.
- A bounded Psycopg connection-pool adapter applies the final schema only to an empty PostgreSQL
  deployment, rejects unknown intermediate/newer versions, records persistence telemetry, and
  retains SQLite schema version 4 for loopback development.
- The official LangGraph PostgreSQL saver uses the existing strict serializer allow-list. Its
  schema is initialized by the operator migration command and verified without DDL by production
  startup and readiness.
- Production configuration rejects SQLite, startup DDL, startup retention, a configured response
  cache, a non-HTTPS/missing Qdrant endpoint, and a missing Qdrant runtime key.
- Qdrant clients now accept a runtime API key without exposing it in readiness output or contracts.
- `managed-state-migrate`, `managed-state-status`, and `managed-state-retention` Make targets expose
  explicit operator jobs. Retention runs outside the production web process and deletes expired
  checkpoint threads after application-owned Session cascades.
- The operator CLI now has a persistence-only configuration surface, so migrations, retention, and
  recovery checks do not require Qdrant, IAP, model, or provider configuration. DSNs remain redacted.
- A reviewable PostgreSQL role contract separates owner bootstrap, migration-owned default grants,
  runtime DML, and retention SELECT/DELETE. The owner path never receives or creates a password and
  is designed for immediate removal after the base grants are installed. The Data API used for the
  reviewed SQL is likewise temporary and is disabled on success or interruption.
- The first live privilege-bootstrap run installed the reviewed grants, then failed closed before
  any operator-job execution because `gcloud sql users delete` rejected a create-only `--type`
  option. The exit trap disabled Data API access; the exact temporary owner user was removed, and
  both normal and interrupted cleanup paths now omit the unsupported flag under regression coverage.
- The synthetic qualification command concurrently writes two isolated Principals, same-ID
  principal-owned resources, Runs/RunEvents, and checkpoints; proves restart durability and cross-
  Principal denial; and leaves a namespaced expired retention probe. Separate recovery and
  retention phases verify recovered markers and remove every synthetic source record.
- Digest-pinned private Cloud Run job definitions provide migration, qualification, and retention
  execution through Direct VPC egress and a Cloud SQL Auth Proxy sidecar using automatic IAM
  authentication. Cloud Run requires the multi-container images to use one registry boundary, so
  both reviewed manifests are mirrored without digest changes into the approved `us-west1` Artifact
  Registry. The jobs are now provisioned, but remain unexecuted and do not satisfy the real-service
  recovery gate until the staged qualification completes.
- A credential-gated PostgreSQL qualification test creates a randomly named schema, exercises
  Principal-owned application state and checkpoint-schema restart behavior, and drops only that
  generated schema. Ordinary CI skips it without `AIFA_TEST_POSTGRES_DSN`.
- The PostgreSQL suite now drives two signed IAP Principals through Sessions, Portfolios,
  Snapshots, Goal contexts, Runs, RunEvents, History, Inspector traces, SSE, and idempotency before
  and after application reconstruction. Guessed cross-Principal resource paths remain unavailable.
- Startup turns only deadline-expired `running` Runs into immutable `failed` resources with a safe
  `RUN_INTERRUPTED` result. Fresh Runs are preserved for rollout overlap, and late completion cannot
  replace the recovery terminal state.
- The independently invoked retention operation uses one observed timestamp, removes expired
  Session cascades and checkpoint threads, and is idempotent. A separate runtime role proved that
  verify-only startup and ordinary requests require DML but not DDL permission.
- The environment example documents configuration names only. Database DSNs, Qdrant keys, and
  other secret payloads remain absent from Git, Terraform inputs, contracts, and test fixtures.

## Verification record

| Command/check | Actual result |
| --- | --- |
| `backend/.venv/bin/ruff format src tests` | 155 files unchanged after formatting |
| `backend/.venv/bin/ruff check src tests` | passed |
| `backend/.venv/bin/mypy` | passed for 155 source/test files |
| Focused persistence/managed-state/configuration/identity suite | 27 passed in 1.41 s |
| `AIFA_TEST_POSTGRES_DSN=... pytest -q -m postgres tests/test_managed_persistence.py` against disposable PostgreSQL 17.11 | 5 passed, 2 deselected in 1.97 s |
| Updated `AIFA_TEST_POSTGRES_DSN=... pytest -q tests/test_managed_persistence.py` against disposable PostgreSQL 17 | 11 passed in 2.09 s |
| `pytest -q tests/test_staging_infrastructure.py` | 12 passed in 0.03 s |
| `terraform -chdir=infrastructure/terraform/environments/staging validate` | configuration valid with Google provider 8.9.0 |
| `bash -n infrastructure/terraform/scripts/qualify-cloud-sql-recovery.sh` | passed; `shellcheck` unavailable locally |
| `backend/.venv/bin/python -m pytest -q` | 392 passed, 8 skipped, 4 deselected in 6.16 s |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache uv lock --check --offline` | 136 packages resolved; lock current |
| `docker compose config --quiet` | passed |
| `git diff --check` | passed |

The default credential-free suite skips the seven opt-in PostgreSQL tests, but the same tests passed
separately against the disposable loopback PostgreSQL 17 Compose fixture. That fixture used a
temporary filesystem, loopback-only trust authentication, and was stopped after qualification. It
is not a deployment credential or topology. The other skip and four deselections are
the existing opt-in integration and credential-gated live-provider/model tests. Dependency resolution added
`langgraph-checkpoint-postgres==3.2.0`, Psycopg 3, and its pool/binary packages to the lockfile. The
capability evidence is recorded in
`backend/artifacts/persistence/managed-postgresql-qualification.v1.json`.

## Security and privacy impact

Production startup can no longer silently create or mutate database schemas. Runtime and checkpoint
connections are bounded, strict checkpoint deserialization remains enforced, and retention is an
explicit independently scheduled operation. The PostgreSQL schema retains Principal ownership and
foreign-key cascades across Sessions, Runs, RunEvents, Portfolios, Snapshots, contexts, and
idempotency. Provider observations remain separately purgeable and live retention remains denied
without provider-specific rights. Readiness and operator output disclose no connection string or
API key.

## Stop gate and remaining evidence

- The later staging-foundation slice has provisioned Terraform state, IAM, private Cloud SQL, and
  empty Secret Manager containers. The private migration and synthetic-prepare jobs have now run
  successfully through the Cloud SQL IAM/private-network path. This report still claims no
  successful retention, recovered-target verification, backup restore, or PITR rehearsal.
- Complete the synthetic Cloud SQL recovery/retention procedure using the fully qualified backup
  name for the configured new-instance restore. The locally passing complete
  two-Principal REST/SSE/History/Inspector matrix remains required at the later assembled staging
  workload gate.
- Reproduce the locally passing migration/runtime/retention role boundary with Cloud SQL IAM and
  retain the generated execution names and measured recovery result in the release artifact.
- Measure `db-f1-micro` memory, latency, pool saturation, rollout overlap, and concurrent Runs;
  upgrade to `db-g1-small` if any acceptance threshold fails.
- Provision and rehearse seven-backup/three-day-PITR restore, deletion reconciliation, schema/image
  rollback, and timed RPO/RTO. The targets in the contract are not operational claims.
- The application and checkpoint saver use separate transactions. No whole-Run atomic-commit claim
  is made; deadline-expired interrupted Runs are now reconciled, but more granular crash-point tests
  remain part of Cloud SQL staging recovery.
- Exercise Qdrant authenticated readiness and collection activation separately. No Qdrant key or
  collection was created, accessed, or migrated in this slice.

## Artifact paths

- `backend/src/ai_finance_assistant/persistence/`
- `backend/tests/test_managed_persistence.py`
- `backend/tests/test_managed_state_contract.py`
- `backend/artifacts/persistence/managed-postgresql-qualification.v1.json`
- `contracts/deployment/managed-state.v1.json`
- `contracts/deployment/recovery-policy.v1.json`
- `infrastructure/terraform/modules/managed_state_jobs/`
- `infrastructure/terraform/scripts/qualify-cloud-sql-recovery.sh`
- `docs/research/managed_state_deployment_recommendations.md`
