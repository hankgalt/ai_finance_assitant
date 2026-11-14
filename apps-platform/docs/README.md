# App Platform documentation

Version 0.7 | Status: governance and requirements/decisions complete; system design and contracts
next

This directory is the design authority for Comfforts App Platform. The completed slice defines the
platform requirements and accepted decisions without implementing them. It does not claim that the
catalogue, Shared Edge, identity boundary, fixture applications, Terraform, or any cloud resource
exists.

## Current reading order and authority

1. [Project overview](../README.md) states the current operational status and project boundary.
2. [Domain glossary](../GLOSSARY.md) supplies canonical governance terms.
3. [Product requirements](01_product_requirements.md) defines required behavior, quality, scope, and
   ownership boundaries.
4. [Architecture decision records](02_architecture_decision_records.md) constrain shared-edge,
   application, registration, and state ownership.
5. [Repository layout](repository_layout.md) defines capability ownership and extraction rules.
6. [Prompt ownership](../prompts/README.md) keeps task entry points separate from specifications.
7. [System-design/contracts handoff](../prompts/starting_prompt.md) provides a bounded new-chat entry
   point for proposing the next slice.

The requirements-and-decisions slice is complete. System design, implementation planning,
evaluation strategy, threat modeling, contracts, fixture implementation, and Terraform remain
deferred until their owning slice is approved. An absent authority must not be inferred from
discussion history.

## Incremental delivery sequence

Each numbered item is a separate bounded branch and pull request. Start it from updated `main`, use
small reviewable commits, merge it, and only then begin the next item.

1. **Governance foundation — complete:** standalone project root, authority routing, extraction
   boundary, local checks, and path-scoped parent workflow.
2. **Requirements and decisions — complete:** product/quality requirements, accepted ownership,
   admission and fixture-first ADRs, handoff prompt, and inactive Finance integration package.
3. **System design and versioned contracts — next:** define the minimal Shared Edge, catalogue,
   registration, attachment, admission, identity, lifecycle, state, threat, and evaluation
   boundaries. Add only reviewed contract schemas and deterministic validation; implement no
   fixture runtime, Terraform, cloud resource, DNS, identity configuration, or Finance migration.
   Suggested branch: `feat/apps-platform-system-design-contracts`.
4. **Deterministic fixtures — following:** after item 3 merges, define and obtain owner approval for
   the fixture implementation plan and evaluation strategy before adding fixture code in later
   commits on the same bounded branch. Cover public/authenticated/restricted admission, identity
   delivery, feature-entitlement denial, routing, lifecycle, rollback, and direct-bypass cases.
   Suggested branch: `feat/apps-platform-fixtures`.
5. **Platform infrastructure and live qualification — later:** proceed only through separately
   approved slices after deterministic fixture qualification.
6. **Finance Application Adoption — later and independent:** use the inactive integration package
   only after platform qualification and Finance-owned adoption approval.

The suggested names are workflow guidance, not product authority. A slice is complete only when its
declared repository checks pass and its pull request is merged; deployed or qualified status still
requires the evidence named by its future evaluation authority.

## Future document precedence

Once present, conflicts will be resolved in this order:

1. Requirements specification
2. Accepted architecture decision records
3. System design
4. Implementation plan
5. Evaluation strategy
6. Runbooks and delivery evidence
7. Prompts

Until the remaining documents exist, the requirements and governance foundation authorize
documentation and deterministic governance checks only.

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

Documentation and source files are not operational evidence. Each future capability must name its
deterministic tests and, where applicable, secret-free live evidence. Credentials, Terraform state,
saved plans, authenticated browser state, and unredacted external payloads are never committed.
