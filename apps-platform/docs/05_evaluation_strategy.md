# App Platform evaluation strategy

Version 0.2 | Status: deterministic evaluation authority for AP-M3 and AP-M4

This document preserves how delivery item 3, AP-M3, is evaluated and defines the Fixture (`F`) gate
for delivery item 4, AP-M4. AP-EVAL-M4 qualifies only the selected in-process harness. It does not
qualify a live Shared Edge, provider identity, cloud resource, or consuming application.

Plan: [App Platform implementation plan](04_implementation_plan.md)

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

## AP-EVAL-M4 · Deterministic-fixtures gate

### Evaluation claim

A passing AP-EVAL-M4 result means only that the evaluated repository revision implements the
in-process Deterministic Reference Edge and three synthetic Fixture Applications according to
AP-M4. It provides Fixture (`F`) evidence for the behaviors explicitly named below.

It does not mean the platform is deployed, network reachable, persistent, production-secure, or
ready for a real application. Live (`L`) and Adoption (`A`) evidence remain unavailable. AP-EVAL-M3
continues to own Contract (`C`) evidence, and its implemented contract regression checks must pass
in the same `make check` run. AP-M3's historical no-fixture scope gate is not reinterpreted as a ban
on the separately authorized AP-M4 implementation.

### Evaluation environment

AP-EVAL-M4 runs from the App Platform project root using the same extraction-safe entry points:

```bash
make check
make -C apps-platform check
```

`make check` must include `fixture-check` after governance and contract checks. The complete command
uses only a supported Python 3 interpreter and its standard library. It performs no installation,
network access, socket bind, browser automation, credential read, environment secret read, cloud
access, external mutation, or committed artifact generation. The harness itself launches no
subprocess; the extraction check may launch an isolated standard-library Python interpreter from a
temporary project copy, as AP-EVAL-M3 already requires.

The harness opens no listening socket. There is no registration API or database; tests supply
reviewed Registration Sets directly to the in-memory activation interface.

Tests use an injected clock, deterministic correlation-identifier source, explicit synthetic
session map, public test key material, immutable requests, and separately constructed in-memory
Platform and Fixture Application State. An unexpected external dependency fails the gate.

### AP-EVAL-M4-01 · Authority, trace, and scope integrity

Verify that:

- every `AP-M4-W*` and `AP-EVAL-M4-*` identifier is unique, complete, and traces to existing
  requirements, decisions, design sections, and threats;
- AP-M3 Contract evidence remains distinct and continues to pass;
- the documented fixture limits and identity profile match executable constants and tests;
- no Integration Draft or Finance artifact is loaded as fixture input; and
- status text distinguishes designed, implemented, Fixture-qualified, Live-qualified, and adopted.

Expected evidence: deterministic governance tests and the complete gate. Documentation presence
alone cannot pass a behavioral AP-EVAL-M4 gate.

### AP-EVAL-M4-02 · Registration, adapter binding, and atomic activation

Using independent fixture registration files, verify that:

- all three fixtures enter through a complete Version 1 Registration Set and the AP-M3 compiler;
- only the reviewed `fixture-in-process-v1` kind is enabled for the harness;
- every resource reference exactly matches its application and attachment identifier;
- the compiled attachment resolves only through the explicitly supplied read-only map;
- a wrong kind, malformed reference, absent target, owner mismatch, or stale predecessor rejects
  activation before the current-generation pointer changes; and
- successful activation installs catalogue, routes, admission, attachments, and ownership as one
  generation.

This gate proves the Fixture portions of AP-TM-003, AP-TM-007, AP-TM-008, AP-TM-009, and AP-TM-011.
It does not prove a provider resource, IAM identity, state backend, or deployment transaction.

### AP-EVAL-M4-03 · Catalogue, route, mount, and forwarding behavior

Verify through `handle(request) -> response` that:

- `/` returns deterministic UTF-8 HTML with only active, listed fixtures in canonical order;
- catalogue titles and summaries are literal escaped text and every link is the registered prefix;
- exact prefixes and segment-bounded subpaths route to only their registered fixture;
- longest segment-bounded mount selection and all three Version 1 forwarding modes behave as
  compiled;
- near-prefixes, reserved paths, malformed paths, encoded separators, dot segments, staged,
  suspended, retired, and unmatched paths return closed responses; and
- an unavailable attachment fails only the selected fixture and never falls through to another.

