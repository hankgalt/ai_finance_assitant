# App Platform implementation plan

Version 0.1 | Status: implementation-plan authority for AP-M3 only

This document owns delivery item 3, the system-design-and-versioned-contracts slice. It does not
authorize a Shared Edge runtime, catalogue runtime, Fixture Application, Terraform configuration,
cloud resource, DNS change, identity change, credential, or Application Adoption.

Requirements: AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006

Decisions: ADR-001, ADR-002, ADR-003, ADR-004

Design: [App Platform system design](03_system_design.md)

Threats: [App Platform threat model](06_threat_model.md)

Evaluation: [App Platform evaluation strategy](05_evaluation_strategy.md)

## AP-M3 · System design and versioned contracts

### Outcome

AP-M3 establishes the reviewed logical platform design, threat boundary, versioned machine
contracts, and deterministic offline validation needed before Fixture Applications may be planned.
It provides one deep module interface:

```text
compile(previous_generation, proposed_registration_set, platform_configuration)
    -> compiled_configuration + ownership_manifest
    |  ordered_validation_violations
```

The interface is pure and side-effect-free. It is not a deployment interface and may not call a
provider, resolve DNS, read credentials, inspect another state backend, or mutate a repository or
runtime.

### Scope

AP-M3 includes:

- system-design and threat-model authority;
- an item-scoped implementation plan and deterministic evaluation gate;
- Version 1 schemas for registration sets, attachments, compiled Shared Edge configuration,
  verified identity context, and state ownership;
- a standard-library reference compiler and validator;
- synthetic contract vectors and deterministic tests; and
- authority, status, repository-layout, and next-slice handoff updates.

AP-M3 excludes:

- a catalogue, edge, identity, fixture, or application runtime;
- provider-specific attachment adapters or provider discovery;
- Terraform, cloud resources, state backends, plans, DNS, TLS, IAM, OAuth, or secrets;
- live mutation, runtime qualification, screenshots, or authenticated evidence; and
- Finance Assistant code, configuration, migration, access changes, or Application Adoption.

## Dependencies

| Dependency | Required state | AP-M3 treatment |
| --- | --- | --- |
| Governance foundation | Merged and passing | Preserve project boundary, extraction rules, and `make check` |
| Product requirements | Authoritative | Trace every contract behavior and exclusion |
| ADR-001 through ADR-004 | Accepted | Treat ownership, admission, registration, and fixture-first decisions as constraints |
| System design | Approved in this slice | Define the compiler and future runtime seams before schemas |
| Threat model | Approved in this slice | Cover every Contract (`C`) evidence requirement |
| Owner decisions | Approved for this slice | Use the Version 1 route, lifecycle, attachment, identity, and ownership semantics in the design |

An unmet or changed dependency stops the affected work package. Discussion history, an Integration
Draft, or a later-slice implementation cannot fill an authority gap.

## Work packages

### AP-M3-W1 · Logical system design

Deliverables:

- `docs/03_system_design.md`; and
- only the canonical terms required by that design in `GLOSSARY.md`.

The design must define the Shared Edge, catalogue, Registration Set, Application Registration,
Application Attachment, route model, admission and identity seam, lifecycle, application-release
boundary, exclusive ownership, failure behavior, fixture boundary, and unresolved implementation
decisions. It must describe no runtime control as implemented.

### AP-M3-W2 · Threat boundary

Deliverables:

- `docs/06_threat_model.md`; and
- the system-design link to that authority.

The threat model must identify assets, actors, trust crossings, control ownership, data classes,
threats `AP-TM-001` through `AP-TM-014`, evidence classes, residual risks, and unresolved security
decisions. Contract evidence must never be represented as fixture, live, or adoption evidence.

### AP-M3-W3 · Plan and evaluation authority

Deliverables:

- `docs/04_implementation_plan.md`; and
- `docs/05_evaluation_strategy.md`.

