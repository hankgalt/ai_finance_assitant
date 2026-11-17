# App Platform provider-runtime handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, and AP-M5 supplies accepted infrastructure-planning authority and its deterministic
planning gate. No networked Shared Edge, provider runtime, Terraform configuration, cloud resource,
DNS change, credential, deployment, Application Adoption, or Live (`L`) evidence is implemented or
qualified merely because those authorities exist.

Use this handoff only from updated `main` after the AP-M5 pull request has merged. If AP-M5 is not
in `main`, the working tree is not clean, or the requested branch already contains AP-M6 changes,
report that conflict and stop instead of switching, pulling, resetting, committing, or combining
slices without owner direction.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform project root. While colocated, also preserve the
   containing repository's security, source-control, secret-handling, and destructive-action
   guardrails.
2. Inspect the working tree, branch, and relationship to `main`. Preserve unrelated changes and
   report any state that conflicts with the incremental delivery sequence instead of resetting,
   pulling, switching, or committing without owner direction.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md`,
   `contracts/README.md`, and `fixtures/registrations/README.md` completely to load the AP-M3
   through AP-M5 boundaries and the AP-M6 evaluation constraints.
5. State the proposed AP-M6 slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-TM-*`, `AP-M6`, and
   `AP-EVAL-M6` identifier it implements. Treat absent runtime design, plan, contract, and evaluation
   authority as unresolved.
6. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or runtime, and cannot authorize Application Adoption.

Next task: propose AP-M6, the smallest locally testable networked provider-runtime slice. Identify
the exact documents, interfaces, implementation paths, tests, and acceptance boundary it would add
or update. The proposal must cover the networked Shared Edge, root catalogue and reserved platform
paths, prefix routing, bounded request and streaming behavior, generation loading and status
readback, Google OIDC and Platform Session seams through fake adapters, ES256 assertion and JWKS
seams through fake managed-key adapters, `gcp-cloud-run-v1` resolution through fake provider
metadata, direct-entry application verification, failure isolation, redaction, and repository
extraction. Wait for owner approval before editing.

Before runtime edits, obtain explicit owner decisions for the network server/framework, dependency
policy, and exact live header, request-body, response-body, non-streaming timeout, and
abusive-traffic limits. Do not infer them from Fixture limits, provider defaults, or discussion.

Do not write Terraform, create a workflow with cloud authority, create credentials, call a cloud
provider, modify repository settings, DNS, or identity configuration, deploy a service, run a live
plan, or claim Live evidence. AP-M6 belongs on a new bounded branch and pull request after AP-M5
merges; it is not a continuation of the infrastructure-planning branch. Local runtime tests may use
loopback only after the AP-M6 proposal and owner decisions are approved, and must never use an
external network or real provider.

Keep the proposal inside the App Platform boundary. Leave Finance Assistant requirements, code,
infrastructure, Terraform state, DNS, identity configuration, deployment, and access unchanged. An
Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating.
