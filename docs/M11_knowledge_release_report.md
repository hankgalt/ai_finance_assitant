# M11 shared-knowledge release implementation report

Status: repository implementation qualified; live collection transfer pending | 2026-11-11

## Scope and traceability

This slice advances M11 and PR-008/PR-017 under ADR-019, ADR-029, and proposed ADR-030. It adds
partial EVAL-07, EVAL-08, and EVAL-20 evidence for transferring the already-qualified Finance and
Tax collections to the selected Qdrant Cloud cluster. It does not activate a live provider, change
an Application Principal entitlement, or claim that the remote collections have been transferred.

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
- The release revalidates exact manifests, point counts, and vector/index compatibility. It runs
  the fixed Finance/Tax qrels through the read-only runtime key before activating either current
  alias, then points each alias to its immediate rollback collection and restores the current
  collection.
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

## Verification and remaining live gate

The deterministic suite covers missing and existing target collections, conflict refusal,
snapshot cleanup, fixed-qrels qualification, activation/rollback/restoration, runtime write denial,
separate secret wiring, provider-boundary enforcement, and secret-free operator behavior. Live
execution remains pending because the demo runtime is intentionally absent.

Repository verification completed with these exact results:

- `cd backend && .venv/bin/python -m pytest -q` — 428 passed, 8 skipped, 4 deselected.
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

No cloud resource, Qdrant collection, secret value, DNS record, or provider setting was mutated by
this repository implementation and verification run.

After merge, the owner must:

1. recreate the demo runtime with a new Qdrant read-only runtime key;
2. ensure the local Qdrant volume contains all four contracted collections;
3. run `make knowledge-release-staging` and create the prompted seven-day manage/write release key;
4. commit the resulting revision-scoped qualified JSON evidence under
   `backend/artifacts/knowledge/deployment/`; and
5. run the Terraform plan/readiness checks before the IAP edge slice.

Until that live record has `status: qualified`, remote collection readiness and authenticated
application readiness remain pending. The focused reusable runtime-key rotation procedure is a
separate approved change immediately after this slice and before the edge/IAP slice.
