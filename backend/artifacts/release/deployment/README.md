# Deployment release evidence

- `delivery-controls.v1.json` records the locally qualified repository-side delivery controls and
  the external GitHub/GCP activation gates that remain pending.
- `cloud-sql-recovery.v1.json` is reserved for the live synthetic Cloud SQL migration, retention,
  backup-restore, and point-in-time-recovery result. It is created only after the complete wizard
  passes; its governing interface is `contracts/deployment/recovery-policy.v1.json`.
- `application-workloads.v1.json` records the separate-state frontend/backend Terraform, migration-
  first lifecycle, secret-access decision, and qualified live staging/no-bypass boundary.
- `demo-runtime-lifecycle.v1.json` records the reviewed disposable runtime create/destroy/recreate
  result.
- `private-edge-<revision>.v1.json` records the qualified HTTPS, DNS, IAP, owner admission, route,
  and direct-origin boundary for that merged revision.
- `private-demo-<revision>.v1.json` is created only after the assembled owner-only
  `credential_free` browser/API/SSE qualification passes for that merged revision. Its governing
  interface is `contracts/deployment/private-demo-qualification.v1.json`.

Published image digests, attestations, Terraform plans, staging results, deployment records, and
rollback evidence belong here when their owning capability runs. Runtime credentials, browser
authentication state, Terraform state, and secret values are never committed.