This gate supplies Fixture evidence for AP-TM-001, AP-TM-002, AP-TM-003, AP-TM-009, and AP-TM-013.
It does not qualify provider path decoding, browser behavior, network routing, or availability.

### AP-EVAL-M4-04 · Admission, header stripping, and assertion delivery

Verify that:

- public admission succeeds without identity and does not invent an Application Principal;
- authenticated admission rejects a missing or unknown synthetic session;
- restricted admission requires the exact registered synthetic issuer-and-subject pair;
- a visitor-supplied `X-Comfforts-Verified-Identity` value is removed before attachment invocation;
- a protected attachment receives only a newly issued assertion for its own audience after
  successful admission; and
- authentication and restricted-denial responses reveal no member list, assertion, attachment
  reference, principal, entitlement, or application state.

This gate supplies the edge-side Fixture portions of AP-TM-004, AP-TM-005, AP-TM-006, AP-TM-009,
and AP-TM-010. It does not qualify OAuth, a production identity provider, key management, or network
origin isolation.

### AP-EVAL-M4-05 · Independent application verification and authorization

Call protected fixture entry points directly and verify rejection of:

- a missing, malformed, unsigned, wrong-key, or visitor-controlled assertion;
- a wrong contract version, issuer, subject shape, or application audience;
- an assertion issued in the future, expired, or longer than 60 seconds;
- a cross-application assertion; and
- a replayed correlation identifier or a new assertion when the 256-entry store has no expired
  capacity.

Then verify that a valid assertion derives an immutable application-scoped principal, while the
restricted fixture independently denies the synthetic premium Feature Entitlement to an admitted
principal who lacks it. Application-side verification must not consult platform membership or
another fixture's state.

This gate supplies assertion and authorization-separation Fixture evidence for AP-TM-004 through
AP-TM-006, AP-TM-009, and AP-TM-010. It cannot prove key secrecy, distributed replay defense,
provider rights, or a real application's authorization.

### AP-EVAL-M4-06 · State and cross-application isolation

Verify that:

- each fixture is constructed with a distinct state object, principal map, entitlement policy,
  verifier, and replay store;
- a request, failure, identity, or state mutation in one fixture does not alter another fixture;
- the reference edge holds only compiled references and the read-only adapter map, not application
  data or write authority;
- no fixture can change the current generation or another attachment mapping; and
- generation activation, suspension, retirement, and rollback never mutate or delete fixture state.

This gate supplies Fixture evidence for AP-TM-006, AP-TM-008, AP-TM-009, and AP-TM-014. In-process
object isolation is not provider IAM or process-isolation evidence.

### AP-EVAL-M4-07 · Release, update, lifecycle, failure, and rollback journeys

Verify in sequence that:

- the initial reviewed generation activates all intended fixture behavior;
- an application release behind an unchanged attachment needs no Registration change;
- a platform-facing update requires and activates a new complete generation;
- suspension removes route and catalogue behavior without changing Fixture Application State;
- reactivation restores the reviewed behavior; retirement is terminal and remains closed;
- attachment replacement keeps distinct old and new targets available for rollback;
- validation failure, missing attachment resolution, or simulated selected-attachment failure does
  not partially activate or affect another fixture; and
- rollback selects a retained reviewed generation as a whole without rolling back application state.

This gate supplies the in-memory Fixture portions of AP-TM-007, AP-TM-008, AP-TM-009, and AP-TM-013.
It does not qualify persistence, concurrent writers, a provider transaction, or an operator runbook.

### AP-EVAL-M4-08 · Limits, redaction, determinism, extraction, and non-mutation

At each exact boundary and one unit beyond it, verify the 16-byte method, 1,024-byte path,
1,024-byte query, 32-header, 64-byte header-name, 1,024-byte header-value, 8,192-byte aggregate
header, empty-body, 65,536-byte response, 60-second assertion, and 256-entry replay limits.

Also verify that:

- repeated runs from identical constructed state return byte-identical responses and outcomes;
- diagnostics contain only approved fixture identifiers, generation digests, outcome codes, and
  correlation identifiers;
- diagnostics and failures omit assertion envelopes, sessions, restricted members, request bodies,
  principals, entitlements, and application state;
- tests run from a temporary copy of the project-local fixture and contract layers without a
  containing-repository import; and
- tracked inputs remain byte-identical and no unexpected file, cache treated as evidence, network
  call, socket, credential read, or external mutation occurs.

