# App Platform documentation

Version 0.9 | Status: deterministic Fixture harness implemented and qualified; Live and Adoption
qualification unavailable

This directory is the design authority for Comfforts App Platform. AP-M3 supplies Contract (`C`)
evidence through the logical design, threat boundary, Version 1 schemas, deterministic compiler,
and reviewed vectors. AP-M4 supplies Fixture (`F`) evidence through a synchronous in-process
reference edge, synthetic identity boundary, three independent Fixture Applications, reviewed
registration generations, and deterministic lifecycle journeys. Live (`L`) and Adoption (`A`)
evidence remain unavailable. No networked Shared Edge, provider identity, Terraform configuration,
cloud resource, DNS change, application migration, or production credential is implemented.

## Current reading order and authority

1. [Project overview](../README.md) states the current operational status and project boundary.
2. [Domain glossary](../GLOSSARY.md) supplies canonical governance terms.
3. [Product requirements](01_product_requirements.md) defines required behavior, quality, scope, and
   ownership boundaries.
4. [Architecture decision records](02_architecture_decision_records.md) constrain shared-edge,
   application, registration, and state ownership.
5. [System design](03_system_design.md) defines logical modules, interfaces, lifecycle, state
   ownership, and later runtime boundaries.
6. [Threat model](06_threat_model.md) defines trust zones, threats, controls, and evidence classes.
7. [AP-M3 and AP-M4 implementation plan](04_implementation_plan.md) owns delivery items 3 and 4.
8. [AP-M3 and AP-M4 evaluation strategy](05_evaluation_strategy.md) defines the deterministic
   Contract and Fixture gates.
9. [Version 1 contract index](../contracts/README.md) owns machine interfaces subordinate to the
   requirements, accepted decisions, and system design.
10. [Repository layout](repository_layout.md) defines capability ownership and extraction rules.
11. [Prompt ownership](../prompts/README.md) keeps task entry points separate from specifications.
12. [Infrastructure-planning handoff](../prompts/starting_prompt.md) provides a bounded entry point
    for proposing item 5 only after AP-M4 merges.

AP-M3 contract behavior and AP-M4 Fixture behavior are implemented at this repository revision and
pass their deterministic gates. Item 4 delivery is complete only after its pull request merges.
Item 5 has no approved implementation plan, Live evaluation strategy, provider topology, operator
procedure, or infrastructure mutation authority; those must be proposed from updated `main` after
the merge. An absent authority must not be inferred from fixture code, branch history, discussion,
or an Integration Draft.

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
4. **Deterministic fixtures — implemented and Fixture-qualified:** AP-M4 defines and exercises the
   bounded in-process reference edge, synthetic identity, three independent fixtures, reviewed
   registrations, lifecycle, failure isolation, and rollback. Its checks pass without a socket,
   credential, provider, Terraform, cloud resource, DNS mutation, or application migration.
   Completion is recorded only by merging the pull request from `feat/apps-platform-fixtures`.
5. **Platform infrastructure planning — next after item 4 merges:** from updated `main`, propose and
   obtain owner approval for the smallest infrastructure implementation plan and Live evaluation
   strategy. Planning must resolve provider topology, state ownership, identity, ingress, DNS,
   lifecycle, cost, operator, rollback, and evidence decisions before any infrastructure or live
   mutation. Implementation belongs to later separately approved work.
6. **Finance Application Adoption — later and independent:** use the inactive integration package
   only after platform qualification and Finance-owned adoption approval.

The suggested names are workflow guidance, not product authority. A slice is complete only when its
declared repository checks pass and its pull request is merged; deployed or qualified status still
requires the evidence named by its future evaluation authority.

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

Current AP-M3 and AP-M4 authorities authorize the Version 1 contract implementation, the
deterministic in-process Fixture harness, and their Contract and Fixture evidence only. Missing item
5 authorities block infrastructure implementation and Live qualification rather than inheriting
authority from fixture code, the AP-M4 plan, or its evaluation strategy.

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

Passing contract and Fixture tests are revision-scoped Contract and Fixture evidence, not deployed
or operational evidence. Each future capability must name its Live or Adoption gate and, where
applicable, secret-free live evidence. Credentials, Terraform state, saved plans, authenticated
browser state, and unredacted external payloads are never committed.
