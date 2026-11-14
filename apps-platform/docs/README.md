# App Platform documentation

Version 0.8 | Status: system design and versioned contracts implemented; runtime qualification
unavailable

This directory is the design authority for Comfforts App Platform. AP-M3 adds the logical system
design, threat boundary, Version 1 schemas, deterministic reference compiler, and reviewed contract
vectors. That repository behavior supplies Contract (`C`) evidence only. There is no Fixture (`F`),
Live (`L`), or Adoption (`A`) evidence, and no catalogue runtime, Shared Edge runtime, identity
provider, Fixture Application, Terraform configuration, or cloud resource is implemented.

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
7. [AP-M3 implementation plan](04_implementation_plan.md) owns delivery item 3 only.
8. [AP-M3 evaluation strategy](05_evaluation_strategy.md) defines its deterministic Contract gate.
9. [Version 1 contract index](../contracts/README.md) owns machine interfaces subordinate to the
   requirements, accepted decisions, and system design.
10. [Repository layout](repository_layout.md) defines capability ownership and extraction rules.
11. [Prompt ownership](../prompts/README.md) keeps task entry points separate from specifications.
12. [Deterministic-fixture planning handoff](../prompts/starting_prompt.md) provides a bounded entry
    point for proposing item 4 after AP-M3 merges.

AP-M3 system design and versioned contracts are implemented at this repository revision and pass
the deterministic gate. Item 3 delivery is complete only after its pull request merges. Item 4 has
no approved implementation plan, evaluation strategy, milestone identifier, or fixture topology;
those authorities must be proposed from updated `main` after the merge. An absent authority must
not be inferred from contracts, branch history, discussion, or an Integration Draft.

## Incremental delivery sequence

Each numbered item is a separate bounded branch and pull request. Start it from updated `main`, use
small reviewable commits, merge it, and only then begin the next item.

1. **Governance foundation — complete:** standalone project root, authority routing, extraction
   boundary, local checks, and path-scoped parent workflow.
2. **Requirements and decisions — complete:** product/quality requirements, accepted ownership,
   admission and fixture-first ADRs, handoff prompt, and inactive Finance integration package.
3. **System design and versioned contracts — implemented:** AP-M3 defines the logical platform,
   threat and evidence boundary, Version 1 machine contracts, deterministic compiler, and reviewed
   vectors. Its checks pass without a fixture runtime, Terraform, cloud resource, DNS, identity
   configuration, or Finance migration. Completion is recorded only by merging the pull request
   from `feat/apps-platform-system-design-contracts`.
4. **Deterministic fixture planning — next after item 3 merges:** from updated `main`, define and
   obtain owner approval for the fixture implementation plan and evaluation strategy before adding
   fixture code in later commits on the same bounded item 4 branch. The proposal must cover
   public/authenticated/restricted admission, identity delivery, feature-entitlement denial,
   routing, lifecycle, rollback, and direct-bypass cases. Suggested branch:
   `feat/apps-platform-fixtures`.
5. **Platform infrastructure and live qualification — later:** proceed only through separately
   approved slices after deterministic fixture qualification.
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

Current AP-M3 authorities authorize the Version 1 contract implementation and Contract evidence
only. Missing item 4 authorities block Fixture implementation rather than inheriting authority from
the AP-M3 plan or evaluation strategy.

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

Passing contract tests are revision-scoped Contract evidence, not operational evidence. Each future
capability must name its Fixture, Live, or Adoption gate and, where applicable, secret-free live
evidence. Credentials, Terraform state, saved plans, authenticated browser state, and unredacted
external payloads are never committed.