These documents define only AP-M3. They must name exact deliverables, acceptance criteria, tests,
evidence, exclusions, security and privacy impact, limitations, and the merge dependency that blocks
delivery item 4.

### AP-M3-W4 · Versioned contracts

Deliverables:

- `contracts/README.md`;
- `contracts/schemas/registration-set.v1.schema.json`;
- `contracts/schemas/application-attachment.v1.schema.json`;
- `contracts/schemas/compiled-shared-edge.v1.schema.json`;
- `contracts/schemas/verified-identity-context.v1.schema.json`; and
- `contracts/schemas/state-ownership-manifest.v1.schema.json`.

All schemas use JSON Schema Draft 2020-12, stable `urn:comfforts:app-platform:` identifiers and
references resolved through a project-local registry, explicit Version 1 discriminators, bounded
strings and collections, and closed objects unless a reviewed extension point is necessary. No
schema fetches a remote reference.

`contracts/README.md` is the contract index and must define:

- authority and precedence;
- schema and instance versioning;
- backward-compatible versus breaking change rules;
- canonical serialization and digest rules;
- stable violation-code semantics;
- the compiler interface and its non-mutating behavior;
- supported and deliberately unsupported adapter kinds;
- security and secret-handling rules; and
- the difference between contract implementation and runtime qualification.

The Version 1 schemas must encode the system design without adding provider-specific behavior. An
unknown attachment adapter is invalid; AP-M3 may use a synthetic contract-only adapter kind for
test vectors, but it may not implement or imply a Fixture Application or live provider adapter.

### AP-M3-W5 · Deterministic validation

Deliverables:

- `contracts/__init__.py`;
- `contracts/validation.py`;
- `contracts/test-vectors/manifest.v1.json`;
- synthetic valid and invalid JSON cases under `contracts/test-vectors/`;
- `tests/test_contracts.py`; and
- a `contract-check` dependency in the project `Makefile`.

The reference validator uses the Python standard library only. It implements the explicitly
documented JSON Schema keyword subset used by these five schemas and fails if a schema introduces
an unsupported keyword. It is not a general JSON Schema implementation. Shape validation through
that bounded schema interpreter and semantic compilation are separate phases checked by the same
test-vector manifest so they cannot silently diverge.

The validator must:

- parse bounded JSON and reject duplicate object keys;
- validate contract versions, required fields, types, bounds, enumerations, and unknown fields;
- validate the complete set for routes, mounts, reserved paths, lifecycle, admission, attachment,
  audience, catalogue, and ownership semantics;
- compare a proposed generation with its declared predecessor when supplied;
- emit stable, ordered violations and no compiled output on any failure;
- emit canonical compiled configuration and ownership output on success; and
- perform no network access, provider lookup, credential access, input mutation, or file write.

Tests exercise only observable behavior through the compiler interface. Test data is deterministic,
synthetic, non-secret, and not a Fixture Application.

### AP-M3-W6 · Authority integration and handoff

Deliverables update only:

- `AGENTS.md`;
- `README.md`;
- `docs/README.md`;
- `docs/repository_layout.md`;
- `prompts/README.md` and `prompts/starting_prompt.md`;
- `tests/test_governance.py`; and
- the existing Finance Integration Draft checks only if required to preserve its inactive status.

The updates place the new authorities in the reading order, record contract implementation without
claiming runtime behavior, preserve the inactive Finance package, and route the next task to item 4
planning only after AP-M3 merges. They must not add a fixture implementation plan or evaluation
authority.

## Ordered delivery

Work proceeds in this order:

1. approve system design;
2. approve the threat boundary;
3. approve the AP-M3 plan and evaluation strategy;
4. approve Version 1 schemas and contract policy;
5. approve deterministic validation and test evidence; and
6. reconcile authority indexes and the next-slice handoff.

Each work package is a small reviewable commit. A later package may refine an earlier AP-M3 document
only to link newly added authority, correct an inconsistency, or record actual results. It may not
silently change an approved interface or introduce item 4 behavior.

