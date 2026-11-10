# M11 delivery report — Managed-state adapter and operating contract

Status: PostgreSQL adapter recovery qualified locally; Cloud SQL recovery stop gate pending | 2026-11-09

## Scope and decisions

This slice advances the managed-state portion of PR-017 under ADR-019, ADR-029, and proposed
ADR-030. It implements QR-005–QR-007, QR-010–QR-011, and QR-014–QR-015 adapter behavior and adds
EVAL-18/EVAL-20 test seams. The real PostgreSQL adapter portion of the slice-3 qualification now
passes locally. It does not claim that the complete M11 slice 3, EVAL-20, Cloud SQL backup/PITR, or
the private multi-user deployment is qualified or operational.

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
| `backend/.venv/bin/python -m pytest -q` | 364 passed, 6 skipped, 4 deselected in 6.09 s |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache uv lock --check --offline` | 136 packages resolved; lock current |
| `docker compose config --quiet` | passed |
| `git diff --check` | passed |

The default credential-free suite skips the five opt-in PostgreSQL tests, but the same tests passed
separately against the disposable loopback PostgreSQL 17.11 Compose fixture. That fixture used a
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

- Provision no infrastructure from this report. Terraform, IAM, Cloud SQL, Secret Manager,
  Cloud Run, GitHub environments, IAP, DNS, and the Qdrant release transfer belong to later slices.
- Repeat the passing PostgreSQL qualification test against Cloud SQL staging, then run the full
  two-Principal REST/SSE/History/Inspector matrix there.
- Reproduce the locally passing separate migration/runtime-role boundary with Cloud SQL IAM and
  select/qualify the concrete Cloud SQL connection authentication path.
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
- `docs/research/managed_state_deployment_recommendations.md`
