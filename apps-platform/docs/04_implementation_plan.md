# App Platform implementation plan

Version 0.4 | Status: implementation-plan authority through AP-M6; no Terraform, deployment, or
Live qualification authority

This document preserves delivery item 3, the system-design-and-versioned-contracts slice, delivery
item 4, the deterministic-fixtures slice, and delivery item 5, the infrastructure-planning slice.
It now owns delivery item 6, the networked-provider-runtime slice. AP-M6 may implement and locally
test a listening Shared Edge and production provider adapters through deterministic fakes. It does
not authorize Terraform configuration, a cloud call, credential, provider resource, DNS or identity
mutation, deployment, Live qualification, or Application Adoption.

Requirements: AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006

Decisions: ADR-001 through ADR-009

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

AP-M3 did not approve a fixture implementation. That merge dependency is now satisfied and the
separate AP-M4 authority below does not retroactively add Fixture evidence to AP-M3. Infrastructure
and Application Adoption remain later independent slices.

## Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M3-W1 through AP-M3-W3 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-004 | AP-TM-001 through AP-TM-014 |
| AP-M3-W4 | AP-PR-001 through AP-PR-007; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-003 | AP-TM-001 through AP-TM-012, AP-TM-014 |
| AP-M3-W5 | AP-PR-001 through AP-PR-008; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001 through ADR-004 | Contract (`C`) portions of AP-TM-001 through AP-TM-014 |
| AP-M3-W6 | AP-PR-008, AP-PR-009; AP-QR-003, AP-QR-004, AP-QR-006 | ADR-004 | AP-TM-010, AP-TM-011, AP-TM-014 |

## AP-M4 · Deterministic Fixture Applications

### Outcome

AP-M4 implements the smallest deterministic qualification harness for the logical platform design.
It provides one deep in-process module with three observable operations:

```text
activate(proposed_registration_set) -> activation_result
rollback(reviewed_generation_digest) -> activation_result
handle(request) -> response
```

Activation resolves the declared predecessor against the harness's current reviewed generation;
the caller cannot substitute a separate predecessor object. Activation and rollback change only
the harness's in-memory Platform State. `handle` accepts and returns immutable values and is the
request test surface. Callers cannot configure routes, catalogue entries, admission exceptions, or
attachment targets outside a compiled generation and the read-only adapter map supplied at
construction.

AP-M4 produces Fixture (`F`) evidence only. It does not turn the harness into a network server or
qualify a live provider, real identity, persistent control plane, or consuming application.

### Scope

AP-M4 includes:

- the deterministic reference topology and fixture threat profile selected in system design;
- a Python standard-library, synchronous, in-process request pipeline with no listening socket;
- the `fixture-in-process-v1` attachment adapter and its exact inert resource-reference binding;
- HTML catalogue projection, canonical route and mount selection, forwarding, and closed responses;
- public, authenticated, and restricted admission using synthetic identities;
- fixture-only signed identity delivery, independent application verification, and replay denial;
- three independently constructed Fixture Applications and their Application State;
- reviewed registration generations, atomic in-memory activation, lifecycle journeys, and rollback;
- deterministic behavior, security, extraction, non-mutation, and redaction tests; and
- status, repository-layout, and next-slice handoff reconciliation after the gate passes.

AP-M4 excludes:

- a socket, HTTP framework, browser, process manager, external registration endpoint, or database;
- network ingress, DNS, TLS, OAuth, production signing, credential, IAM, or provider discovery;
- persistence, concurrent writers, streaming, load, availability, or performance qualification;
- Terraform, cloud resources, state backends, live plans, deployment, or operator mutation;
- changes to Version 1 attachment fields or identity claims; and
- Finance Assistant requirements, code, infrastructure, identity, state, registration, migration,
  access, or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M4 treatment |
| --- | --- | --- |
| AP-M3 | Merged to clean `main` with `make check` passing | Reuse the accepted Version 1 contracts and compiler |
| Fixture system design | Owner-approved on the AP-M4 branch | Implement only the selected in-process topology and evidence boundary |
| Threat profile | Owner-approved on the AP-M4 branch | Cover every applicable Fixture (`F`) claim without implying Live (`L`) evidence |
| AP-M4 plan and evaluation | Approved before runtime edits | Bind implementation paths, observable behavior, gates, and evidence |
| Python runtime | Supported Python 3 standard library | Add no package, service, credential, or network dependency |
| Owner decisions | Recorded in design | Use the three fixtures, exact limits, synthetic assertion profile, and Git-reviewed registration model |

Changing a Version 1 field, a requirement, an accepted ADR, or the Fixture evidence boundary stops
the affected package for owner review. An Integration Draft, a real application, or live provider
behavior cannot substitute for a missing AP-M4 dependency.

### Work packages

#### AP-M4-W1 · Fixture topology and threat profile

Deliverables update only:

- `docs/03_system_design.md`;
- `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects the in-process reference topology, three fixtures, request limits, synthetic
identity profile, in-memory generation model, direct-bypass claim boundary, and remaining live
decisions. It implements no runtime and creates no Fixture evidence.

#### AP-M4-W2 · Plan and evaluation authority

Deliverables update only:

- `docs/04_implementation_plan.md`;
- `docs/05_evaluation_strategy.md`; and
- focused AP-M4 identifier and scope checks in `tests/test_governance.py`.

This package defines the remaining implementation order, exact acceptance boundary, mandatory
Fixture gates, evidence, exclusions, and handoff. It may not add `fixtures/` implementation.

#### AP-M4-W3 · Deterministic reference edge and attachment binding

Deliverables:

- `fixtures/__init__.py` and `fixtures/reference_edge.py`;
- the `fixture-in-process-v1` semantic binding in `contracts/validation.py` and its policy in
  `contracts/README.md`;
- `tests/test_fixtures.py` coverage for bounded requests, catalogue, routes, mounts, forwarding,
  closed responses, and attachment failure; and
- a standard-library `fixture-check` target in `Makefile`, included by `make check`.

The reference edge implements one `handle(request) -> response` interface. Adapter resolution is an
exact read-only map lookup; it performs no dynamic import, URL fetch, filesystem lookup, or provider
discovery. An invalid fixture resource reference or missing target rejects activation without
changing the current generation.

#### AP-M4-W4 · Synthetic identity and admission

Deliverables extend only:

- `fixtures/reference_edge.py` with the explicitly constructed identity adapter and fixture signer;
- `fixtures/identity.py` with envelope verification and the bounded replay store; and
- `tests/test_fixtures.py` with public, authenticated, restricted, stripping, forgery, expiry,
  issuer, audience, cross-application, and replay cases.

The implementation uses only injected public test material and an injected clock. It must not read
an environment secret, select a production algorithm, emulate OAuth, or describe its in-process
assertion denial as network-origin protection.

#### AP-M4-W5 · Independent Fixture Applications and registrations

Deliverables:

- `fixtures/applications.py`;
- complete reviewed generations under `fixtures/registrations/`;
- synthetic fixture-owned setup under `fixtures/data/` only when data cannot be clearer as code;
  and
- `tests/test_fixtures.py` coverage for all three applications, principal derivation, entitlement
  denial, catalogue visibility, state isolation, and cross-application denial.

`fixture-public`, `fixture-authenticated`, and `fixture-restricted` each receive their own runtime
and Application State. Registration inputs use the public Version 1 contracts and must not copy
contract test vectors or depend on Finance Assistant.

#### AP-M4-W6 · Generation lifecycle, failure, and rollback journeys

Deliverables extend only:

- `fixtures/reference_edge.py` with atomic activation and rollback over reviewed in-memory
  generations;
- the fixture registration generations needed for update, suspension, retirement, and attachment
  replacement; and
- `tests/test_fixtures.py` with successful and failed lifecycle journeys.

Tests observe initial registration, an unchanged-registration application release, a registration
update, suspension, retirement, replacement, invalid or unavailable activation, failure isolation,
and rollback. A generation change must never roll back, delete, or transfer Fixture Application
State.

#### AP-M4-W7 · Qualification record and handoff

Deliverables update only after every behavioral gate passes:

- `README.md`, `docs/README.md`, and `docs/repository_layout.md`;
- `prompts/README.md` and `prompts/starting_prompt.md`;
- `AGENTS.md` only if the authoritative reading or verification order changes;
- governance checks that protect truthful AP-M4 status; and
- the pull-request handoff record, without committing generated or authenticated evidence.

The updates may record the exact Fixture evidence obtained at the evaluated revision. They must
leave Live and Adoption evidence unavailable and must not initiate infrastructure or application
adoption work.

### Ordered delivery

Work proceeds in this order:

1. approve fixture topology and threat-profile authority;
2. approve AP-M4 planning and evaluation authority;
3. implement and approve the bounded reference edge and fixture adapter binding;
4. implement and approve synthetic identity and admission;
5. implement and approve the three Fixture Applications and reviewed registrations;
6. implement and approve lifecycle, failure, and rollback journeys; and
7. run the complete gate, record actual evidence, and reconcile the handoff.

Each work package is a separate small commit reviewed before the next package is edited. A later
package may change an earlier file only to complete the behavior assigned above, correct a proven
inconsistency, or record actual results. It may not add a listening service, live provider behavior,
or Application Adoption.

### Acceptance criteria

AP-M4 is accepted only when all of the following are true:

1. Every implemented behavior traces to AP-PR-001 through AP-PR-009, AP-QR-001 through AP-QR-006,
   ADR-001 through ADR-004, the fixture system design, and the applicable Fixture portions of
   AP-TM-001 through AP-TM-014.
2. Exactly three independent fixtures register through Version 1 complete Registration Sets, and
   only `fixture-in-process-v1` resolves in the harness.
3. The request pipeline enforces the exact method, path, query, header, body, and response limits
   before untrusted values cross their relevant seam.
4. Catalogue, routes, attachment mounts, forwarding, admission, and closed responses derive only
   from the one current compiled generation.
5. Protected fixtures independently reject missing, visitor-controlled, forged, expired,
   wrong-issuer, wrong-audience, cross-application, and replayed assertions.
6. Platform admission never grants the restricted fixture's synthetic premium Feature Entitlement,
   and each fixture's principal and state remain application-scoped.
7. Activation and rollback change one complete generation atomically, preserve the last reviewed
   generation after failure, and never mutate Fixture Application State.
8. Every mandatory AP-EVAL-M4 gate passes through `make check` without credentials, network access,
   package installation, browser use, cloud access, external mutation, or mandatory skips.
9. Tests and evidence label in-process direct-call denial, synthetic cryptography, and in-memory
   lifecycle behavior as Fixture evidence rather than network, production-identity, or persistence
   qualification.
10. Finance Assistant and every infrastructure, Terraform, DNS, identity, credential, deployment,
    and Application Adoption path remain unchanged.

Near-complete behavior, a warning-only denial, an undocumented skip, a test against an unreviewed
generation, or a Fixture result presented as Live or Adoption evidence fails AP-M4.

### Required evidence

The pull-request handoff records:

- branch, AP-M3 merge base, evaluated source revision, and final revision;
- one commit and changed-path list for each AP-M4 work package;
- exact commands, working directory, interpreter version, exit status, duration, test count,
  failures, errors, warnings, and skips;
- fixture registration generation and digest, contract and compiler versions, enabled adapter kind,
  and identities expressed only as synthetic labels;
- the requirements, ADRs, and Fixture threat claims covered by each gate;
- security and privacy impact, limitations, and every unresolved Live and Adoption decision; and
- confirmation that no credential, network call, state backend, saved plan, authenticated payload,
  or external mutation was used.

Console output from the revision-scoped deterministic run is sufficient. Generated reports,
screenshots, captured assertion envelopes, interpreter caches, and copied state are not committed as
proof.

### Security and privacy impact

AP-M4 introduces executable parsing, routing, admission, assertion, and application seams for
synthetic inputs. It reduces design ambiguity by exercising their failure behavior, but it creates
no external ingress and processes no real identity or application data. Public test key material is
deliberately non-secret and must never be reused as a credential.

Logs and test diagnostics may contain fixture identifiers, generation digests, outcome codes, and
correlation identifiers. They must not contain assertion envelopes, restricted member sets,
session labels, request bodies, principal maps, entitlement contents, or application state.

### Limitations and deferred work

AP-M4 cannot prove that:

- the Shared Edge is network reachable, correctly deployed, or isolated from direct origin access;
- DNS, TLS, OAuth, IAM, provider signing, key custody, rotation, quotas, or alerts work;
- generation state survives a process restart or concurrent operator change;
- the harness meets availability, latency, throughput, accessibility, or browser requirements; or
- a real application, including Finance Assistant, is compatible with or authorized to adopt the
  platform.

Infrastructure implementation, Live qualification, and each Application Adoption require separate
owner-approved branches, plans, evaluation gates, and evidence after AP-M4 merges.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M4-W1 through AP-M4-W2 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-004 | Fixture (`F`) portions of AP-TM-001 through AP-TM-014 |
| AP-M4-W3 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004 | AP-TM-001 through AP-TM-004, AP-TM-007, AP-TM-009, AP-TM-012, AP-TM-013 |
| AP-M4-W4 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-005 | ADR-003, ADR-004 | AP-TM-004 through AP-TM-006, AP-TM-009, AP-TM-010, AP-TM-013 |
| AP-M4-W5 | AP-PR-001 through AP-PR-006, AP-PR-008, AP-PR-009; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001 through ADR-004 | AP-TM-001 through AP-TM-006, AP-TM-008 through AP-TM-010, AP-TM-014 |
| AP-M4-W6 | AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004 | AP-TM-003, AP-TM-007 through AP-TM-009, AP-TM-013 |
| AP-M4-W7 | AP-PR-008, AP-PR-009; AP-QR-003 through AP-QR-006 | ADR-004 | AP-TM-010, AP-TM-011, AP-TM-014 |

## AP-M5 · Platform infrastructure planning

### Outcome

AP-M5 converts the owner-approved Live decisions into repository authority for the smallest safe
implementation and qualification sequence. It defines what later slices may implement, how state
and operator authority remain exclusive, which actions require explicit approval, and what Live
evidence must prove. AP-M5 produces no Contract, Fixture, Live, or Adoption evidence and authorizes
no external mutation.

The planned sequence deliberately separates:

1. networked provider runtime implementation;
2. Terraform and workflow implementation;
3. qualification-environment deployment and explicit DNS enablement;
4. Live qualification and evidence review; and
5. any later Application Adoption.

Passing AP-M5 means the planning authority is internally consistent and complete enough to propose
those later slices. It does not mean any planned control exists.

### Scope

AP-M5 includes:

- accepted GCP qualification topology and `gcp-cloud-run-v1` attachment decisions;
- Google OIDC Platform Sessions and application-bound ES256 assertion decisions;
- GCS backend roots, GitHub OIDC/Workload Identity Federation, protected-main operation, and
  break-glass authority;
- immutable Registration Generation staging, activation, DNS/TLS sequencing, readback, rollback,
  and retention decisions;
- logging, evidence, incident, privacy, runtime-scaling, budget, cleanup, and cost controls;
- a later-slice delivery sequence with dependencies, acceptance and rejection boundaries;
- a deterministic AP-M5 planning gate and separately defined future Live gates; and
- authority, repository-layout, status, and next-slice handoff updates.

AP-M5 excludes:

- a network listener, Shared Edge runtime, provider adapter, OAuth flow, session store, or signer;
- Terraform files, modules, state, backends, plans, imports, or provider commands;
- GitHub workflow mutation, repository settings, Workload Identity Federation, service accounts,
  IAM bindings, credentials, secrets, or OAuth clients;
- GCP API enablement, resource creation, deployment, DNS/TLS mutation, or live readback;
- committed Live evidence, screenshots, authenticated artifacts, or provider payloads; and
- Finance Assistant requirements, code, infrastructure, Terraform state, DNS, identity, access,
  deployment, migration, or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M5 treatment |
| --- | --- | --- |
| AP-M3 | Merged and Contract-qualified | Preserve Version 1 interfaces and deterministic compiler behavior |
| AP-M4 | Merged and Fixture-qualified on `main` | Preserve fixture evidence and carry every Live limitation forward |
| Requirements and ADR-001 through ADR-004 | Authoritative | Do not weaken ownership, admission, fixture-first, or adoption boundaries |
| Owner Live decisions | Approved | Record them as ADR-005 through ADR-009 and provider-specific design authority |
| Dedicated GCP project | Identified, with no AP-M5 mutation authority | Record project and region as configuration without calling GCP |
| Finance Assistant | Outside the slice | Do not read its state or change its edge, DNS, identity, deployment, or access |

If AP-M4 is absent from `main`, an owner decision conflicts with an accepted requirement, or an
edit would create or mutate an external resource, AP-M5 stops rather than absorbing later work.

### Work packages

#### AP-M5-W1 · Provider and attachment topology

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-005;
- the GCP topology and Cloud Run attachment sections of `docs/03_system_design.md`;
- applicable AP-TM-001 through AP-TM-004, AP-TM-007 through AP-TM-014 boundaries in
  `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects the dedicated project, `us-west1`, qualification hostname, global load