## Acceptance criteria

AP-M3 is accepted only when all of the following are true:

1. Every planned behavior traces to a requirement, accepted ADR, system-design section, and
   applicable threat identifier.
2. The five schemas are strict, versioned, locally resolvable, extraction-safe, and free of secrets
   and provider-specific operational assumptions.
3. Schema and semantic validation agree for every declared test vector.
4. Valid input produces byte-stable canonical output and a stable digest for the same compiler
   version; invalid input produces ordered stable violations and no partial output.
5. Tests cover catalogue projection, route isolation, every Admission Mode, identity claim shape,
   attachment mounts, application updates, lifecycle transitions, rollback inputs, and exclusive
   ownership.
6. Contract controls mapped to `AP-TM-001` through `AP-TM-014` are tested to their declared `C`
   boundary without claiming `F`, `L`, or `A` evidence.
7. `make check` passes without a credential, network call, paid provider, browser, cloud account, or
   external mutation.
8. Project-relative contract loading and a temporary-copy validation test demonstrate that the
   contract layer does not depend on the containing repository.
9. The change contains no fixture runtime, infrastructure, Terraform state, saved plan, DNS,
   identity configuration, credential, or Finance Application Adoption change.
10. Status and handoff documents describe contract behavior as implemented only after its tests
    pass and continue to describe every runtime and live control as unimplemented.

Near-complete work, undocumented skips, or passing tests against a different schema revision do not
satisfy AP-M3.

## Required evidence

The pull-request handoff records:

- branch, source revision, and final revision;
- commits and changed paths for each AP-M3 work package;
- exact verification commands, exit status, test count, failures, and skips;
- schema identifiers, compiler version, and test-vector manifest version;
- the requirements, ADRs, and threats covered by the deterministic gate;
- security and privacy impact;
- explicit `F`, `L`, and `A` limitations and every unresolved later decision; and
- confirmation that no credential, state, saved plan, authenticated payload, or external mutation
  was used.

Test output in a review description is evidence for this repository revision. Generated reports,
screenshots, plans, caches, or authenticated artifacts are not committed merely to demonstrate a
passing deterministic gate.

## Security and privacy impact

AP-M3 reduces ambiguity by making untrusted registration inputs, identity claims, route selection,
attachment references, and state ownership strict and testable. It introduces no runtime data flow.
Restricted membership and signed assertion examples use synthetic values; secret payloads,
application data, provider data, and real identities are prohibited from schemas, vectors, logs,
and evidence.

The reference validator is not a security boundary for a live deployment. Future runtimes must
enforce the same contracts at their own trust crossings and qualify the runtime controls separately.

## Limitations and deferred work

AP-M3 does not prove that:

- a Shared Edge, catalogue, identity boundary, attachment, or state backend exists;
- signatures, ingress, IAM, TLS, DNS, routing, rollback, logging, or provider controls work live;
- a Fixture Application or real application is compatible; or
- Finance Assistant has adopted or can migrate to the platform.

Delivery item 4 has no approved implementation plan, evaluation strategy, fixture topology, or
milestone identifier in this document. It may be proposed only from `main` after the AP-M3 pull
request merges. Infrastructure and Application Adoption remain later independent slices.

## Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M3-W1 through AP-M3-W3 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-004 | AP-TM-001 through AP-TM-014 |
| AP-M3-W4 | AP-PR-001 through AP-PR-007; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-003 | AP-TM-001 through AP-TM-012, AP-TM-014 |
| AP-M3-W5 | AP-PR-001 through AP-PR-008; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001 through ADR-004 | Contract (`C`) portions of AP-TM-001 through AP-TM-014 |
| AP-M3-W6 | AP-PR-008, AP-PR-009; AP-QR-003, AP-QR-004, AP-QR-006 | ADR-004 | AP-TM-010, AP-TM-011, AP-TM-014 |
