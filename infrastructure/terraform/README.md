# Finance Assistant GCP infrastructure

This capability-owned Terraform implements the M11 staging foundation selected by proposed
ADR-030. It contains no secret payloads, service-account keys, or committed Terraform state. It
defines an on-demand, disposable `db-g1-small` demo runtime, three private non-HTTP Cloud Run
operator jobs, and separate-state private frontend/backend workload definitions. The workloads are
qualified through a reviewed create/deploy/no-direct-origin/destroy cycle and a later recreation;
the current disposable runtime is active for the remaining MVP gates. The repository also defines a
separate-state owner-only HTTPS/IAP edge with an API-only public-base-path rewrite. Its live OAuth,
edge, and DNS resources are provisioned, while final browser qualification remains operator-reviewed
work. The authoritative machine policy is
`contracts/deployment/infrastructure-policy.v1.json`.

The bootstrap, shared, and historical `db-f1-micro` staging roots were provisioned on 2026-11-10.
The corrected `db-g1-small` lifecycle and application workloads were applied, verified, destroyed,
and recreated for the qualified shared-knowledge release. The live edge resources are provisioned,
but final browser qualification remains pending until the corrected frontend redirect is deployed
and verified. See
`docs/M11_staging_infrastructure_report.md` for live
evidence and `backend/artifacts/release/deployment/demo-runtime-lifecycle.v1.json` for the
qualified lifecycle record.

Apply the roots in this order:

1. `bootstrap/` — import the operator-created bootstrap bucket and create separate staging and
   production state buckets.
2. `shared/` — enable approved APIs, create Artifact Registry, the USD 100 alert-only budget, and
   environment-bound GitHub Workload Identity Federation identities. Trust requires GitHub's
   immutable `OWNER@OWNER-ID/REPO@REPO-ID` subject plus independent numeric repository, owner,
   branch, and protected-environment checks.
3. `environments/staging/` — create the disposable isolated staging VPC, private Cloud SQL instance,
   workload identities, separate runtime/release Qdrant secret metadata with a single `us-west1`
   replica, and digest-pinned managed-state operator jobs.
4. `environments/staging-workloads/` — after the grants and migration job pass, create the private,
   digest-pinned frontend and backend Cloud Run services in the separate `workloads` state prefix.
5. `environments/staging-edge/` — after the workloads are private and ready, create the global
   external HTTPS load balancer, managed certificate, exact base-path URL map, IAP policies, and
   IAP-only Cloud Run invoker bindings in the separate `edge` state prefix. Apply this root before
   changing DNS.

Use the reviewed lifecycle entry points from a clean merged `main` checkout:

```bash
make mirror-merged-main-images
make set-deployment-image-variables
export GCP_BACKEND_IMAGE="$(gh variable get GCP_BACKEND_IMAGE --repo hankgalt/ai_finance_assitant --env staging)"
export GCP_FRONTEND_IMAGE="$(gh variable get GCP_FRONTEND_IMAGE --repo hankgalt/ai_finance_assitant --env staging)"
infrastructure/terraform/scripts/demo-runtime-up.sh
make knowledge-release-staging
make rotate-qdrant-runtime-key-staging
make private-edge-up
make private-edge-down
infrastructure/terraform/scripts/demo-runtime-down.sh
```

`make private-edge-up` requires the disposable runtime to be ready. It refreshes the shared OAuth
secret metadata without a payload, then pauses for the owner to create the external OAuth client and
enter its secret directly in Secret Manager. The procedure observes only the positive numeric
secret version, applies a displayed saved edge plan before DNS, derives the backend service's
generated IAP audience, and restricts the workload update plan to the backend service. It then sets
the non-secret GitHub client-ID, secret-version, and audience variables, asks the owner to add the
single Squarespace A record, and qualifies TLS, redirects, IAP, owner admission, unmatched-path
denial, direct-origin denial, and drift. After Google reports the managed certificate `ACTIVE`, the
procedure allows a bounded 30-minute serving-propagation window and requires an anonymous IAP
challenge before browser verification. The frontend's canonical trailing-slash redirect remains
relative so the public HTTPS origin is preserved behind the load balancer. The procedure writes
only secret-free revision-scoped evidence.

`make private-edge-down` first requires the owner to remove the Squarespace record, restores the
workload's fail-closed audience, verifies the non-secret GitHub audience variable, and destroys only
the edge state after the exact confirmation phrase. It deliberately retains the shared OAuth secret
container and does not destroy the application runtime. Neither procedure reads, prints, exports,
or stores the OAuth secret payload.

Use `make set-deployment-image-variables DEPLOYMENT_ENVIRONMENT=production` for the only other
accepted GitHub environment.