balancer, one Cloud Run edge, typed attachment grammar, same-project fixture boundary, future
cross-project Shared VPC ownership, and explicit DNS action. It implements none of them.

#### AP-M5-W2 · Identity and assertion trust profile

Deliverables update only:

- `GLOSSARY.md` with Platform Session;
- `docs/02_architecture_decision_records.md` with ADR-006;
- the identity sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects Google OIDC, edge-managed sessions, Firestore Native, logout, restricted
membership, KMS ES256 signing, JWKS, lifetime, skew, rotation, caching, and replay posture. Existing
IAP and application-managed Google login remain unchanged pending Application Adoption.

#### AP-M5-W3 · State and operator authority

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-007;
- state and operator sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects state roots and buckets, backend recovery, protected-main operation, federated
identity, revision/plan binding, concurrency, normal local limits, and break-glass authority. It
creates no root, bucket, workflow, repository setting, identity, or state.

#### AP-M5-W4 · Activation, DNS, readback, and rollback

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-008;
- lifecycle sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects content-addressed configurations, immutable edge revisions, the one active
generation pointer, staged activation, explicit DNS/TLS sequencing, cross-layer readback, a
15-minute post-approval rollback objective, and a 24-hour minimum retention window. It performs no
activation, rollback, DNS lookup, or provider operation.

