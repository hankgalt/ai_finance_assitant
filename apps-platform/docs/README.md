# App Platform documentation

Version 1.1 | Status: AP-M6 implementation in progress; catalogue, routing, sessions, admission,
assertions, application verification, and Cloud Run attachment resolution implemented locally;
provider operation, Live, and Adoption qualification unavailable

This directory is the design authority for Comfforts App Platform. AP-M3 supplies Contract (`C`)
evidence through the logical design, threat boundary, Version 1 schemas, deterministic compiler,
and reviewed vectors. AP-M4 supplies Fixture (`F`) evidence through a synchronous in-process
reference edge, synthetic identity boundary, three independent Fixture Applications, reviewed
registration generations, and deterministic lifecycle journeys. AP-M5 supplies accepted provider
topology, identity, state, operator, lifecycle, evidence, incident, and cost planning plus a
deterministic planning gate. Live (`L`) and Adoption (`A`) evidence remain unavailable. No listening
or deployed Shared Edge, provider identity, Terraform configuration, cloud resource, DNS change,
application migration, or production credential is implemented.

## Current reading order and authority

1. [Project overview](../README.md) states the current operational status and project boundary.
2. [Domain glossary](../GLOSSARY.md) supplies canonical governance terms.
3. [Product requirements](01_product_requirements.md) defines required behavior, quality, scope, and
   ownership boundaries.
4. [Architecture decision records](02_architecture_decision_records.md) constrain shared-edge,
   application, registration, state, provider, identity, and operator boundaries.
5. [System design](03_system_design.md) defines logical modules, interfaces, lifecycle, state
   ownership, selected Live topology, and unresolved implementation inputs.
6. [Threat model](06_threat_model.md) defines trust zones, threats, controls, and evidence classes.
7. [AP-M3 through AP-M6 implementation plan](04_implementation_plan.md) owns delivery items 3
   through 6 and separates runtime, Terraform, deployment, and Live work.
8. [Evaluation strategy](05_evaluation_strategy.md) defines AP-M3 through AP-M6 deterministic gates
   and the future AP-M7 through AP-M9 claim boundaries.
9. [Version 1 contract index](../contracts/README.md) owns machine interfaces subordinate to the
   requirements, accepted decisions, and system design.
10. [Repository layout](repository_layout.md) defines capability ownership and extraction rules.
11. [Prompt ownership](../prompts/README.md) keeps task entry points separate from specifications.
12. [Provider-runtime handoff](../prompts/starting_prompt.md) provides a bounded entry point for
    proposing AP-M6 only after AP-M5 merges.

AP-M3 Contract behavior, AP-M4 Fixture behavior, and AP-M5 planning authority are merged and pass
their deterministic gates. AP-M6-W1 is accepted. AP-M6-W2 implements the locked dependency
environment and closed-default ASGI foundation. AP-M6-W3 implements bounded immutable-generation
loading and a locally tested Cloud Storage source adapter; it performs no provider operation.
AP-M6-W4 implements escaped catalogue projection, canonical path closure, registered route and
mount selection, and path rewriting. AP-M6-W5 implements the Google OIDC and opaque Platform
Session boundary, public/authenticated/restricted admission, exact restricted membership, absolute
expiry, safe logout, and production/fake provider and store seams. Its route handoff remains closed
until forwarding exists. AP-M6-W6 implements minimized ES256 assertions, exact application
audiences, Cloud KMS and deterministic signing seams, public-only current/overlap JWKS, visitor-
value replacement, and independent application verification with bounded key caching. AP-M6-W7
implements strict Cloud Run URN parsing, injected production/fake metadata adapters, and exact
readiness, owner, audience, and edge-caller grant checks. It supplies no proxy or operational
behavior and performs no provider operation during deterministic verification. An absent behavior
or later authority must not be inferred from planning documents, fixture code, branch history,
discussion, or an Integration Draft.

## Incremental delivery sequence

Each numbered item is a separate bounded branch and pull request. Start it from updated `main`, use
small reviewable commits, merge it, and only then begin the next item.

1. **Governance foundation — complete:** standalone project root, authority routing, extraction
   boundary, local checks, and path-scoped parent workflow.
2. **Requirements and decisions — complete:** product/quality requirements, accepted ownership,
   admission and fixture-first ADRs, handoff prompt, and inactive Finance integration package.
3. **System design and versioned contracts — complete:** AP-M3 defines the logical platform, threat
   and evidence boundary, Version 1 machine contracts, deterministic compiler, and reviewed
   vectors. Its pull request is merged, and its repository behavior supplies Contract evidence.
