# Deployment release evidence

- `delivery-controls.v1.json` records the locally qualified repository-side delivery controls and
  the external GitHub/GCP activation gates that remain pending.
- `cloud-sql-recovery.v1.json` is reserved for the live synthetic Cloud SQL migration, retention,
  backup-restore, and point-in-time-recovery result. It is created only after the complete wizard
  passes; its governing interface is `contracts/deployment/recovery-policy.v1.json`.
- `application-workloads.v1.json` records the separate-state frontend/backend Terraform, migration-
  first lifecycle, secret-access decision, and the live staging/no-bypass evidence still pending.

Published image digests, attestations, Terraform plans, staging results, deployment records, and
rollback evidence belong here when their owning later slices run. Runtime credentials, Terraform
state, and secret values are never committed.
