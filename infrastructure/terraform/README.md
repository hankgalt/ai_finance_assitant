# Finance Assistant GCP infrastructure

This capability-owned Terraform implements the M11 staging foundation selected by proposed
ADR-030. It contains no secret payloads, service-account keys, or committed Terraform state. It
defines an on-demand, disposable `db-g1-small` demo runtime plus three private, non-HTTP Cloud Run
operator jobs for Cloud SQL migration, qualification, and retention; it does not yet define or
deploy the browser-facing application workload. The authoritative machine policy is
`contracts/deployment/infrastructure-policy.v1.json`.

The bootstrap, shared, and historical `db-f1-micro` staging roots were provisioned on 2026-11-10.
The corrected `db-g1-small` lifecycle is defined but has not been applied. The application workload
and external edge remain unprovisioned. See `docs/M11_staging_infrastructure_report.md` for live
evidence and `backend/artifacts/release/deployment/demo-runtime-lifecycle.v1.json` for the
defined-not-applied lifecycle record.

Apply the roots in this order:

1. `bootstrap/` — import the operator-created bootstrap bucket and create separate staging and
   production state buckets.
2. `shared/` — enable approved APIs, create Artifact Registry, the USD 100 alert-only budget, and
   environment-bound GitHub Workload Identity Federation identities. Trust requires GitHub's
   immutable `OWNER@OWNER-ID/REPO@REPO-ID` subject plus independent numeric repository, owner,
   branch, and protected-environment checks.
3. `environments/staging/` — create the disposable isolated staging VPC, private Cloud SQL instance,
   workload identities, regional secret metadata, and digest-pinned managed-state operator jobs.

Use the reviewed lifecycle entry points from a clean merged `main` checkout:

```bash
export GCP_BACKEND_IMAGE='us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/finance-assistant-backend@sha256:<digest>'
infrastructure/terraform/scripts/demo-runtime-up.sh
infrastructure/terraform/scripts/demo-runtime-down.sh
```

The up wizard checks the exact owner identity and pinned Artifact Registry image, refreshes the
persistent bootstrap/shared foundation, and applies only a displayed saved staging plan. It creates
an empty `db-g1-small` instance with no automated backups, PITR, final backup, retained backup, or
deletion protection. Provisioning does not bootstrap PostgreSQL grants or run schema migration;
those remain part of the next staging-workload step.

The down wizard first applies a displayed non-destructive transition plan that removes any live
deletion guards while preserving the observed database tier. It then displays a separate
staging-only destroy plan and requires the exact phrase `DESTROY EMPTY-DEMO-RUNTIME` before applying
that saved plan. The staging VPC, Cloud SQL data, operator jobs, service identities, and regional
secret containers/versions are deleted. Protected Terraform state, Artifact Registry, WIF, the
budget, shared non-secret configuration, and the separately managed Qdrant cluster remain. The
script never accepts a service-account key or secret payload.

`terraform plan` is credentialed through short-lived GitHub OIDC only after the local bootstrap has
created WIF and the protected GitHub environment. No workflow in this slice performs
`terraform apply`. The `staging` GitHub environment must provide `GCP_BACKEND_IMAGE` as the full
merged-main backend image reference pinned by `@sha256:` in
`us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/` before the expanded staging plan runs.

Cloud Run rejected the first operator-job apply because the multi-container jobs combined a GHCR
backend with a GCR proxy. Both reviewed manifests are now mirrored without digest changes into the
existing immutable `aifa-containers` Artifact Registry, and Terraform rejects another mixed-registry
input before apply. For a later backend revision, preserve the reviewed manifest with:

```bash
gcloud auth configure-docker us-west1-docker.pkg.dev --quiet
docker buildx imagetools create --prefer-index=false \
  --tag us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/finance-assistant-backend:<git-sha> \
  ghcr.io/hankgalt/ai-finance-assitant-backend@sha256:<reviewed-digest>
docker buildx imagetools inspect \
  us-west1-docker.pkg.dev/comfforts-369117/aifa-containers/finance-assistant-backend:<git-sha>
```

Use the inspected Artifact Registry `name@sha256:digest` as `GCP_BACKEND_IMAGE`. The pinned proxy
mirror is managed separately and must retain the digest recorded in the staging Terraform root.

The Cloud SQL jobs use Direct VPC egress, private IP, and Cloud SQL Auth Proxy automatic IAM
authentication. Their passwordless DSN is configuration, not a credential, and is not stored in
Secret Manager. Cloud Run does not natively inject regional Secret Manager secrets, so the later
application/Qdrant deployment must select and qualify a regional-secret access pattern; it must not
silently replace the approved regional topology with global secrets.

`scripts/qualify-cloud-sql-recovery.sh` is retained as deferred post-MVP hardening evidence. Do not
run it as part of the private-demo create/destroy lifecycle. It does not replace the explicit
destroy confirmation and its incomplete backup/PITR qualification is not an MVP gate.
