# M11 delivery report — Staging infrastructure foundation

Status: Staging and production keyless identity qualified; managed-state migration, synthetic
preparation, and retention cleanup passed; the billable on-demand runtime is absent, the approved
private-networking foundation remains, and the workload create/no-bypass/destroy lifecycle has been
exercised; live knowledge and edge qualification remain pending and real-service recovery deferred |
2026-11-11

## Scope and decisions

This M11 slice advances PR-017 and QR-003, QR-005–QR-007, QR-010–QR-011, and QR-014–QR-015
under accepted ADR-019/ADR-029 and proposed ADR-030. It implements the approved same-project
staging foundation in GCP project `comfforts-369117`, region `us-west1`. It does not deploy a Cloud
Run workload, configure load balancing/IAP/DNS, transfer Qdrant collections, enter secret payloads,
or broaden any provider entitlement.

The corrected MVP target is an on-demand `db-g1-small` demo runtime with an empty store on every
creation and explicit data loss on destroy. The provisioned `db-f1-micro`, seven-backup, and
three-day-PITR configuration below remains truthful evidence of the earlier foundation apply, but it
is not the target configuration and its recovery qualification no longer blocks the private-demo
MVP.

The repository implements reviewed `demo-runtime-up.sh` and `demo-runtime-down.sh` entry points.
The down path preserves the current database tier while first removing historical deletion guards,
then applies only a separately reviewed staging destroy plan after the exact
`DESTROY EMPTY-DEMO-RUNTIME` confirmation. The first down run deleted the application database but
failed to delete its IAM users because Terraform scheduled those operations concurrently. The
merged database-before-user dependency corrected that ordering, and the reviewed retry removed the
remaining Cloud SQL instance, users, jobs, service identities, subnetwork, and secret containers.
Google retains deleted Cloud SQL producer networking for up to four days, so the VPC, allocated
internal range, and Service Networking connection remain as the approved foundation. The down entry
point now accepts only that exact residue after an independent empty Cloud SQL inventory; any other
remainder fails closed. The corrected path subsequently executed against staging, verified the
exact residue, and exited successfully; its empty-inventory filter and expected-residue messaging
are now also corrected.

The machine-readable desired-state boundary is
[`contracts/deployment/infrastructure-policy.v1.json`](../contracts/deployment/infrastructure-policy.v1.json).
The historical foundation qualification record is
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
- The billable staging runtime is absent. Cloud SQL inventory is empty, and its application
  database, IAM users, Cloud Run jobs, service accounts/bindings, subnetwork, and regional Secret
  Manager containers/versions have been removed. Terraform owns no secret payload.