`mirror-merged-main-images.sh` refuses a dirty checkout, fast-forwards `main`, verifies GitHub and
GCP authentication, and mirrors both merged-main GHCR manifests into Artifact Registry without
changing their digests. An already-correct SHA tag is reported and skipped; a conflicting tag is
rejected rather than overwritten. `set-deployment-image-variables.sh [environment]` accepts only
`staging` or `production` and defaults to `staging`; it resolves those mirrored manifests, writes
both non-secret digest references to that GitHub environment, and requires exact readback.
Repeating either script against identical state
performs no branch switch, pull, Docker-authentication update, manifest copy, or GitHub-variable
write. GitHub environment variables do not enter the calling shell automatically, so the explicit
exports remain required before the lifecycle entry point unless the operator chooses to paste both
references at its prompts.

The up wizard checks the exact owner identity and both pinned Artifact Registry images, refreshes the
persistent bootstrap/shared foundation, and applies only displayed saved plans. It creates an empty
`db-g1-small` instance with no automated backups, PITR, final backup, retained backup, or deletion
protection. The operator then enters the Qdrant key directly in Secret Manager. The wizard observes
only its numeric version, installs reviewed least-privilege PostgreSQL grants through a temporary
Data API path, removes the owner elevation, executes the migration job, deploys the separate-state
workloads, and verifies their digest, readiness, ingress, disabled default URL, and absence of an
anonymous invoker.

After the runtime is ready, `make knowledge-release-staging` transfers only missing approved
Finance/Tax current and rollback snapshots, reruns the fixed qrels remotely, activates the current
aliases, proves rollback/restoration, and requires the runtime key's write attempt to return 403.
The temporary manage/write release key is entered only in its separate Secret Manager resource,
revoked in Qdrant after qualification, and then destroyed in Secret Manager. The generated
revision-scoped evidence contains no key payload.

After a qualified knowledge release, `make rotate-qdrant-runtime-key-staging` performs only the
focused runtime-key change. It creates no Cloud SQL, networking, job, frontend, or knowledge
resource. The wizard qualifies a new read-only key from Secret Manager, requires a saved plan whose
only managed difference is the backend's numeric Qdrant secret version, verifies the private
backend and credential-free provider boundary, then updates the non-secret GitHub version variable.
The old key/version remain available for rollback until cutover passes; only then does the operator
revoke the old Qdrant key and separately confirm destruction of the old Secret Manager version.
The live run writes a unique secret-free evidence record under
`backend/artifacts/knowledge/deployment/`.
Revision `86146b6227285015665b84cbfa3f4ce0395cd618` qualified that live path from secret version 1
to version 2: the new key read the active collections and received HTTP 403 on the non-mutating
write probe, Terraform changed only the backend version reference, private/provider controls
remained intact, the GitHub version selector matched, and the revoked old key plus old stored
version were removed. The evidence is
`backend/artifacts/knowledge/deployment/staging-runtime-key-rotation-86146b6227285015665b84cbfa3f4ce0395cd618-v1-to-v2.json`.

The down wizard first applies a displayed non-destructive transition plan that removes any live
deletion guards while preserving the observed database tier. It then displays separate workload and
staging destroy plans and requires the exact phrase `DESTROY EMPTY-DEMO-RUNTIME`. It destroys the
workload state before the managed-state plan. Cloud SQL data, operator jobs, service identities,
and both Qdrant secrets/versions are deleted. Google may temporarily retain the VPC, allocated
private-service range, and Service Networking connection; the wizard treats this as success only
when those are the exact remaining Terraform resources and Cloud SQL/workload inventories are
empty. Protected Terraform state, Artifact Registry, WIF, the budget, shared non-secret
configuration, and the separately managed Qdrant cluster remain. The script never accepts a
service-account key or secret payload.

`terraform plan` is credentialed through short-lived GitHub OIDC only after the local bootstrap has
created WIF and the protected GitHub environment. No workflow in this slice performs
`terraform apply`. The `staging` GitHub environment must provide `GCP_BACKEND_IMAGE` and
`GCP_FRONTEND_IMAGE` as full merged-main references pinned by `@sha256:` in the approved Artifact
Registry, plus non-secret numeric `GCP_QDRANT_SECRET_VERSION`, before the expanded staging plans run.

Cloud Run rejected the first operator-job apply because the multi-container jobs combined a GHCR
backend with a GCR proxy. Backend and frontend merged-main manifests are now mirrored through the
repeatable script above without digest changes into the existing immutable `aifa-containers`
Artifact Registry, and Terraform rejects another mixed-registry input before apply. The pinned
proxy mirror is managed separately and must retain the digest recorded in the staging Terraform
root.

The Cloud SQL jobs and backend workload use Direct VPC egress, private IP, and Cloud SQL Auth Proxy automatic IAM
authentication. Their passwordless DSN is configuration, not a credential, and is not stored in
Secret Manager. The Qdrant runtime and offline release keys instead use separate standard Secret
Manager resources with user-managed replication restricted to `us-west1`; Cloud Run can access
only the pinned numeric runtime version. Terraform, GitHub, plans, logs, and repository artifacts
never receive either payload.

`scripts/qualify-cloud-sql-recovery.sh` is retained as deferred post-MVP hardening evidence. Do not
run it as part of the private-demo create/destroy lifecycle. It does not replace the explicit
destroy confirmation and its incomplete backup/PITR qualification is not an MVP gate.