#### AP-M5-W5 · Observability, evidence, incident, and cost controls

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-009;
- data, evidence, and cost sections of `docs/03_system_design.md` and
  `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects minimized seven-day logs, 30-day evidence, owner incident authority, the USD
20 budget response, scale-to-zero bounds, resource sizes, concurrency, streaming duration, service
exclusions, image cleanup, labels, and cost allocation. It creates no sink, bucket, budget, runtime,
alert, or cleanup action.

#### AP-M5-W6 · Delivery plan and repository locations

Deliverables update only:

- `docs/04_implementation_plan.md`;
- `docs/repository_layout.md`.

This package defines AP-M5 acceptance and the later AP-M6 through AP-M9 separation, identifies
implementation inputs that remain unresolved and must not be guessed, and reserves later-owned
locations without creating them.

#### AP-M5-W7 · Evaluation authority

Deliverables update only:

- `docs/05_evaluation_strategy.md`.

This package defines the deterministic AP-EVAL-M5 planning gate and the future AP-EVAL-M6 through
AP-EVAL-M9 claim boundaries. It performs no Live evaluation and pre-fills no success result.

#### AP-M5-W8 · Planning authority validation

Deliverables update only:

- `tests/test_governance.py` and the default `make check` dependency chain only if required.

This package enforces AP-M5 identifiers, traces, later-slice separation, reserved paths, truthful
status, and absence of infrastructure or live mutation. It remains standard-library,
credential-free, deterministic, and non-mutating.

#### AP-M5-W9 · Planning record and next-slice handoff

Deliverables update only after the AP-M5 deterministic gate passes:

- `README.md`, `docs/README.md`, and `prompts/starting_prompt.md`;
- `AGENTS.md` only if its authority routing must change;
- `tests/test_governance.py`; and
- the secret-free pull-request handoff record.

These updates may record AP-M5 as merged planning authority only. They must leave every runtime,
Terraform, deployment, Live, and Adoption claim unavailable and route the next task to AP-M6 only
after this pull request merges.

## AP-M6 · Networked provider runtime implementation

### Outcome

AP-M6 implements and deterministically tests the networked Shared Edge through the approved ASGI
interface:

```text
create_app(runtime_configuration, adapters) -> ASGI application
```

The module owns the complete request pipeline behind that interface. Internal provider seams accept
production and deterministic fake adapters; callers do not assemble catalogue, routing, admission,
identity, target, forwarding, limit, failure, or logging behavior themselves. The separately
consumable application verifier exposes one compact assertion-verification interface and grants no
application permission.

Passing AP-M6 provides repository implementation evidence only. It does not prove a provider
resource, IAM grant, Google login, Cloud Run origin, DNS record, deployment, availability, cost, or
Live behavior.

### Scope

AP-M6 includes:

- the Python 3.12-or-newer Starlette/Uvicorn runtime and locked dependency environment;
- immutable generation loading and digest binding through production and fake storage adapters;
- the generation-derived root catalogue, reserved platform paths, prefix routing, and closed
  default behavior;
- Google OIDC and Firestore Platform Session adapters plus deterministic fakes;
- ES256 assertion creation, KMS signing, JWKS publication, rotation overlap behavior, and the
  direct-entry application verifier;
- `gcp-cloud-run-v1` metadata resolution, readiness and ownership checks, service-identity target
  transport, and deterministic provider fakes;
- bounded HTTP, upload, download, SSE, and WebSocket forwarding under the approved
  `qualification-v1` limits;
- generation status/readback, failure isolation, correlation identifiers, completion outcomes, and
  required redaction; and
- deterministic unit, adapter-contract, ASGI, loopback integration, extraction, and regression
  tests under AP-EVAL-M6.

AP-M6 excludes:

- a registration submission endpoint, registration database, operator control plane, mutable
  generation pointer, or unreviewed route source;
- Terraform, a backend, state, saved plan, workflow with cloud authority, repository setting,
  credential, secret value, provider call, resource creation, IAM mutation, DNS change, identity
  configuration, deployment, or authenticated evidence;
- a real Google account, OAuth client, Firestore database, KMS key, GCS object, Cloud Run service,
  load balancer, certificate, log bucket, budget, or alert;
- distributed rate limiting, WAF, CDN, load, availability, browser, or Live claims; and
- Finance Assistant code, configuration, state, hostname, identity, access, deployment, migration,
  or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M6 treatment |
| --- | --- | --- |
| AP-M3 and AP-M4 | Merged and passing | Preserve Version 1 contracts, compiler behavior, Fixture evidence, and regression gates |
| AP-M5 | Merged and planning-validated | Implement only the runtime portion of the selected topology and trust profiles |
| Runtime profile | Owner-approved in AP-M6-W1 | Use Starlette/Uvicorn, the locked dependency policy, and exact `qualification-v1` limits |
| Provider access | Unavailable and prohibited | Exercise production adapter logic only through deterministic fake transports and metadata |
| Terraform and deployment | Deferred to AP-M7 and AP-M8 | Create no infrastructure path, workflow authority, or external mutation |
| Application Adoption | Unavailable | Use only independent Fixture Applications and synthetic identities |

An unmet dependency stops the affected package. A fixture default, provider default, local
credential, Finance configuration, or discussion history may not fill a missing input.

### Work packages

#### AP-M6-W1 · Runtime authority and limits

Update `docs/03_system_design.md`, this plan, `docs/05_evaluation_strategy.md`, and
`docs/06_threat_model.md` to approve:

- the deep ASGI module interface and internal provider seams;
- Python, Starlette, Uvicorn, dependency declaration, lock, and installation boundaries;
- exact header, body, timeout, concurrency, stream, rate, and rejection behavior; and
- the implementation, evidence, and later-slice exclusions.

This package creates no runtime, dependency manifest, reserved implementation directory, or cloud
configuration. Owner acceptance of its exact values is required before AP-M6-W2.

#### AP-M6-W2 · Locked runtime foundation

Add `pyproject.toml`, `uv.lock`, the smallest functional `edge/` package, an ASGI application
factory, typed runtime settings and adapter bundle, a closed-default request result, and the
project-local test target. Update only the existing path-scoped parent CI wrapper needed to
synchronize the frozen environment while the project is colocated.

The external module interface remains `create_app(runtime_configuration, adapters)`. Internal
interfaces are not re-exported. Tests call the ASGI interface and prove that dependency setup is
separate from the network-free `make check` command.

#### AP-M6-W3 · Immutable generation loading

Implement the generation-source seam, GCS production adapter, deterministic fake, exact object and
content digest verification, Version 1 compiled-configuration validation, startup binding, and
failure behavior. Loading one generation never discovers a bucket, follows a mutable registration
source, compiles an unreviewed set, or changes the current provider pointer.

#### AP-M6-W4 · Catalogue and registered routing

Implement escaped root-catalogue rendering, explicit platform-reserved paths, exact longest-prefix
selection within the already compiled non-overlapping route set, mount rewriting, staged/suspended/
retired exclusion, and closed unknown or malformed behavior. Framework routing contains no copy of
registration-derived application routes.

#### AP-M6-W5 · Sessions and admission

Implement Google OIDC authorization-code-with-PKCE flow, opaque host-only Platform Sessions,
Firestore production and in-memory fake stores, public optional identity, authenticated and
restricted admission, logout, absolute expiry, return-location validation, and fail-closed provider
errors. No Google access or refresh token is retained, and email never becomes an admission key.

#### AP-M6-W6 · Assertion and application verification

Implement the Version 1 ES256 assertion envelope, KMS production and deterministic fake signers,
application-specific audiences, 60-second lifetime, 30-second skew, versioned key identifiers,
JWKS publication, overlap/cache behavior, visitor-header stripping, and the application-side
verifier. Tests cover malformed, expired, wrong-issuer, wrong-audience, unknown-key, and stale-key
results without a real key or identity.

#### AP-M6-W7 · Cloud Run attachment resolution

Implement strict `gcp-cloud-run-v1` URN parsing, Cloud Run production metadata and deterministic fake
adapters, exact project/region/service matching, readiness, declared owner, edge-caller grant, and
application-audience checks. A registration-supplied URL, credential, state address, provider query,
cross-application result, or unresolved target fails closed.

#### AP-M6-W8 · Bounded application proxy

Implement service-identity target transport, path and query preservation, hop-by-hop and identity
header handling, uploads, downloads, buffered and streamed HTTP, SSE, WebSocket bridging,
cancellation, timeout, size, rate, and concurrency enforcement, and protocol-appropriate closed
errors. Tests use loopback only inside the test process and never contact an external address.

#### AP-M6-W9 · Status, readback, failure, and redaction

Implement operator-authorized generation status and readback, correlation identifiers, one
structured completion event per request or streaming connection, coarse outcomes, latency, adapter
health, failure isolation, and the approved prohibited-data list. Status reports repository and
generation facts only; it cannot activate, roll back, mutate, or reveal secrets or identity data.

#### AP-M6-W10 · Runtime qualification gate

Implement the complete AP-EVAL-M6 matrix in behavior-named tests and the default `make check`
dependency chain. Enforce all AP-M6 identifiers and traces, exact limits, adapter parity, extraction,
dependency locking, no external network, no credentials, no reserved later-slice paths, no provider
or repository mutation, and all AP-M3/AP-M4 regressions.

#### AP-M6-W11 · Runtime record and AP-M7 handoff

After AP-EVAL-M6 passes, update `README.md`, `docs/README.md`, `prompts/starting_prompt.md`, prompt
index, governance assertions, and the secret-free pull-request handoff. Record only locally
implemented runtime behavior. Leave provider deployment, Terraform, Live, and Adoption claims
unavailable and route the next task to AP-M7 only after the AP-M6 pull request merges.

### Ordered delivery

AP-M6 work proceeds in work-package order. Each package is a separately reviewable commit and adds
its tests with its behavior. No package may defer failing behavior tests to AP-M6-W10, weaken an
existing gate, or introduce a later-slice file because its interface is known.

### Acceptance criteria

AP-M6 is accepted only when all of the following are true:

1. The owner has accepted AP-M6-W1's exact framework, dependency, and limit profile.
2. The Shared Edge presents one small ASGI interface and keeps provider adapters behind internal
   seams with production and deterministic fake implementations.
3. One immutable compiled generation exclusively derives catalogue, platform paths, application
   routing, admission, attachments, and status facts.
4. Public, authenticated, and restricted requests, session lifecycle, logout, assertion delivery,
   application verification, and every fail-closed identity path pass AP-EVAL-M6.
5. Cloud Run references resolve only through the allow-listed adapter and exact declared resource;
   no arbitrary URL, discovery, cross-application reuse, or ownership transfer is possible.
6. HTTP, uploads, downloads, SSE, and WebSocket behavior enforces every approved numeric limit,
   closes or cancels failed work, and isolates application failures.
7. Logs, status, errors, and test output exclude assertions, sessions, restricted members, request
   and response bodies, visitor metadata, application data, secrets, credentials, and state.
8. `make check` is deterministic, credential-free, external-network-free, non-mutating,
   extraction-safe, and mandatory-skip-free in an already synchronized locked environment.
9. The branch contains no Terraform, state, plan, credential, secret value, cloud call, repository
   setting change, DNS or identity mutation, deployment, or generated Live evidence.
10. Finance Assistant and all existing applications and Integration Drafts remain unchanged and
    inactive.

Near-complete runtime behavior, an untested production adapter, a fake-only hypothetical seam, an
implicit framework default, a provider lookup during tests, or a Live claim fails AP-M6.

### Required evidence

The pull-request handoff records branch and AP-M5 merge base, evaluated and final revisions, all
AP-M6 commits and changed paths, frozen dependency digest, Python version, exact commands, duration,
test counts and outcomes, identifier coverage, security/privacy impact, limitations, and unresolved
AP-M7/AP-M8 inputs. It confirms that tests used only deterministic adapters and process-local
loopback, that no external mutation occurred, and that Finance Assistant remained unchanged.

Console output is sufficient. The branch commits no credential, browser state, provider response,
request payload, generated report, screenshot, or Live evidence bundle.

### Security and privacy impact

AP-M6 introduces executable network parsing, identity, signing, provider-reference, proxy, and
logging code. Numeric limits, closed failure, header stripping, audience binding, application
isolation, fake-provider tests, and strict redaction reduce its attack surface. No production
identity, member set, application payload, key, token, session, or visitor address enters committed
test data or evidence.

The runtime cannot prove provider IAM, direct-origin denial, key custody, session persistence,
distributed rate limiting, availability, or cost. Those controls remain unqualified until their
later provider and Live gates pass.

### Limitations and unresolved inputs

AP-M6 does not deploy or call its production adapters. OAuth client values, secret references,
bucket names, object generations, key versions, Firestore database, Cloud Run services, caller
identity, IAM grants, trusted load-balancer metadata, repository federation, and initial Live
Registration Set remain AP-M7/AP-M8 inputs. Exact provider behavior, direct-origin denial,
multi-instance effects, browser login, accessibility, load, recovery, and cost remain AP-M9 Live
evidence.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M6-W1, AP-M6-W2 | AP-PR-001 through AP-PR-008; AP-QR-002 through AP-QR-006 | ADR-001 through ADR-006, ADR-008, ADR-009 | AP-TM-001 through AP-TM-007, AP-TM-009 through AP-TM-013 |
| AP-M6-W3, AP-M6-W4 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007; AP-QR-002, AP-QR-003, AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-005, ADR-008 | AP-TM-001, AP-TM-002, AP-TM-007, AP-TM-011, AP-TM-013 |
| AP-M6-W5, AP-M6-W6 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-006 | ADR-003, ADR-004, ADR-006, ADR-009 | AP-TM-004 through AP-TM-006, AP-TM-010 through AP-TM-013 |
| AP-M6-W7, AP-M6-W8 | AP-PR-002, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-008 | AP-TM-002 through AP-TM-005, AP-TM-007 through AP-TM-013 |
| AP-M6-W9 through AP-M6-W11 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |

`AP-PR-009`, `AP-QR-001`, `ADR-007`, `AP-TM-008`, and `AP-TM-014` are negative constraints in
AP-M6: they preserve explicit adoption and exclusive state ownership and do not authorize state or
application mutation.

## Later delivery sequence

AP-M6 authorizes no later work by itself. Each item below requires a new owner-approved branch,
plan refinement, evaluation gate, merge, and clean-main handoff.

### AP-M7 · Terraform and workflow implementation

Implement the bootstrap, platform, and per-fixture roots; reusable modules; static policy checks;
GitHub workflow templates; extraction inputs; secret references; and deterministic configuration
tests. AP-M7 may perform local formatting, validation, and credential-free tests only. It does not
initialize a backend, run an authenticated plan, create a credential, call GCP, mutate repository
settings, or deploy.

Exact globally unique bucket names, dedicated repository and workflow subjects, DNS zone resource,
OAuth client references, notification destination, and initial Registration Set values are operator
inputs resolved through reviewed configuration rather than reusable module assumptions.

### AP-M8 · Non-production qualification deployment

After repository extraction and AP-M6/AP-M7 merges, use separately approved operator actions to
configure repository protection and federation, bootstrap backends, run authenticated plans,
deploy the platform and Fixture Application resources, and perform the separately approved
`apps-staging.comfforts.com` DNS/TLS action. Deployment evidence proves only that named resources
exist and read back; it does not make AP-EVAL-M9 pass.

AP-M8 must stop before any Finance Assistant resource, existing hostname, real application project,
or Application Adoption action enters scope.

### AP-M9 · Live qualification

Execute the approved Live gates against the exact deployed revision and Registration Generation.
Exercise provider routing, identity, IAM, direct-origin denial, state ownership, failure isolation,
activation, rollback, logging, retention, drift, cost controls, and recovery. Store only approved
redacted evidence and obtain owner acceptance before calling the platform Live-qualified.

### Later Application Adoption

Only after AP-M9 is accepted may a consuming application propose adoption through its own
requirements, decisions, contracts, implementation, state transition, cutover, rollback, and
release authority. Finance Assistant remains unchanged until that independent process approves it.

### Ordered delivery

AP-M5 work proceeds in this order:

1. approve provider and attachment topology;
2. approve the identity and assertion trust profile;
3. approve state and operator authority;
4. approve activation, DNS, readback, and rollback behavior;
5. approve observability, evidence, incident, and cost controls;
6. approve the delivery plan and repository locations;
7. approve evaluation authority;
8. enforce the complete deterministic planning gate; and
9. reconcile truthful status and the next-slice handoff.

Each work package is a separate small commit reviewed before the next package is edited. A later
package may correct an inconsistency or complete traceability, but it may not add provider runtime,
Terraform, a workflow with live authority, a credential, or external mutation.

### Acceptance criteria

AP-M5 is accepted only when all of the following are true:

1. Every decision traces to AP-PR-001 through AP-PR-009, AP-QR-001 through AP-QR-006, ADR-001
   through ADR-009, and the applicable AP-TM-001 through AP-TM-014 boundary.
2. The design defines provider topology, attachment ownership, identity trust, state roots,
   operator authority, activation, DNS/TLS, readback, rollback, observability, incident response,
   cost control, retention, and later-slice boundaries without claiming implementation.
3. AP-M6, AP-M7, AP-M8, AP-M9, and Application Adoption are distinct review and merge boundaries;
   no later slice inherits mutation authority merely because AP-M5 is accepted.
4. Every selected cloud value remains environment configuration rather than a reusable contract or
   Finance-derived assumption.
5. Exact unresolved implementation inputs are named and block only their dependent later package;
   they are not silently filled from fixture code, provider defaults, or discussion history.
6. The default `make check` remains deterministic, credential-free, network-free, non-mutating,
   extraction-safe, and mandatory-skip-free.
7. The branch contains no provider runtime, Terraform configuration, workflow with cloud authority,
   state, saved plan, credential, secret, cloud call, DNS change, identity change, deployment, or
   generated Live evidence.
8. Finance Assistant and every existing application resource, state, hostname, identity, access
   rule, deployment, and integration package remain unchanged and inactive.
9. Status and handoff text call AP-M5 planning authority only and leave Contract, Fixture, Live,
   and Adoption evidence classes unchanged.

Near-complete documentation, a missing owner decision disguised as a default, a cloud lookup in the
default gate, or any operational claim fails AP-M5.

### Required evidence

The pull-request handoff records:

- branch, AP-M4 merge base, evaluated source revision, and final revision;
- one commit and changed-path list for every AP-M5 work package;
- exact verification command, working directory, interpreter version, duration, test count,
  failures, errors, warnings, and skips;
- requirements, ADRs, threats, and proposed later gates covered;
- security and privacy impact, limitations, and unresolved implementation inputs;
- confirmation that no `infrastructure/`, runtime, live registration, state, saved plan, credential,
  provider call, repository mutation, DNS action, deployment, or authenticated artifact was added;
  and
- confirmation that Finance Assistant and every Integration Draft remain unchanged and inactive.

This is planning evidence for review, not a new evidence class and not Live evidence. Console output
from the deterministic gate is sufficient; generated reports and screenshots are not committed.

### Security and privacy impact

AP-M5 reduces future ambiguity by selecting explicit trust, state, operation, retention, and cost
boundaries. It introduces no runtime data flow. It records project identifiers, resource-reference
grammar, and non-secret operational settings, but no real restricted membership, OAuth client,
credential, key, state, plan, log, IP address, assertion, provider response, or application data.

The selected controls remain declarations until later implementation and Live evidence prove them.
Their presence must not be used to weaken existing Finance Assistant access or justify migration.

### Limitations and unresolved inputs

AP-M5 does not prove that any cloud resource, identity, state backend, route, certificate, session,
assertion, log, alert, budget, rollback, or recovery behavior exists. It does not qualify latency,
availability, throughput, browser behavior, accessibility, or a real application.

The following exact inputs remain required at their named later boundary:

| Input | Required before |
| --- | --- |
| Dedicated GitHub organization, repository, workflow subjects, protected environment, and repository settings | AP-M7 federation implementation and AP-M8 deployment |
| Globally unique state, configuration, log, and evidence bucket names | AP-M7 environment configuration |
| DNS managed-zone resource and exact separately approved record transaction | AP-M7 environment configuration and AP-M8 DNS action |
| OAuth client identifiers, redirect registration, secret references, and owner notification destination | AP-M7 environment configuration and AP-M8 deployment |
| Initial live Fixture Registration Set, restricted synthetic members, image digests, and attachment resource references | AP-M6/AP-M7 implementation and AP-M8 deployment |
| Application-specific principals, data, providers, entitlements, state transfer, and cutover | Each Application Adoption |

These are unavailable inputs, not permission to query a provider, copy Finance configuration, or
invent a value in AP-M5.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M5-W1 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-003, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005 | AP-TM-001 through AP-TM-004, AP-TM-007 through AP-TM-014 |
| AP-M5-W2 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-003, ADR-004, ADR-005, ADR-006 | AP-TM-004 through AP-TM-006, AP-TM-009, AP-TM-010, AP-TM-013 |
| AP-M5-W3 | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-007 | AP-TM-007 through AP-TM-014 |
| AP-M5-W4 | AP-PR-001 through AP-PR-005, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-008 | AP-TM-002 through AP-TM-005, AP-TM-007 through AP-TM-014 |
| AP-M5-W5 | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001 through ADR-004, ADR-009 | AP-TM-001, AP-TM-004, AP-TM-005, AP-TM-007 through AP-TM-014 |
| AP-M5-W6 through AP-M5-W9 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |
