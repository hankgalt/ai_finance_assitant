# M11 shared-knowledge release implementation report

Status: live staging shared-knowledge release qualified; edge integration pending | 2026-11-12

## Scope and traceability

This slice advances M11 and PR-008/PR-017 under ADR-019, ADR-029, and proposed ADR-030. It records
EVAL-07/EVAL-08 deployed-retrieval evidence and the shared-knowledge portion of EVAL-20 for the
selected Qdrant Cloud cluster. It does not activate a live provider, change an Application Principal
entitlement, or claim that the load-balancer/IAP edge and deployed product journeys are qualified.

## Implemented interfaces

- `contracts/deployment/knowledge-release.v1.json` pins the Qdrant source/target versions, the
  current and immediate-rollback collection names, committed manifest/qrels/evaluation inputs,
  exact expected point counts, separate credential purposes, and the credential-free provider
  boundary.
- `ai_finance_assistant.knowledge.release` validates both Qdrant versions and all four local
  collections, creates execution-scoped collection snapshots only for missing remote collections,
  uploads with `priority=snapshot`, and fails closed instead of overwriting a conflicting remote
  collection. Snapshot files are deleted with their temporary directory and never become release
  artifacts.
- The release revalidates manifests, point counts, and vector/index compatibility. Every manifest
  field must match except the Git-confirmed `artifacts/m1/<same filename>` to capability-owned
  evaluation-artifact relocation; accepting that relocation is recorded in the release evidence.
  It runs the fixed Finance/Tax qrels through the read-only runtime key before activating either
  current alias, then points each alias to its immediate rollback collection and restores the
  current collection.
- A cluster-wide read-only runtime key and a short-lived cluster-wide manage/write release key have
  separate Secret Manager resources. Only the runtime service account can access the runtime
  secret. The release key is never injected into Cloud Run; the operator verifies Qdrant rejects it
  after revocation and then destroys its Secret Manager version.
- Runtime-key qualification reads the active aliases and attempts to create a uniquely named probe
  collection. HTTP 403 is required. If an over-privileged key accepts the write, the release key
  removes the probe and the release fails.
- Before any Qdrant write, the operator reads back the deployed backend configuration and requires
  both provider and model modes to be `credential_free`. Any OpenAI, Alpha Vantage, Massive, or
  Tavily credential/terms environment name fails the release; the reduced non-secret result is
  included in the release evidence.
- `make knowledge-release-staging` invokes the repeatable operator wizard. Secret payloads are
  entered only in Secret Manager and reach the Python process through file descriptors, never
  command arguments, GitHub variables, Terraform inputs, committed files, or wizard prompts.
- `knowledge.cli` now supports the same file-descriptor API-key input for explicit remote validate,
  activation, or rollback operations.

The deployment remains `credential_free` for market/news providers and models. Live OpenAI,
market, or news credentials and activation flags are neither provisioned nor accepted by this
workflow. Such activation remains a separate owner/provider-rights decision.

## Security and privacy impact

The target Qdrant cluster contains only shared immutable education knowledge and no
Application-Principal-owned data. Terraform owns secret containers and runtime accessor IAM but no
secret versions or values. The release evidence contains collection identifiers, snapshot
checksums/sizes, evaluation results, alias transitions, bounded HTTP status codes, and cleanup
status; it explicitly records that no secret payload was captured.

The runtime key is limited to reads, the elevated release key is time-bounded and removed after one
qualification, and an existing collection with nonmatching metadata blocks release rather than
being deleted or overwritten. The workflow requires a clean merged `main`, the approved owner GCP
identity, the exact project, and the already-qualified persistent local Qdrant collections.

## Verification and live qualification

The deterministic suite covers missing and existing target collections, the single approved
evaluation-artifact relocation, refusal of arbitrary paths or substantive conflicts, snapshot
cleanup, fixed-qrels qualification, activation/rollback/restoration, runtime write denial, separate
secret wiring, provider-boundary enforcement, and secret-free operator behavior.

Repository verification completed with these exact results:

- `cd backend && .venv/bin/python -m pytest -q` — 431 passed, 8 skipped, 4 deselected.
- `cd backend && .venv/bin/python -m ruff format --check .` — 175 files already formatted.
- `cd backend && .venv/bin/python -m ruff check .` — passed.
- `cd backend && .venv/bin/python -m mypy src tests` — no issues in 163 source files.
- `terraform fmt -check -recursive infrastructure/terraform` — passed.
- `terraform -chdir=infrastructure/terraform/environments/staging validate` and the equivalent
  `staging-workloads` validation — both configurations valid.
- `bash -n` for the staging bootstrap, runtime up/down, and shared-knowledge release scripts;
  machine-contract `jq` parsing; and `git diff --check` — passed.
- `shellcheck` — skipped because it is not installed locally; Bash syntax and deterministic script
  contract tests passed.

The live operator completed on revision `a737f8e9e935f8afc05e16fc7148e3a185b32086` and wrote
`backend/artifacts/knowledge/deployment/staging-release-a737f8e9e935f8afc05e16fc7148e3a185b32086.json`.
Its contract checksum matches the committed release contract and its status is `qualified`:

- all four current/rollback snapshots uploaded and revalidated at 106, 30, 6,295, and 4,735 points;
- 17 Finance and 32 Tax fixed qrels passed through the read-only runtime credential;
- both current aliases activated, switched to the immediate rollback collection, and restored;
- runtime collection reads succeeded and the mutation probe returned HTTP 403;
- deployed provider and model modes were `credential_free`, with no forbidden live-provider
  credential or approval environment;
- the temporary release key was rejected by Qdrant with HTTP 403 after revocation, and its Secret
  Manager version was destroyed; and
- the evidence records no secret payload.

Read-only GCP reconciliation on 2026-11-12 found the `db-g1-small` Cloud SQL instance `RUNNABLE`,
both application services `Ready`, disabled default URLs, internal/load-balancer-only ingress, and
no anonymous invoker. This current runtime remains disposable and has no external IAP edge.

The separately reviewable runtime-key rotation procedure is now implemented and locally qualified;
its live run and secret-free evidence remain pending. Later gates are Terraform plan/readiness
confirmation, load balancing/HTTPS/IAP/DNS, and the critical deployed product and identity-
isolation journeys. Backup/PITR and production hardening remain deferred.
