# M11 delivery report — Staging infrastructure foundation

Status: Foundation provisioned and last applied plans drift-free; staging and production keyless
identity qualified; managed-state images mirrored and operator jobs provisioned; real-service recovery, workload, and no-
bypass qualification pending | 2026-11-10

## Scope and decisions

This M11 slice advances PR-017 and QR-003, QR-005–QR-007, QR-010–QR-011, and QR-014–QR-015
under accepted ADR-019/ADR-029 and proposed ADR-030. It implements the approved same-project
staging foundation in GCP project `comfforts-369117`, region `us-west1`. It does not deploy a Cloud
Run workload, configure load balancing/IAP/DNS, transfer Qdrant collections, enter secret payloads,
or broaden any provider entitlement.

The machine-readable desired-state boundary is
[`contracts/deployment/infrastructure-policy.v1.json`](../contracts/deployment/infrastructure-policy.v1.json).
The live qualification record is
[`backend/artifacts/release/deployment/staging-foundation.v1.json`](../backend/artifacts/release/deployment/staging-foundation.v1.json).

## Delivered foundation

- Protected, versioned GCS Terraform state is separated across bootstrap, staging, and production
  buckets. Public access prevention, uniform bucket access, seven-day soft deletion, abandon-on-
  state-removal behavior, and Terraform `prevent_destroy` guards are active.
- Shared Terraform enables the required APIs, provisions an immutable-tag Artifact Registry
  repository, and creates a USD 100 alert-only monthly budget with 50/80/100 percent thresholds.
- Staging and production GitHub OIDC providers are separate. Each trust condition requires the
  immutable GitHub repository ID `1435001816`, owner ID `2118128`, `refs/heads/main`, and the exact
  protected-environment subject. Plan identities have read-only project access plus the dedicated
  Service Usage Consumer permission required for quota-project requests. No service-account key was
  created.
- GitHub `staging` and `production` environments require reviewer `hankgalt`, permit the approved
  single-operator self-review model, and accept deployments only from `main`. Each environment
  stores only the project ID, WIF provider identifier, and deploy-service-account identifier.
- Staging uses an isolated VPC/private-service connection and a private-only Cloud SQL PostgreSQL 17
  Enterprise `db-f1-micro` instance. The live instance is zonal and `RUNNABLE`, uses IAM database
  authentication and encrypted-only connections, has 10 GiB SSD with a 20 GiB auto-grow ceiling,
  seven retained backups, three-day PITR, and deletion protection.
- Runtime, migration, and retention service accounts have only the selected Cloud SQL roles and
  secret access, and each has a matching Cloud SQL IAM database user. Regional Secret Manager
  containers exist for separate runtime/migration/retention PostgreSQL DSNs and the Qdrant runtime
  key. Terraform owns no secret version or payload.
- Capability-oriented Terraform modules, a non-secret operator wizard, a plan-only GitHub workflow,
  policy tests, and release evidence are committed under their infrastructure, delivery, contract,
  test, and release owners.
- Three non-HTTP Cloud Run jobs are provisioned for migration, synthetic qualification, and
  retention.
  Each uses its dedicated IAM database identity, Direct VPC private egress, a digest-pinned backend
  image, and a digest-pinned Cloud SQL Auth Proxy with automatic IAM authentication. The jobs have
  not been executed and are not represented as operational or recovery-qualified.
- Because the selected jobs no longer use DSN secret payloads, the expanded plan removes the three
  PostgreSQL secret-access IAM bindings. The protected empty secret containers remain historical
  metadata; only the runtime Qdrant identity retains its not-yet-used secret-access binding.
- The first reviewed apply removed those three obsolete IAM bindings, then failed closed before
  creating any job because Cloud Run rejected a GHCR backend combined with a GCR proxy. No partial
  job, database, network, service-account, secret-container, or user-data mutation remained. Both
  reviewed manifests were subsequently mirrored with unchanged digests into the existing immutable
  `us-west1` Artifact Registry; the corrected configuration now enforces that single registry.
- A separate staged recovery wizard requires a clean merged `main`, validates exact targets, removes
  temporary owner database elevation, qualifies one backup restore and one PITR clone, deletes the
  temporary instances, checks final Terraform drift, and writes only secret-free evidence.

## Provisioning and verification record

