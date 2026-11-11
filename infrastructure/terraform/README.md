# Finance Assistant GCP infrastructure

This capability-owned Terraform implements the M11 staging foundation selected by proposed
ADR-030. It contains no secret payloads, service-account keys, or Terraform state. It now defines
three private, non-HTTP Cloud Run operator jobs for Cloud SQL migration, qualification, and
retention; it does not define or deploy the browser-facing application workload. The authoritative
machine policy is
`contracts/deployment/infrastructure-policy.v1.json`.

The bootstrap, shared, and staging roots were provisioned on 2026-11-10 and their final plans were
drift-free. The operator-job expansion is defined but has not been applied or live-qualified. The
application workload and external edge remain unprovisioned. See
`docs/M11_staging_infrastructure_report.md` for evidence and stop gates.

Apply the roots in this order:

1. `bootstrap/` — import the operator-created bootstrap bucket and create separate staging and
   production state buckets.
2. `shared/` — enable approved APIs, create Artifact Registry, the USD 100 alert-only budget, and
   environment-bound GitHub Workload Identity Federation identities. Trust requires GitHub's
   immutable `OWNER@OWNER-ID/REPO@REPO-ID` subject plus independent numeric repository, owner,
   branch, and protected-environment checks.
3. `environments/staging/` — create the isolated staging VPC, private Cloud SQL instance, workload
   identities, regional secret metadata, and digest-pinned managed-state operator jobs.

Use `scripts/bootstrap-staging.sh` for the reviewed operator path. The script never accepts a
service-account key or secret payload. Terraform manages regional secret containers only; payloads
are entered separately through Secret Manager when their owning deployment slice is ready.

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

After this change is merged and the new backend digest is available, run
`scripts/qualify-cloud-sql-recovery.sh` from a clean `main` checkout. The staged wizard shows every
plan and destructive target, removes temporary owner database elevation, validates one backup
restore and one point-in-time clone with synthetic data, deletes both temporary instances, requires
a drift-free final plan, and writes the recovery evidence artifact. Temporary Cloud SQL Data API
access is disabled together with owner elevation on the success and interruption paths. Do not run it from an
unreviewed branch or with a tag-only image reference.
