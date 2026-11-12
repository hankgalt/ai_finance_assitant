# M11 Qdrant runtime-key rotation implementation report

Status: procedure implemented and locally qualified; live staging rotation pending | 2026-11-12

## Scope and traceability

This bounded M11 slice advances PR-008/PR-017 and QR-005/QR-010/QR-015 under ADR-019,
ADR-029, and proposed ADR-030. It implements the separately reviewable runtime-key rotation
procedure required before edge work and adds deterministic EVAL-20 seams. It does not rotate the
live credential by itself, enable a provider, modify shared knowledge, replay Cloud SQL
provisioning, or claim that the IAP edge and deployed product journeys are qualified.

## Implemented procedure

- `contracts/deployment/runtime-key-rotation.v1.json` pins the one runtime secret, read-only Qdrant
  permission, active Finance/Tax aliases and collections, the `staging-workloads` state, the single
  permitted backend resource update, private-origin controls, credential-free provider posture,
  retirement order, and secret-free evidence shape.
- `ai_finance_assistant.knowledge.runtime_key_rotation` validates the replacement key against the
  Qdrant version, contract-compatible committed collection manifests (including the already
  approved artifact-path relocation), exact point counts, active aliases, and vector compatibility.
  Its permission probe first proves a unique collection name is absent, then issues
  a DELETE for that absent name and requires HTTP 403. It never creates probe data; a writable key
  produces a non-403 response and fails qualification.
- Terraform plan validation accepts exactly one in-place update to
  `module.application_workloads.google_cloud_run_v2_service.backend`. After normalizing the new
  numeric secret version back to the old value, the complete before/after resources must be equal.
  An image, environment, ingress, identity, or other workload change therefore fails before apply.
- `make rotate-qdrant-runtime-key-staging` runs the seven-stage operator wizard from clean merged
  `main`. The human creates the read-only key in Qdrant and adds it directly to the existing Secret
  Manager resource. Neither the prompt, shell variables, GitHub, Terraform, nor the repository
  receives the payload.
- The wizard saves and displays the focused plan, applies only after confirmation, and reads back
  the exact secret version, immutable backend image, Ready condition, disabled default URL,
  internal/load-balancer ingress, absent anonymous IAM, and credential-free provider/model modes.
  The old Qdrant key and Secret Manager version remain active until those checks pass. A failed
  readback offers a separately planned backend-only rollback to the old numeric version.
- Only after verified cutover does the wizard update and read back the non-secret staging
  `GCP_QDRANT_SECRET_VERSION` variable. It then requires the operator to revoke only the old Qdrant
  key, proves that old payload receives HTTP 401/403, and asks separately before permanently
  destroying the old Secret Manager version.
- The procedure can resume from its evidence state after an interruption. Each successful rotation
  writes a unique
  `staging-runtime-key-rotation-<revision>-v<old>-to-v<new>.json` record, allowing repeated rotations
  from the same revision without overwriting earlier evidence.

## Security and privacy impact

The replacement credential is cluster-wide read-only and can access only the Qdrant cluster's
shared education knowledge; the cluster contract forbids Application-Principal-owned data. Secret
payloads move only from Secret Manager file descriptors into the bounded qualifier process. The
evidence records version numbers, HTTP status codes, collection identifiers, deployment readback,
and cleanup state, never a credential value.

The old key remains a working rollback credential through plan, apply, and verification. It is
revoked before its stored version is destroyed. The procedure does not widen provider rights:
OpenAI, market, and news secrets or approval flags fail deployed readback, and both provider and
model modes must remain `credential_free`.

## Qualification and remaining gate

Deterministic qualification covers collection/alias checks, the non-mutating HTTP 403 probe,
over-privileged-key rejection, secret-version-only Terraform plans, deployed private-origin and
provider readback, anonymous-IAM rejection, contract/script ordering, resume-safe evidence states,
and the capability-owned Make entry point. Local qualification completed with these exact results:

- `cd backend && .venv/bin/python -m pytest -q` — 446 passed, 8 skipped, 4 deselected.
- `cd backend && .venv/bin/python -m ruff format --check .` — 178 files already formatted.
- `cd backend && .venv/bin/python -m ruff check .` — passed.
- `cd backend && .venv/bin/python -m mypy src tests` — no issues in 166 source files.
- `terraform fmt -check -recursive infrastructure/terraform` — passed.
- `terraform -chdir=infrastructure/terraform/environments/staging-workloads validate` —
  configuration valid.
- Bash syntax, JSON parsing, executable-bit, and `git diff --check` checks — passed.
- `shellcheck` — skipped because it is not installed locally; Bash syntax and deterministic script
  contract tests passed.

Two restricted-sandbox Terraform attempts were non-qualifying failures: an `init -backend=false`
attempt inherited the existing remote backend metadata and could not resolve Google OAuth, and the
first direct `validate` could not start the local provider process. Re-running the read-only direct
`validate` with the local provider outside that restriction succeeded as recorded above. No plan or
cloud resource was created or changed by these checks.

Live qualification remains intentionally pending because it requires a newly created Qdrant key,
the owner's Secret Manager entry, review of the real saved plan, and explicit revocation/destruction
confirmations. After this change is merged, run `make rotate-qdrant-runtime-key-staging` from clean,
current `main`, complete all seven stages, verify the resulting evidence status is `qualified`, and
commit that secret-free evidence on a separate evidence branch. Only then is the live rotation gate
complete.