| Check | Actual result |
| --- | --- |
| Terraform/gcloud/provider versions | Terraform 1.17.1; Google provider 8.9.0; gcloud 593.0.0 |
| Bootstrap reviewed apply | First state bucket imported; 2 added, 1 hardened, 0 destroyed |
| Shared reviewed plans/apply | 31-resource foundation plus 2 quota-project bindings; later immutable-subject remediation was 0 add, 2 in-place changes, 0 destroy |
| Staging reviewed plans/apply | 24-resource foundation, retention IAM user, and dedicated empty retention DSN metadata; one stale empty-secret IAM binding revoked; zero data resources destroyed |
| Final bootstrap/shared/staging plans | All returned `No changes` |
| Infrastructure and delivery contract tests | 23 passed |
| Complete credential-free backend suite | 387 passed, 6 skipped, 4 deselected |
| Expanded operator/recovery regression suite | 392 passed, 8 skipped, 4 deselected; 11 opt-in managed PostgreSQL tests passed separately |
| First operator-job apply | failed closed on mixed GHCR/GCR registries; 0 jobs created; 3 obsolete PostgreSQL secret-access bindings removed as planned |
| Artifact Registry mirror | backend and Cloud SQL proxy source manifests retained their reviewed sha256 digests |
| Corrected operator-job apply | 3 jobs added, 0 changed, 0 destroyed; wizard stopped before execution on a post-apply `gcloud` JSON selector defect |
| First privilege-bootstrap run | reviewed grants installed; unsupported delete flag stopped before job execution; Data API disabled and temporary owner user removed |
| Cloud SQL live readback | `RUNNABLE`; PostgreSQL 17; private IP only; `ENCRYPTED_ONLY`; IAM auth on |
| Backup/storage live readback | 10 GiB SSD; auto-grow limit 20 GiB; 7 backups; 3-day transaction logs |
| Artifact Registry live readback | Docker standard repository with immutable tags |
| WIF live readback | Staging and production providers `ACTIVE`; immutable IDs/branch/environment enforced |
| GitHub environments | Staging and production configured with sole reviewer and exact `main` policy |
| Identity smoke runs | Initial staging `42903648350` failed closed on the legacy subject; after remediation and required review, replacement staging `42906846762` and production `42903653548` passed the short-lived exchange and read-only project check |

The first shared apply created every resource except the budget. The initial budget input duplicated
the `billingAccounts/` prefix, then local ADC lacked an explicit quota-project override. The durable
fix accepts a bare billing account ID, validates its shape, and configures every Google provider with
`billing_project = var.project_id` and `user_project_override = true`. Replanning showed one budget
addition and zero changes/destroys; the corrected apply and final drift check passed.

The repository was created after GitHub's immutable-subject cutoff, so its OIDC token uses
`repo:OWNER@OWNER-ID/REPO@REPO-ID:environment:ENVIRONMENT`. The first approved staging smoke
correctly failed at the GCP attribute condition because the initial provider expected the legacy
name-only subject. The reviewed remediation retained the independent repository ID, owner ID,
branch, and environment restrictions while changing only the staging and production subject
conditions in place. It destroyed nothing, its post-apply plan returned `No changes`, and the
replacement staging and production smokes passed after required review. Each returned project
`comfforts-369117` and removed its temporary credential file during job cleanup.

The regional gcloud secret-version listing command incorrectly routed the regional resource to the
global endpoint. This slice did not create or supply a version, the Terraform configuration contains
no secret-version/payload resource, and no secret value appears in its plans or evidence. Cloud Run
also does not natively inject regional Secret Manager versions. The Cloud SQL operator jobs require
no database secret because they use automatic IAM authentication; the later application/Qdrant
workload must select and qualify a regional-secret access pattern before payload entry.

## Security and privacy impact

The foundation replaces long-lived GitHub credentials with environment-specific short-lived
federation, pins trust to immutable GitHub IDs, and separates staging/production state and delivery
identities. Cloud SQL has no public IPv4 address, secrets are metadata-only, service identities are
least privilege, and durable resources carry deletion guards. Terraform state and secret values are
not committed. The operator wizard made approval boundaries and human-only secret entry explicit;
it did not capture credentials.

This work does not change application authorization or provider rights. Viewer live-provider access
remains denied by the existing identity/provider policy, deployed response caching remains disabled,
and the Qdrant Free cluster remains a separate shared-knowledge exception pending slice 6 transfer
qualification.

## Stop gate and remaining evidence

- The corrected single-registry plan added the three private operator jobs. A post-apply JSON
  selector defect was corrected. The next run installed the reviewed grants but stopped before
  migration, qualification, retention, backup restore, or PITR when owner cleanup supplied an
  unsupported delete flag. Data API access is disabled, the temporary owner user is absent, and the
  cleanup fix must merge before the wizard resumes from a clean `main`.
- Slice 3 remains short of its real-service gate: migrations, retention, restart behavior,
  backup/restore, PITR, and recovery must run from an authorized VPC-connected execution path.
- No workload or external edge exists yet, so direct-workload bypass, IAP, TLS, and URL-map controls
  are not yet testable and are not claimed operational.
- Collection transfer/rollback, staging workload deployment, DNS/IAP cutover, integrated capacity/
  cost/observability checks, application/infrastructure rollback, and final EVAL-20 remain pending.
- Proposed ADR-030 remains Proposed until the complete M11 threat and release qualification passes.

## Artifact paths

- `contracts/deployment/infrastructure-policy.v1.json`
- `contracts/deployment/delivery-policy.v1.json`
- `infrastructure/terraform/`
- `infrastructure/terraform/scripts/bootstrap-staging.sh`
- `infrastructure/terraform/scripts/qualify-cloud-sql-recovery.sh`
- `.github/workflows/terraform.yml`
- `backend/tests/test_staging_infrastructure.py`
- `backend/artifacts/release/deployment/staging-foundation.v1.json`
- `backend/artifacts/release/deployment/delivery-controls.v1.json`
