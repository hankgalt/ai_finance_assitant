# Finance Assistant GCP infrastructure

This capability-owned Terraform implements the M11 staging foundation selected by proposed
ADR-030. It contains no secret payloads, service-account keys, Terraform state, or workload
deployment. The authoritative machine policy is
`contracts/deployment/infrastructure-policy.v1.json`.

The bootstrap, shared, and staging roots were provisioned on 2026-11-10 and their final plans were
drift-free. The application workload and external edge remain unprovisioned. See
`docs/M11_staging_infrastructure_report.md` for evidence and stop gates.

Apply the roots in this order:

1. `bootstrap/` — import the operator-created bootstrap bucket and create separate staging and
   production state buckets.
2. `shared/` — enable approved APIs, create Artifact Registry, the USD 100 alert-only budget, and
   environment-bound GitHub Workload Identity Federation identities. Trust requires GitHub's
   immutable `OWNER@OWNER-ID/REPO@REPO-ID` subject plus independent numeric repository, owner,
   branch, and protected-environment checks.
3. `environments/staging/` — create the isolated staging VPC, private Cloud SQL instance, workload
   identities, and regional secret metadata.

Use `scripts/bootstrap-staging.sh` for the reviewed operator path. The script never accepts a
service-account key or secret payload. Terraform manages regional secret containers only; payloads
are entered separately through Secret Manager when their owning deployment slice is ready.

`terraform plan` is credentialed through short-lived GitHub OIDC only after the local bootstrap has
created WIF and the protected GitHub environment. No workflow in this slice performs
`terraform apply`.