This gate supplies the bounded Fixture portions of AP-TM-001, AP-TM-005, AP-TM-010 through
AP-TM-013. It is not load, concurrency, timeout, rate, cost, or availability evidence.

### AP-EVAL-M4-09 · Truthful evidence and handoff

Verify that the AP-M4 change:

- records Fixture evidence only after AP-EVAL-M3 and AP-EVAL-M4 pass at the same revision;
- reports the exact command, counts, failures, errors, warnings, and skips actually observed;
- calls synthetic signing, direct entry-point denial, in-memory activation, and object isolation by
  those names rather than production cryptography, direct-origin denial, persistence, or IAM;
- leaves every Live and Adoption gate explicitly unavailable;
- leaves Finance Assistant and infrastructure, Terraform, DNS, identity, credentials, deployment,
  and access unchanged; and
- directs the next task to separate infrastructure planning rather than implementation or
  Application Adoption.

### Determinism and mutation checks

AP-M4 tests must recreate all mutable harness state for every case. They may advance only the
injected clock, correlation sequence, generation pointer, replay store, and the explicitly selected
fixture's synthetic state. Case order, wall clock, hash randomization, current user, absolute path,
environment, network state, or prior test execution must not affect results.

Tests compare requests, registration inputs, compiled generations, and non-selected state before
and after each journey. Any unrequested mutation, ambient dependency, warning-only rejection,
unbounded operation, or unexpected artifact fails the gate.

### Threat coverage boundary

| Threats | AP-EVAL-M4 claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Bounded HTML catalogue, route and attachment selection, and inert fixture resolution |
| AP-TM-004 | Header stripping and assertion-side direct-entry denial only; network origin remains unqualified |
| AP-TM-005 | Deterministic synthetic signature, issuer, audience, time, cross-application, and replay failure behavior |
| AP-TM-006 | Admission remains separate from fixture-owned principal and entitlement decisions |
| AP-TM-007 | Single-process complete-generation activation and rollback |
| AP-TM-008 | Independent in-memory Platform and Fixture Application State |
| AP-TM-009 | Route, attachment, audience, failure, lifecycle, and state isolation among fixtures |
| AP-TM-010 | Synthetic inputs and redacted deterministic diagnostics |
| AP-TM-011 | Reviewed repository inputs and deterministic default checks; no live control plane |
| AP-TM-012 | Exact in-process size and count limits; no traffic or cost claim |
| AP-TM-013 | Deterministic logical dependency failure without insecure fallback |
| AP-TM-014 | Generic fixtures only; no Integration Draft or Application Adoption behavior |

### Pass, fail, and skip semantics

AP-EVAL-M4 passes only when all nine gates and every implemented AP-M3 contract regression check
pass in one revision-scoped `make check` run, expected test and registration-generation counts
match their reviewed indexes, and there are zero failures, errors, unexpected warnings, and
mandatory skips.

A known Live or Adoption limitation is recorded as unavailable and is not a skip. Any mandatory
fixture case that cannot run fails the gate. No manual override, document review, screenshot,
provider result, or consuming-application test substitutes for a failing deterministic case.

### Required evaluation evidence

The AP-M4 pull-request handoff records:

- evaluated commit, AP-M3 merge base, contract and fixture registration versions, and generation
  digests;
- exact command and working directory, interpreter version, duration, and test counts;
- pass, failure, error, warning, and skip counts;
- enabled fixture adapter, changed and evaluated paths, and synthetic fixture identifiers;
- requirements, decisions, and threats covered by the Fixture gate;
- security/privacy impact and unavailable Live and Adoption evidence; and
- confirmation that no credential, network, socket, package installation, cloud account, browser,
  external mutation, or generated proof artifact was used.

Evidence reports actual output and evaluated revision. It must not pre-fill success, retain an
assertion envelope, record synthetic session labels as if they were secrets, or claim that
in-process behavior occurred on a network.

### Limitations

AP-EVAL-M4 performs no browser, accessibility, load, concurrency, rate, network, cloud, DNS, TLS,
IAM, OAuth, Terraform, provider, persistence, real direct-origin, production cryptographic, cost,
alerting, incident-response, migration, or application-product testing. It does not prove that a
real application can or should adopt the platform.

Infrastructure and Live qualification require a separate owner-approved slice after AP-M4 merges.
Every Application Adoption remains an application-owned later slice with its own evidence.
