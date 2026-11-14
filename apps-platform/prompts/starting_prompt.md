# App Platform deterministic-fixture planning handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: governance, product requirements, accepted architecture decisions, system design,
threat model, the AP-M3 plan and evaluation strategy, Version 1 schemas, deterministic reference
compiler, and reviewed contract vectors are implemented. They provide Contract (`C`) evidence only.
No platform runtime, Fixture Application, provider adapter, Terraform configuration, cloud resource,
DNS change, identity configuration, credential, or application migration is implemented or
qualified.

Use this handoff only from updated `main` after the AP-M3 pull request has merged. If AP-M3 is not in
`main`, the working tree is not clean, or the requested branch already contains item 4 changes,
report that conflict and stop instead of switching, pulling, resetting, committing, or combining
slices without owner direction.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform project root. While colocated, also preserve the
   containing repository's security, source-control, and destructive-action guardrails.
2. Inspect the working tree, branch, and relationship to `main`. Preserve unrelated changes and
   report any state that conflicts with the incremental delivery sequence instead of resetting,
   pulling, switching, or committing without owner direction.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md`, and
   `contracts/README.md` completely to understand the implemented AP-M3 boundary and the behavior
   explicitly deferred to Fixture, Live, and Adoption evidence.
5. State the proposed item 4 planning slice and every `AP-PR-*`, `AP-QR-*`, and `ADR-*` identifier
   it would validate. Treat the absent item 4 implementation plan, evaluation strategy, milestone
   identifier, fixture topology, and owner decisions as unresolved.
6. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior, and cannot serve as Fixture Application requirements.

Next task: propose item 4 planning and evaluation authority for the smallest deterministic Fixture
Application slice. Identify the exact documents it would add or update, the fixture boundary and
synthetic topology, observable cases, evidence classes, acceptance and rejection gates, state
ownership, deterministic verification commands, and every owner decision still required. Cover the
approved requirements for public, authenticated, and restricted admission; identity delivery;
Feature Entitlement separation; catalogue and route isolation; lifecycle and rollback; attachment
failure; and direct-bypass denial without selecting unresolved technology or provider behavior.
Wait for owner approval before editing.

Do not implement a Fixture Application, runtime, provider adapter, or fixture infrastructure while
planning authority is absent. After the plan and evaluation strategy are approved, implementation
may proceed only in later reviewable commits on the same item 4 branch. Item 4 belongs on a new
bounded branch and pull request; it is not a continuation of the AP-M3 branch.

Keep the proposal inside the App Platform boundary. Use Fixture Applications for future platform
qualification; leave Finance Assistant requirements, code, infrastructure, Terraform state, DNS,
identity configuration, and deployment unchanged. An Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating.