4. **Deterministic fixtures — complete and Fixture-qualified:** AP-M4 defines and exercises the
   bounded in-process reference edge, synthetic identity, three independent fixtures, reviewed
   registrations, lifecycle, failure isolation, and rollback. Its merged implementation supplies
   Fixture evidence without a socket, credential, provider, Terraform, cloud resource, DNS
   mutation, or application migration.
5. **Platform infrastructure planning — implemented and planning-validated:** AP-M5 records
   ADR-005 through ADR-009, the provider-specific design, AP-M5 plan, AP-EVAL-M5, and future claim
   boundaries. It creates no runtime, Terraform, workflow authority, cloud resource, DNS change, or
   Live evidence. Its merged evidence proves planning consistency only.
6. **Networked provider runtime — implementation in progress:** AP-M6 selects the deep ASGI module,
   locked dependency policy, exact request profile, eleven work packages, and ten deterministic
   gates. AP-M6-W2 supplies the locked foundation, AP-M6-W3 supplies immutable generation loading,
   AP-M6-W4 supplies catalogue and registered routing, AP-M6-W5 supplies sessions and admission,
   AP-M6-W6 supplies assertions and application verification, and AP-M6-W7 supplies Cloud Run
   attachment resolution; later work packages remain unavailable. AP-M6 performs no Terraform or
   cloud mutation.
7. **Terraform and workflow implementation — later:** AP-M7 may implement reviewed configuration
   and static gates only after AP-M6 merges; it performs no authenticated plan or apply.
8. **Non-production qualification deployment — later:** AP-M8 may bootstrap and deploy only through
   separately approved protected operator actions after repository extraction and AP-M7 merge.
9. **Live qualification — later:** AP-M9 must execute the approved Live gates against the exact
   deployed revision and retain redacted evidence before any Live-qualified claim.
10. **Finance Application Adoption — later and independent:** use the inactive integration package
    only after platform qualification and Finance-owned adoption approval.

The suggested names are workflow guidance, not product authority. A slice is complete only when its
declared repository checks pass and its pull request is merged; deployed or qualified status still
requires the evidence named by its later evaluation authority.

## Document precedence

Conflicts are resolved in this order:

1. Requirements specification
2. Accepted architecture decision records
3. System design
4. Versioned contract index and schemas
5. Implementation plan
6. Evaluation strategy and threat-specific evidence requirements
7. Runbooks and delivery evidence
8. Prompts

Current AP-M3 and AP-M4 authorities authorize the Version 1 contract implementation, deterministic
in-process Fixture harness, and their Contract and Fixture evidence. AP-M5 authorizes planning, and
AP-M6 authorizes only local provider-runtime implementation and tests after AP-M6-W1 acceptance.
Terraform, deployment, Live qualification, and Application Adoption remain separate AP-M7 through
AP-M9 or application-owned gates.

## Scope labels

- **Governance foundation:** project authority, vocabulary, layout, agent routing, and checks without
  product behavior.
- **Proposed:** a requirement or decision awaiting its named validation and approval.
- **Implemented:** repository behavior exists and passes deterministic checks; no live operation is
  implied.
- **Qualified:** the declared evaluation gate has revision-scoped evidence.
- **Integration draft:** a non-authoritative input for a consuming application.
- **Historical evidence:** an immutable account of an earlier implementation or qualification.

## Application boundary

The App Platform owns only the boundaries assigned by its product requirements and accepted
decisions. Application data, provider rights, Feature Entitlements, and product behavior remain
under each application's own authority. Nothing under this subtree changes the active Finance
Assistant requirements, contracts, Terraform state, DNS, IAP configuration, or deployment.

## Inactive integration inputs

- [Finance Assistant integration draft](../integrations/ai_finance_assistant/README.md) preserves a
  proposed edge-ownership transfer and future Finance documentation deltas. It is not platform or
  Finance authority, implementation evidence, or permission to migrate an application.

Read an Integration Draft only after the platform authorities above and only when its consuming
application or a proposed interface makes it relevant. A draft cannot weaken generic platform
requirements or silently specialize the platform around one application.

## Evidence discipline

Passing contract and Fixture tests are revision-scoped Contract and Fixture evidence. Passing
AP-EVAL-M5 proves planning consistency only. Neither is deployed or operational evidence. Each
future capability must pass its named gate and, where applicable, retain secret-free Live evidence.
Credentials, Terraform state, saved plans, authenticated browser state, and unredacted external
payloads are never committed.
