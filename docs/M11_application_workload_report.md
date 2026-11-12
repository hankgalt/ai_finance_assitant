# M11 application workload implementation report

Status: staging create/deploy/no-direct-origin/destroy lifecycle exercised; current private runtime active and shared knowledge qualified | 2026-11-12

## Scope and traceability

This slice advances M11 and PR-017 under ADR-019, ADR-029, and proposed ADR-030. It implements the
repository-controlled portion of QR-003, QR-005–QR-007, QR-010–QR-011, and QR-014–QR-015 and adds
partial EVAL-19/EVAL-20 evidence. The staging workload was deployed and verified, removed by a
reviewed on-demand teardown, and subsequently recreated for shared-knowledge qualification. It does
not claim that an edge, DNS record, or IAP policy exists.

## Implemented interfaces

- `infrastructure/terraform/modules/application_workloads/` defines separate digest-pinned
  frontend and backend Cloud Run services. Both use internal/load-balancer-only ingress, disable
  their default URI, omit anonymous invoker grants, scale from zero to one instance, and expose
  liveness probes rather than treating missing Qdrant collections as a process failure.
- `infrastructure/terraform/environments/staging-workloads/` owns the services in the separate
  `workloads` state prefix. Its explicit inputs are the two image digests and the positive numeric
  Qdrant secret version. The backend uses the runtime identity, Direct VPC egress, and a pinned Cloud
  SQL Auth Proxy sidecar with automatic IAM authentication. The frontend identity has no database,
  network, or secret role.
- `infrastructure/terraform/environments/staging/` owns separate runtime and offline-release
  standard Secret Manager metadata with one user-managed `us-west1` replica. Terraform creates no
  secret version and never receives a payload. Only the runtime identity receives accessor IAM for
  the runtime secret; the release secret is never injected into an application workload. The
  obsolete PostgreSQL DSN secret containers are removed because those connections use passwordless
  IAM.
- `infrastructure/terraform/scripts/bootstrap-staging.sh` is the single lifecycle interface. Create
  order is foundation, direct owner entry of the Qdrant key, reviewed PostgreSQL grants, migration,
  then workloads. Destroy order is workloads first and managed state second after the existing
  exact data-loss confirmation. Interrupted privilege bootstrap attempts to remove the temporary
  owner user and disable Data API access.
- `infrastructure/terraform/scripts/mirror-merged-main-images.sh` idempotently mirrors the exact
  merged-main backend and frontend manifests into Artifact Registry, while
  `set-deployment-image-variables.sh` publishes and verifies their non-secret digest references in
  the selected GitHub environment.
- Before the edge exists, FastAPI uses the deliberately non-matching IAP audience
  `/projects/730340912967/global/backendServices/0`. It fails closed and must be replaced by the
  exact IAP backend-service audience in the edge slice.
- The Terraform workflow statically validates both roots and, when manually dispatched, produces
  separate machine-readable foundation and workload plans. It performs no apply.

The deployed model/provider modes remain `credential_free`, the response cache remains disabled,
and no provider access right is added or broadened.

## Verification

| Command | Result |
| --- | --- |
| `terraform fmt -check -recursive infrastructure/terraform` | Passed |
| `terraform validate` for modified staging roots | Passed for both roots |
| `bash -n infrastructure/terraform/scripts/bootstrap-staging.sh` | Passed |
| `bash -n` for the image mirroring and GitHub-variable scripts | Passed |
| `shellcheck infrastructure/terraform/scripts/*.sh` | Not run; `shellcheck` is not installed locally |
| `cd backend && .venv/bin/python -m ruff format --check .` | Passed |
| `cd backend && .venv/bin/python -m ruff check .` | Passed |
| `cd backend && .venv/bin/python -m pytest -q` | 406 passed, 8 skipped, 4 deselected |

The machine-readable record is
`backend/artifacts/release/deployment/application-workloads.v1.json`.

## Security and privacy impact

No credential or secret payload is committed, accepted by the wizard, placed in Terraform input,
or stored in GitHub. The backend alone can read the exact numeric Qdrant version. Cloud SQL remains
private and passwordless. Direct Cloud Run origins were disabled in live readback, had no public
invoker, and rejected the wizard's direct-origin request before the earlier runtime was destroyed.
Read-only reconciliation on the current 2026-11-12 recreation again found both services `Ready`,
their default URLs disabled, internal/load-balancer ingress, and no anonymous IAM. Google
reports the service launch stage as `GA` after accepting the `BETA`-gated disabled-default-URL
field; Terraform therefore ignores only that normalized metadata while continuing to manage and
verify the disabled URL and ingress fields. The workload preserves the
implemented Application Principal and per-resource authorization layer and starts with an empty
deployed store.

## Remaining MVP gates

The workload and reviewed down/recreate paths have executed successfully; the disposable runtime is
currently active. The separate shared-knowledge release is qualified and the runtime key proved
read-only. Focused runtime-key rotation, the load balancer, the real IAP audience and owner
allow-list, HTTPS, DNS, and deployed product journeys remain later MVP gates. Backup/PITR, HA,
capacity, SLO/alerting, incident, and full rollback qualification remain post-MVP hardening.
