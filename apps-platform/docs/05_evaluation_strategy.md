# App Platform evaluation strategy

Version 0.1 | Status: deterministic evaluation authority for AP-M3 only

This document defines how delivery item 3, AP-M3, is evaluated. It does not qualify a Shared Edge,
catalogue runtime, identity provider, Application Attachment, Fixture Application, cloud resource,
or consuming application.

Plan: [AP-M3 implementation plan](04_implementation_plan.md)

Design: [App Platform system design](03_system_design.md)

Threats: [App Platform threat model](06_threat_model.md)

## AP-EVAL-M3 · System-design-and-contracts gate

### Evaluation claim

A passing AP-EVAL-M3 result means only that the repository revision contains internally consistent
App Platform design authority, Version 1 machine contracts, and deterministic offline validation
that meet AP-M3's acceptance criteria.

It does not mean the platform is deployed or runtime-qualified. It provides Contract (`C`) evidence
only. Fixture (`F`), Live (`L`), and Adoption (`A`) evidence remain unavailable.

### Evaluation environment

The gate runs from the App Platform project root before and after repository extraction. While the
project is colocated, either of these entry points is authoritative:

```bash
make check
make -C apps-platform check
```

One invocation from the appropriate root is sufficient when both resolve to the same project-local
target. The command must:

- require only a supported Python 3 interpreter and the Python standard library;
- perform no package installation or network access;
- require no cloud account, provider, browser, identity, credential, or secret;
- mutate no external state and create no committed artifact;
- use only project-relative paths; and
- return nonzero on any failed or skipped mandatory gate.

Ordinary ignored interpreter caches are not evidence and must not be required for success.

## Gate structure

### AP-EVAL-M3-01 · Authority and trace integrity

Verify that:

- the authority reading order includes requirements, accepted ADRs, system design, implementation
  plan, evaluation strategy, threat model, and repository layout in precedence order;
- all `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-M3-*`, `AP-EVAL-M3-*`, and `AP-TM-*` identifiers are unique
  within their authority and every referenced identifier exists;
- public terms use the canonical glossary definitions;
- Integration Drafts remain outside the authority chain; and
- status text distinguishes documented, implemented, deployed, and qualified behavior.

Expected evidence: deterministic governance tests over committed Markdown and machine-contract
paths. Documentation presence alone cannot pass any behavioral gate.

### AP-EVAL-M3-02 · Schema integrity and compatibility

Verify all five Version 1 schemas:

- parse as duplicate-key-free JSON;
- declare JSON Schema Draft 2020-12 and a unique stable URN identifier;
- resolve every reference locally inside `contracts/`;
- require an explicit contract version and reject an unsupported major version;
- bound every string, array, and object whose size can be attacker-controlled;
- close objects against unknown properties unless a documented extension point exists;
- contain no remote reference, credential, provider command, Terraform state address, Finance path,
  containing-repository path, or secret-like payload; and
- follow the compatibility rules in `contracts/README.md`.

The schema documents and the reference validator are evaluated against the same test-vector
manifest. A case accepted by one and rejected by the other fails the gate.

### AP-EVAL-M3-03 · Deterministic successful compilation

For every valid vector, verify that the compiler:

- accepts the declared predecessor, Registration Set, and platform configuration;
- returns no violations;
- produces the expected complete Compiled Shared Edge Configuration;
- produces the expected State Ownership Manifest;
- orders applications, catalogue entries, routes, mounts, admission members, and ownership entries
  canonically;
- produces byte-identical canonical output and digest on repeated execution; and
- does not depend on input object order, current time, random values, absolute paths, environment
  identity, network state, or containing-repository files.

Valid vectors must include public, authenticated, and restricted registrations; listed and
unlisted catalogue behavior; multiple applications; multiple attachment mounts; staged and active
states; a content-only application update; a stable attachment reference across an application
release; and an approved attachment replacement generation.

### AP-EVAL-M3-04 · Fail-closed route, catalogue, and attachment validation

Invalid vectors must cover at least:

- duplicate or near-matching application prefixes;
- root, `/_platform`, and `/.well-known` conflicts;
- uppercase, trailing slash, empty segment, dot segment, percent encoding, encoded separator,
  query, fragment, control character, and Unicode-lookalike paths;
- duplicate or ambiguous attachment mounts;
- unsupported forwarding modes or adapter kinds;
- arbitrary URLs, credentials, secret-like values, state addresses, or wrong-owner references;
- unsafe, oversized, marked-up, or private catalogue fields; and
- unknown registration or attachment properties.

Each case must return its declared ordered violation codes, produce no compiled output, perform no
external lookup, and leave its input files unchanged.

This gate supplies Contract evidence for AP-TM-001, AP-TM-002, AP-TM-003, and the applicable
configuration portion of AP-TM-012. It does not prove runtime route parsing, rendering, ingress, or
provider behavior.

### AP-EVAL-M3-05 · Admission and identity contract separation

Verify that:

- the only Admission Modes are `public`, `authenticated`, and `restricted`;
- restricted membership uses exact issuer-and-subject values and never email;
- owner-only is represented as restricted membership rather than a separate mode;
- authenticated and restricted registrations require compatible identity and audience data;
- public registrations do not require or invent an identity;
- the identity schema requires contract version, issuer, subject, audience, issued time, expiry,
  and correlation identifier within approved bounds;
- wrong-type, missing, unknown, mutable-owner, Feature Entitlement, product-role, and provider-right
  fields are rejected; and
- compiled output keeps admission separate from application authorization.

This is shape and semantic evidence only. Signature verification, header stripping, expiry,
wrong-audience rejection, replay handling, and direct-origin denial require Fixture and Live gates.

### AP-EVAL-M3-06 · Lifecycle, update, rollback-input, and ownership validation

Verify that:

- a new application begins staged;
- only the transitions authorized by the system design are accepted;
- retired registrations are immutable tombstones and retain their identifiers and prefixes;
- a stale or missing predecessor digest is rejected;
- catalogue, route, admission, attachment, and ownership outputs are generated as one unit;
- an application release behind an unchanged attachment requires no registration difference;
- a platform-facing attachment change requires a new Registration Generation;
- valid attachment replacement retains distinct old and new application-owned references for the
  future acceptance and rollback sequence;
- each canonical resource reference has exactly one declared owner; and
- suspension, retirement, and rollback inputs never contain an instruction to destroy Application
  State.

This gate supplies the Contract portions of AP-TM-007 and AP-TM-008. It cannot prove provider
transactions, state readback, rollback execution, or destructive-action protection.

### AP-EVAL-M3-07 · Security, privacy, and isolation declarations

Verify that contracts and vectors contain:

- synthetic identities and application identifiers only;
- no credential, signing key, OAuth secret, unredacted assertion, real restricted membership,
  provider payload, application data, Terraform state, saved plan, or authenticated artifact;
- application-scoped audiences and ownership identifiers;
- no path by which an application receives Platform State write authority;
- no platform field for Application Principals or Feature Entitlements; and
- explicit unavailable states where later provider or runtime evidence is required.

Secret-pattern checks are defense in depth and do not certify that an arbitrary value is safe. A
positive match fails the committed-artifact gate; a negative match does not replace review.

### AP-EVAL-M3-08 · Extraction and non-mutation

Verify that:

- the contract loader and validator resolve from the App Platform project root;
- tests copy the contract layer to a temporary directory and exercise validation without importing
  Finance Assistant or another containing-repository path;
- `Makefile` contains no cloud, DNS, Terraform apply, provider CLI, credential, browser, or live
  mutation command in the default check dependency chain;
- validation does not modify contract inputs or tracked files; and
- ignored caches and temporary directories are not treated as evidence.

The temporary-copy test validates the contract layer's extraction boundary. Full repository
extraction, root workflow recreation, and repository settings remain later operator work.

### AP-EVAL-M3-09 · Scope and truthful handoff

Verify that the AP-M3 change:

- adds no `fixtures/` implementation, `infrastructure/terraform/` content, cloud resource, DNS
  record, identity configuration, credential, or runtime;
- leaves Finance Assistant requirements, code, infrastructure, state, deployment, and access model
  unchanged;
- keeps every Finance integration document labelled inactive and non-authoritative;
- records AP-M3 as contract implementation only after the complete gate passes; and
- directs the next task to propose delivery item 4 planning after AP-M3 merges, without treating the
  current branch or pull request as that merge.

