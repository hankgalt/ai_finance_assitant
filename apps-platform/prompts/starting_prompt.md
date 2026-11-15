# App Platform infrastructure-planning handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: governance, product requirements, accepted architecture decisions, system design,
threat model, Version 1 contracts, deterministic compiler, and the AP-M3/AP-M4 plans and evaluation
strategies are implemented. The contract layer provides Contract (`C`) evidence. The synchronous
in-process reference edge, synthetic identity boundary, three independent Fixture Applications,
reviewed registrations, and lifecycle journeys provide Fixture (`F`) evidence only. No networked
Shared Edge, provider identity, Terraform configuration, cloud resource, DNS change, credential,
deployment, Application Adoption, or Live (`L`) evidence is implemented or qualified.

Use this handoff only from updated `main` after the AP-M4 pull request has merged. If AP-M4 is not
in `main`, the working tree is not clean, or the requested branch already contains item 5 changes,
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
   `contracts/README.md`, and `fixtures/registrations/README.md` completely to understand the
   implemented Contract and Fixture boundaries and the behavior explicitly deferred to Live and
   Adoption evidence.
5. State the proposed item 5 planning slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-TM-*`, and
   proposed evaluation identifier it would cover. Treat the absent infrastructure plan, Live
   evaluation authority, provider topology, state-root design, operator procedure, and deployment
   decisions as unresolved.
6. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize Application
   Adoption.

Next task: propose item 5 planning and evaluation authority for the smallest platform
infrastructure and Live-qualification sequence. Identify the exact documents it would add or
update, the provider and shared-edge decisions still required, state and resource ownership,
attachment and identity trust boundaries, direct-origin denial, DNS and TLS sequencing,
registration activation and rollback, operator access, secrets, observability, demo-scale cost and
recovery controls, deterministic plan checks, explicit live actions, evidence retention, acceptance
and rejection gates, and every owner decision still required. Separate planning, infrastructure
implementation, deployment, and Live qualification into reviewable slices. Wait for owner approval
before editing.

Do not write Terraform, create credentials, call a cloud provider, modify DNS or identity, deploy a
service, run a live plan, or reuse Fixture evidence as Live evidence while item 5 authority is
absent. Item 5 belongs on a new bounded branch and pull request after AP-M4 merges; it is not a
continuation of the fixture branch.

Keep the proposal inside the App Platform boundary. Leave Finance Assistant requirements, code,
infrastructure, Terraform state, DNS, identity configuration, deployment, and access unchanged. An
Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating. Any later live verification must use a separate explicit operator command and
secret-free revision-scoped evidence.