- Terraform state retains exactly the `aifa-staging` VPC, its allocated private-service internal
  range, and Service Networking connection. They have [no hourly connection or internal-address
  charge](https://cloud.google.com/vpc/network-pricing) and are reused by the next demo runtime.
- Capability-oriented Terraform modules, a non-secret operator wizard, a plan-only GitHub workflow,
  policy tests, and release evidence are committed under their infrastructure, delivery, contract,
  test, and release owners.
- Three non-HTTP Cloud Run jobs were provisioned for migration, synthetic qualification, and
  retention and passed migration, synthetic preparation, retention, and source cleanup. The partial
  teardown removed those jobs. Restored-target validation and the complete recovery procedure did
  not pass and are not represented as recovery-qualified.
- Before teardown, the selected jobs no longer used DSN secret payloads, so the expanded plan
  removed the three PostgreSQL secret-access IAM bindings. The regional secret containers remained
  empty historical metadata until the partial teardown removed them.
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
| First on-demand down run | Transition apply disabled legacy guards; destroy removed the application database and other staging resources, then IAM-user deletion failed on database privilege dependencies |
| Reviewed down retry | Database-before-user ordering removed the remaining Cloud SQL instance, IAM users, jobs, service identities, subnetwork, and secret containers; Service Networking deletion returned the documented producer-recovery-window error |
| Live residual inventory | Cloud SQL inventory empty; Terraform state contains exactly the VPC, allocated private-service range, and Service Networking connection |
| Networking-acceptance static qualification | Simulated provider-delay regression passes only for the exact three-resource network residue plus independently absent Cloud SQL and fails on any unexpected fourth resource; Terraform format/validate and shell syntax pass |
| First operator-job apply | failed closed on mixed GHCR/GCR registries; 0 jobs created; 3 obsolete PostgreSQL secret-access bindings removed as planned |
| Artifact Registry mirror | backend and Cloud SQL proxy source manifests retained their reviewed sha256 digests |
| Corrected operator-job apply | 3 jobs added, 0 changed, 0 destroyed; wizard stopped before execution on a post-apply `gcloud` JSON selector defect |
| First privilege-bootstrap run | reviewed grants installed; unsupported delete flag stopped before job execution; Data API disabled and temporary owner user removed |
| First migration/recovery run | migration `aifa-staging-migrate-xrbw9` and prepare `aifa-staging-qualify-gpp85` passed; numeric-ID restore rejected configuration overrides before creating a temporary instance; PITR and retention did not run |
| Second migration/recovery run | migration `aifa-staging-migrate-cldkf` and prepare `aifa-staging-qualify-nxtgm` passed; backup creation succeeded, but the named-backup response exposed no `id` field and restore was not attempted; no temporary instance was created |
| Third migration/recovery run | migration `aifa-staging-migrate-wvsz2`, prepare `aifa-staging-qualify-mw4fs`, and backup restore passed; the PITR clone continued server-side after the synchronous `gcloud` client wait expired, so recovered-target validation and cleanup did not run |
| Cloud SQL live readback after reviewed retry | No instances |
| Retained private networking | `aifa-staging` VPC, `aifa-staging-private-services` allocated range, and `servicenetworking-googleapis-com` connection |
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

## Remaining MVP gates and deferred hardening

- The corrected single-registry plan added the three private operator jobs. A post-apply JSON
  selector defect was corrected. The next run installed the reviewed grants but stopped before
  job execution when owner cleanup supplied an unsupported delete flag. Data API access is disabled
  and the temporary owner user is absent. The subsequent run passed migration and synthetic
  preparation but stopped before creating either temporary recovery instance because `gcloud`
  permits new-instance overrides only with the fully qualified backup name, not the numeric backup
  run ID. No temporary instance was created, and the exact on-demand backup was deleted after
  explicit operator confirmation. The corrected wizard resolves and validates the unique backup
  name before restore.
- The subsequent run passed migration and preparation and created a successful on-demand backup,
  but stopped before restore because the named-backup create response had no `id` field. The exact
  backup was deleted after explicit operator confirmation; no temporary instance exists. The
  corrected wizard now derives the evidence-only numeric run ID from the resolved backup resource's
  `backupRun` metadata.
- The following run completed backup restore and started PITR operation
  `68521fda-e842-439a-ad92-72a600000033`, but the client wait expired while Cloud SQL still reported
  `RUNNING`. The wizard exited before validation and cleanup. Recovery validation was deprioritized;
  after the non-cancellable clone reached `DONE`, both exact temporary instances and the exact
  qualification backup were deleted, while the protected source and durable foundation remained
  intact. Retention `aifa-staging-retention-x8gwt` and verification/cleanup
  `aifa-staging-qualify-wmpdz` then passed and removed all namespaced synthetic source state. The
  corrected wizard uses asynchronous operations plus a shared four-hour polling deadline, reapplies
  deletion protection and backup controls after restore, and disables PITR before disabling clone
  backups.
- Recovered-target validation, backup/restore, PITR, measured RPO/RTO, and recovery final-drift
  evidence remain incomplete and are explicitly deferred post-MVP hardening.
- The staging workload and external-origin denial were exercised before the reviewed teardown; no
  external edge exists yet, so IAP, TLS, and URL-map controls remain unqualified.
- The billable runtime is absent after the reviewed `db-g1-small` create/deploy/destroy lifecycle;
  only the approved three-resource networking foundation remains.
- Collection transfer/readiness, DNS/TLS/IAP cutover, critical feature-parity smoke, and the
  private-demo portion of EVAL-20 remain pending MVP gates. The repository now defines the exact
  snapshot transfer, fixed-qrels, alias rollback, runtime read-only, and release-key cleanup path,
  but live Qdrant execution remains pending. Collection rollback depth beyond that immediate proof,
  integrated capacity/soak/SLO/alerting, incident rehearsal, and application/infrastructure rollback
  remain post-MVP hardening.
- Proposed ADR-030 remains Proposed until the corrected private-demo M11 threat and release
  qualification passes; that acceptance will not imply production readiness.

## Artifact paths

- `contracts/deployment/infrastructure-policy.v1.json`
- `contracts/deployment/delivery-policy.v1.json`
- `infrastructure/terraform/`
- `infrastructure/terraform/scripts/bootstrap-staging.sh`
- `infrastructure/terraform/scripts/demo-runtime-up.sh`
- `infrastructure/terraform/scripts/demo-runtime-down.sh`
- `infrastructure/terraform/scripts/qualify-cloud-sql-recovery.sh`
- `.github/workflows/terraform.yml`
- `backend/tests/test_staging_infrastructure.py`
- `backend/artifacts/release/deployment/staging-foundation.v1.json`
- `backend/artifacts/release/deployment/demo-runtime-lifecycle.v1.json`
- `backend/artifacts/release/deployment/delivery-controls.v1.json`