## Test-vector manifest

`contracts/test-vectors/manifest.v1.json` is the reviewed index of deterministic cases. Each entry
must declare:

- stable case identifier and description;
- input schema and relative input paths;
- predecessor path when applicable;
- expected acceptance or rejection;
- expected compiled and ownership paths for acceptance;
- expected ordered violation codes and paths for rejection;
- requirements, decisions, and threat identifiers covered; and
- an explicit evidence class of `C`.

The manifest contains no executable command, absolute path, environment-specific identifier, or
expected live result. A vector not indexed by the manifest is test support, not acceptance evidence.

## Determinism and mutation checks

Tests must isolate nondeterminism by:

- injecting no clock, random generator, network client, provider client, or credential source;
- comparing canonical bytes and digests across repeated execution;
- permuting non-semantic JSON object order where the contract permits it;
- running with a minimal environment and a temporary working directory for extraction checks;
- hashing or byte-comparing input vectors before and after validation; and
- treating an unexpected file creation, external call, warning-only rejection, or skipped mandatory
  case as failure.

The AP-M3 reference compiler may read caller-supplied contract files but exposes no file-writing
interface. It returns in-memory values, and tests do not write generated artifacts into the
repository.

## Threat coverage boundary

| Threats | AP-EVAL-M3 claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Contract shape, semantic rejection, safe projection, and inert attachment references |
| AP-TM-004 | Declaration of protected-ingress and identity requirements only; bypass remains unqualified |
| AP-TM-005 | Identity claim shape, issuer-subject membership, and audience binding only; cryptography remains unqualified |
| AP-TM-006 | Platform contracts exclude Feature Entitlements and product roles |
| AP-TM-007 | Generation, transition, atomic-output, and rollback-input validation |
| AP-TM-008 | Declared exclusive ownership and cross-state reference validation only |
| AP-TM-009 | Unique routes, attachments, audiences, and owners in compiled configuration |
| AP-TM-010 | Prohibited committed fields, synthetic vectors, and secret-pattern defense in depth |
| AP-TM-011 | Deterministic revision-bound inputs and extraction-safe default checks only |
| AP-TM-012 | Contract and compiler size bounds only; runtime abuse and cost remain unqualified |
| AP-TM-013 | Fail-closed declarations only; dependency failure remains unqualified |
| AP-TM-014 | Authority labels and absence of fixture or adoption behavior |

## Pass, fail, and skip semantics

AP-EVAL-M3 passes only when:

- every mandatory gate passes in one revision-scoped run;
- expected test counts and vector counts match the manifest;
- there are zero failures, errors, unexpected warnings, and skips;
- the working tree contains no unexpected generated or sensitive artifact; and
- manual review confirms the declared scope and unresolved decisions.

Any mandatory failure, error, skip, schema/validator disagreement, nondeterministic output, external
dependency, unreviewed generated file, secret-like payload, missing trace, or false runtime claim
fails AP-EVAL-M3. A known limitation is recorded as unavailable; it is not converted into a skip or
passing assertion.

## Required evaluation evidence

The AP-M3 pull-request handoff records:

- evaluated commit and contract versions;
- exact command and working directory;
- interpreter version;
- test and vector counts;
- pass, failure, error, warning, and skip counts;
- duration when reported by the test runner;
- changed and evaluated artifact paths;
- Contract threat coverage and all unavailable `F`, `L`, and `A` evidence;
- security/privacy impact and unresolved decisions; and
- confirmation that no credential or external mutation was used.

Evidence reports actual output. It must not pre-fill a success result, omit a failed command, or
claim runtime qualification from documentation, schemas, or static configuration.

## Limitations

AP-EVAL-M3 does not perform load, browser, accessibility, cryptographic, network, cloud, DNS, TLS,
IAM, OAuth, Terraform, provider, runtime, direct-origin, or application-product testing. It does not
qualify availability, cost controls, logging, incident response, migration, or rollback execution.

Those gates require separately approved plans after AP-M3 merges. Finance Application Adoption
requires Finance-owned authority and evidence in addition to qualified platform behavior.
