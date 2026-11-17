# App Platform evaluation strategy

Version 0.3 | Status: deterministic evaluation authority through AP-M5; future AP-M6 through AP-M9 claim boundaries

This document preserves how delivery item 3, AP-M3, and delivery item 4, AP-M4, are evaluated. It
now defines the deterministic planning gate for delivery item 5, AP-M5, and the claim boundaries
that later AP-M6 through AP-M9 authorities must refine before implementation or use. AP-EVAL-M5
qualifies planning consistency only; it does not qualify a live Shared Edge, provider identity,
cloud resource, deployment, or consuming application.

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

## AP-EVAL-M5 · Infrastructure-planning gate

### Evaluation claim

A passing AP-EVAL-M5 result means only that the evaluated repository revision contains complete,
internally consistent planning authority for the initial GCP qualification topology and for the
later AP-M6 through AP-M9 delivery sequence.

It proves no provider behavior and creates no new evidence class. AP-EVAL-M3 Contract (`C`) and
AP-EVAL-M4 Fixture (`F`) regression gates must continue to pass. Live (`L`) and Adoption (`A`)
evidence remain unavailable.

### Evaluation environment

AP-EVAL-M5 runs through the existing project-local entry points:

```bash
make check
make -C apps-platform check
```

One invocation from the appropriate root is sufficient. The complete command must remain Python
standard-library-only, credential-free, deterministic, network-free, and non-mutating. It may read
committed source but may not run Terraform, a provider CLI, DNS lookup, socket, browser, OAuth flow,
authenticated workflow, or cloud plan. It must create no committed artifact and must return nonzero
for any failed or skipped mandatory AP-M5 gate.

### AP-EVAL-M5-01 · Authority, identifiers, and trace integrity

Verify that:

- ADR-001 through ADR-009 are unique, accepted, and trace to existing requirements;
- AP-M5-W1 through AP-M5-W9 are unique, ordered, and trace to AP-PR-001 through AP-PR-009,
  AP-QR-001 through AP-QR-006, and AP-TM-001 through AP-TM-014;
- the system design, threat model, implementation plan, evaluation strategy, repository layout, and
  future handoff agree on the planning-only status;
- AP-M3 Contract and AP-M4 Fixture authorities remain intact and continue to pass; and
- every claim distinguishes selected, implemented, deployed, Live-qualified, and adopted behavior.

Documentation presence is not enough: deterministic governance checks must inspect identifiers,
required decisions, scope exclusions, and later-slice boundaries.

### AP-EVAL-M5-02 · Provider topology and attachment boundary

Verify that the authority consistently selects:

- project `comfforts-platform-non-prod`, project number `455651441682`, region `us-west1`, and no
  production environment;
- `apps-staging.comfforts.com` without changing `apps.comfforts.com` or Finance Assistant;
- one global external Application Load Balancer, Google-managed certificate, HTTP-to-HTTPS
  behavior, one Cloud Run edge, and no application-prefix duplication in the provider URL map;
- `gcp-cloud-run-v1` with the exact typed, inert project-number/region/service-name reference;
- provider metadata, readiness, ownership, and edge-caller grant as activation prerequisites rather
  than arbitrary URL fetching;
- separate Platform and Fixture Application State even in one project; and
- platform-owned Shared VPC networking for later cross-project GCP attachment without transferring
  application runtime, IAM, data, or state ownership.

The gate rejects a provider command, credential, URL target, cross-state read, Finance path, or
claim that same-project design qualifies cross-project behavior.

### AP-EVAL-M5-03 · Identity, session, and assertion trust profile

Verify that the authority distinguishes Visitor identity, Platform Session, edge-caller workload
identity, Application Principal, and Feature Entitlement, and selects:

- Google OIDC authorization code with PKCE for consumer Google and Google Workspace accounts;
- no initial MFA requirement and no other OIDC provider;
- an opaque host-only secure cookie, minimal Firestore Native session state, and an eight-hour
  absolute reauthentication boundary without stored Google access or refresh tokens;
- optional verified identity on public routes, required identity on authenticated routes, exact
  issuer-subject restricted membership, and display-only email;
- platform-owned logout with a validated relative return path;
- one environment Cloud KMS software ES256 signer with application-specific audiences and public
  JWKS only;
- 60-second assertions, 30-second clock skew, 90-day rotation, 24-hour verification overlap, and
  15-minute application key caching; and
- no distributed replay-prevention claim.

The gate must preserve existing IAP and `@react-oauth/google` behavior as unchanged application
inputs until an independently approved Application Adoption.

### AP-EVAL-M5-04 · State, operator, and source-control authority

Verify that planning defines:

- independent bootstrap, platform, and per-fixture Terraform roots;
- a platform-state GCS bucket and separate state bucket per fixture, with locking, public-access
  prevention, versioning, and recovery history of at least 90 days and 20 newer generations;
- no `terraform_remote_state`, application-backend read, shared write authority, committed state,
  saved plan, or recovery copy;
- one-time short-lived bootstrap and migration of temporary state only after verified recovery;
- GitHub Actions OIDC and GCP Workload Identity Federation bound after repository extraction;
- advisory pull-request plans, an exact protected-main plan, explicit environment approval, source
  and plan digests, concurrency, and backend locking;
- separate plan, apply, rollback, import, recovery, and destroy authority; and
- no routine local apply, with a narrowly scoped, recorded, short-lived break-glass exception.

The same human may review and approve, but normal operation may not bypass protected source,
workload identity, exact plan, target scoping, readback, or drift reconciliation.

### AP-EVAL-M5-05 · Generation activation, DNS, readback, and rollback

Verify that:

- complete Registration Sets remain reviewed Git inputs with no registration endpoint or database;
- compilation and predecessor validation produce a digest before planning;
- immutable configuration objects and edge revisions bind source, compiler, generation, object,
  image, identity, adapter, and platform versions;
- the Cloud Run traffic assignment to one revision is the only current Live generation pointer;
- staging validates dependencies before owner-approved 100-percent traffic activation;
- source, plan, state, provider, runtime, catalogue, route, attachment, identity, direct-origin, and
  ownership readback must agree;
- provider partial failure stops for inspection and never triggers automatic rollback or cleanup;
- owner-confirmed whole-generation rollback has a 15-minute post-approval objective and never
  changes Application State;
- the preceding configuration, revision, and replaced target remain for at least 24 hours; and
- the separately approved new hostname action uses a 1,800-second TTL, `dig` readback, certificate
  readiness, and no existing hostname or Finance mutation.

The gate fails if DNS is treated as a registration update, TTL is described as a propagation
guarantee, or cleanup is automatic at the end of the retention window.

### AP-EVAL-M5-06 · Logging, evidence, privacy, and incident boundary

Verify that the selected seven-day Cloud Logging profile permits only revision and generation
digests, application and route identifiers, coarse outcomes, status class, latency, correlation
identifier, and non-secret versions.

It must prohibit assertions, sessions, restricted members, issuer-subject pairs, email, bodies,
queries, raw application paths, application data, provider payloads, secrets, Terraform state,
saved plans, stream chunks, intentionally retained IP addresses, and user-agent strings. Logs have
owner-only access and no external sink.

Verify that Live evidence is a 30-day, owner-readable, private GCS bundle containing redacted
revision-bound digests, commands, readback, results, failures, limitations, and evidence labels.
Screenshots, browser state, raw provider output, and unredacted logs are not authoritative evidence.
The App Platform Owner is the incident contact, and any suspension, rollback, key action, or cleanup
requires an explicit decision.

### AP-EVAL-M5-07 · Demo-scale resource and cost controls

Verify that planning records:

- a USD 20 monthly budget with owner notifications at 50, 80, and 100 percent;
- review at 50 percent, a new-billable-change pause at 80 percent, and an explicit owner decision at
  100 percent without automatic billing disablement or destruction;
- Shared Edge Cloud Run bounds of zero minimum, two maximum, 1 vCPU, 512 MiB, and concurrency 20;
- per-fixture bounds of zero minimum, one maximum, 1 vCPU, 512 MiB, and concurrency 10;
- at most 55 minutes per SSE or WebSocket connection;
- one non-production edge and load balancer with no CDN, WAF, HSM, production replica, always-on
  instance, Firestore backup, or PITR;
- only active and overlapping KMS verification versions and active, rollback, and candidate images;
- dry-run-first, owner-approved cleanup; and
- Terraform rejection of unapproved services, larger or unbounded runtimes, longer retention,
  additional environments or edges, and missing ownership labels.

The gate must state that budgets and maximum instances are safeguards, not guaranteed hard spending
caps. Future application projects retain their own runtime and billing ownership.

### AP-EVAL-M5-08 · Later-slice and unresolved-input separation

Verify that AP-M6 provider runtime, AP-M7 Terraform/workflows, AP-M8 deployment, AP-M9 Live
qualification, and Application Adoption remain separate owner-approved branches and merge gates.

The plan must name, rather than infer:

- the network framework and dependency policy;
- exact live header, body, non-streaming timeout, and abusive-traffic limits;
- dedicated repository, workflow subject, and protected-environment values;
- globally unique bucket names and DNS managed-zone resource;
- OAuth client and notification configuration; and
- initial live fixture identities, registrations, image digests, and resource references.

An unavailable later input blocks its dependent slice. It is not a skip, provider lookup, fixture
default, Finance-derived value, or reason to weaken the accepted boundary.

### AP-EVAL-M5-09 · Non-mutation and truthful handoff

Verify that the AP-M5 branch:

- creates none of the reserved `edge/`, `registrations/`, `infrastructure/terraform/`,
  `docs/runbooks/`, or Live `artifacts/` capabilities;
- contains no Terraform file, workflow with cloud authority, state, plan, credential, secret,
  provider command, DNS lookup, browser state, deployment, or generated Live evidence;
- leaves default verification free of network, credentials, cloud accounts, and mutation;
- leaves Finance Assistant and every Integration Draft unchanged and inactive;
- records only planning authority after all nine AP-EVAL-M5 gates pass; and
- directs the next task to AP-M6 proposal only after this pull request merges.

### Threat coverage boundary

| Threats | AP-EVAL-M5 planning claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Provider topology, inert Cloud Run reference, catalogue/routing authority, and future validation requirements are explicit |
| AP-TM-004 through AP-TM-006 | Direct-origin layers, Google OIDC, Platform Sessions, ES256 assertions, audiences, and application authorization separation are explicit |
| AP-TM-007 through AP-TM-009 | Immutable generation pointer, state roots, concurrency, rollback, IAM, and application-isolation plans are explicit |
| AP-TM-010 | Prohibited log/evidence data, access, retention, and no-export policy are explicit |
| AP-TM-011 | Protected-main, WIF, exact-plan, break-glass, drift, and extraction dependencies are explicit |
| AP-TM-012 | Scale, concurrency, streaming, retention, budget, and billable-resource controls are explicit; remaining input limits are named |
| AP-TM-013 | DNS/TLS, key, session, configuration, provider-failure, readback, and rollback plans are explicit |
| AP-TM-014 | Fixture, Live, and Adoption claims remain separate and Finance Assistant remains unchanged |

### Pass, fail, and skip semantics

AP-EVAL-M5 passes only when all nine gates, every AP-EVAL-M3 and AP-EVAL-M4 regression test, and
the complete `make check` command pass at one repository revision with zero failures, errors,
unexpected warnings, and mandatory skips.

A missing trace, contradictory decision, false operational claim, undeclared later input, reserved
implementation path, credential, network dependency, cloud command, external mutation, Finance
change, or runtime/Live/Adoption claim fails the gate. A later capability being unavailable is an
explicit limitation, not a skipped AP-M5 gate.

### Required evaluation evidence

The AP-M5 pull-request handoff records:

- branch, AP-M4 merge base, evaluated revision, and final revision;
- AP-M5 work-package commits and changed paths;
- exact command and working directory, interpreter version, duration, and test count;
- pass, failure, error, warning, and skip counts;
- requirements, ADRs, threats, and later evaluation boundaries covered;
- security/privacy impact, limitations, and unresolved implementation inputs; and
- confirmation that no credential, network, provider, Terraform, DNS, identity, repository-setting,
  deployment, or application mutation occurred.

Console output from the deterministic run is sufficient. AP-M5 evidence contains no cloud result
because no cloud action is authorized.

### Limitations

AP-EVAL-M5 performs no runtime, Terraform, workflow, repository-setting, browser, accessibility,
load, concurrency, network, DNS, TLS, IAM, OAuth, KMS, Firestore, provider, budget, logging,
deployment, rollback, recovery, incident, migration, or application-product test. It cannot qualify
any selected control as implemented or operational.

## Future evaluation boundaries

The following sections constrain later authorities. They do not authorize implementation or
provide a passing result. Each later milestone must refine its environment, commands, fixtures,
expected results, evidence schema, pass/fail semantics, and exact source revision before work begins.

### AP-EVAL-M6 · Networked-provider-runtime gate

AP-EVAL-M6 may qualify only repository implementation of the networked Shared Edge and provider
runtime through local deterministic and integration tests. It must cover catalogue and prefix
routing, bounded HTTP behavior, forwarding, public/authenticated/restricted admission, OIDC flow
seams through fake adapters, session lifecycle, logout, assertion signing and verification, JWKS,
Cloud Run reference resolution through fake provider metadata, direct-entry application
verification, immutable generation loading, status/readback, failure isolation, streaming seams,
redaction, and extraction.

AP-EVAL-M6 uses no real Google account, OAuth client, KMS key, Firestore database, Cloud Run service,
Terraform, DNS, credential, socket exposed outside the test process, or provider mutation. It
supplies implementation evidence only and no Live evidence. It cannot begin until the owner approves
the network framework, dependency policy, and exact remaining request limits.

### AP-EVAL-M7 · Terraform-and-workflow gate

AP-EVAL-M7 may qualify only committed Terraform and workflow implementation through formatting,
static validation, module contract tests, policy checks, fixture configuration checks, extraction
tests, and secret/state/plan exclusion. It must prove the root and module ownership boundaries,
backend configuration shape, typed cross-state inputs, least-privilege role intent, budget and
scaling policy, explicit destructive targets, workflow source binding, and absence of implicit
apply.

AP-EVAL-M7 performs no backend initialization, authenticated plan, repository-setting change,
Workload Identity Federation action, provider API call, resource creation, DNS change, or deploy.
Static configuration is not deployed evidence and cannot satisfy AP-EVAL-M8 or AP-EVAL-M9.

### AP-EVAL-M8 · Qualification-deployment gate

AP-EVAL-M8 is an explicit operator gate executed only from protected, merged source after repository
extraction and owner approval. It may configure repository protection and federation, bootstrap
backends, run authenticated plans, apply exact approved roots, deploy the Shared Edge and Fixture
Applications, and perform the separately approved qualification DNS/TLS action.

A passing result proves only that the named revision and environment resources exist, state and
provider inventories agree, no unapproved resource changed, and deployment/readback evidence is
redacted and retained. Any partial apply stops for inspection. A deployment result cannot qualify
routing, identity, direct-origin denial, rollback, cost behavior, or application adoption.

### AP-EVAL-M9 · Live-qualification gate

AP-EVAL-M9 supplies Live (`L`) evidence only for the exact non-production project, hostname,
revision, Registration Generation, and fixture resources named by the approved gate. It uses
owner-approved non-production Google test identities without retaining their identifiers or browser
state as evidence. The default `make check` remains separate and credential-free.

#### AP-EVAL-M9-01 · Revision, environment, and evidence integrity

Verify protected-main source and plan digests, compiler and contract versions, image digests,
Registration Generation and predecessor, Terraform lineages, project number, region, hostname,
workflow identity, approval, timestamps, and redacted evidence destinations. Any mismatch or
unapproved resource fails before behavioral claims proceed.

#### AP-EVAL-M9-02 · DNS, TLS, catalogue, and route behavior

Read back authoritative and recursive DNS, certificate status, HTTPS, HTTP redirection, security
headers, one load-balancer backend, one edge traffic target, catalogue projection, registered exact
and subpaths, mounts, forwarding, and closed unknown, malformed, reserved, suspended, and retired
paths. Confirm application prefixes are not duplicated in the provider URL map.

#### AP-EVAL-M9-03 · Attachment ownership and direct-origin denial

Read back each typed Cloud Run target, readiness, project, region, Application State owner, edge
caller grant, ingress, and absence of arbitrary URL resolution. Prove a protected target rejects an
unauthenticated direct request and a caller lacking the edge identity, while the reviewed edge path
reaches only the intended application. Same-project evidence does not qualify cross-project
attachment.

#### AP-EVAL-M9-04 · OIDC, session, admission, and logout

Exercise anonymous public access, optional identity on public access, authenticated admission,
restricted allow and deny, invalid/expired session failure, eight-hour boundary configuration,
cookie attributes, safe redirect state, logout from root and application paths, and display-only
email. Prove authentication grants no Fixture Application Feature Entitlement.

#### AP-EVAL-M9-05 · Assertion, KMS, JWKS, and application verification

Read back the software ES256 key location and active version, public JWKS, key identifier, one
environment signer, and application-specific audiences. Exercise valid, missing, visitor-supplied,
malformed, expired, future, wrong-issuer, wrong-audience, cross-application, and unknown-key
assertions; 60-second lifetime; 30-second skew; key refresh; overlap; and fail-closed stale-key
behavior. Record that distributed replay prevention remains unavailable rather than implying it.

#### AP-EVAL-M9-06 · Activation, failure, readback, and rollback

Stage a reviewed successor without traffic, reject a stale predecessor and invalid dependency,
activate one complete generation, and compare source, state, provider, runtime, route, attachment,
identity, ownership, and digest readback. Simulate an approved non-destructive partial failure and
confirm stop-for-inspection. With owner confirmation, measure whole-generation rollback against the
15-minute objective and prove Application State is unchanged and prior assets remain for 24 hours.

#### AP-EVAL-M9-07 · State, operator, drift, and recovery controls

Read back independent roots, buckets, IAM, locking, versioning, recovery lifecycle, WIF conditions,
protected environment, concurrency, and plan/apply scope. Confirm platform identities cannot read
fixture state and fixtures cannot read one another. Introduce only an approved reversible drift
case, prove detection, and reconcile through source. Break-glass, force-unlock, push, import, and
destroy remain unexecuted unless a separately approved recovery case requires them.

#### AP-EVAL-M9-08 · Limits, streaming, isolation, and cost inventory

Exercise the approved header, body, timeout, concurrency, and stream boundaries without load claims;
verify SSE and WebSocket behavior through the edge up to the bounded test duration; and prove one
fixture's failure does not route to or alter another. Read back scale-to-zero, instance maxima,
resources, budgets, thresholds, labels, image-retention dry run, approved billable-service inventory,
and excluded services. State explicitly that budgets and instance maxima are not hard spend caps.

#### AP-EVAL-M9-09 · Logging, redaction, retention, incident, and evidence

Verify one bounded completion event, required control-plane audit events, allowed fields, prohibited
field absence, owner-only access, seven-day log retention, no external sink, 30-day evidence
retention, and evidence hashes. Exercise the incident procedure without destructive action and
confirm screenshots, assertions, identities, IP addresses, payloads, state, and raw provider output
are absent from authoritative evidence.

#### AP-EVAL-M9-10 · Truthful qualification and adoption boundary

AP-EVAL-M9 passes only when all mandatory gates and AP-EVAL-M3 through AP-EVAL-M8 dependencies pass
for the exact revision with zero mandatory skips. Report every failure, limitation, residual risk,
unavailable cross-project claim, and unimplemented alert. Record Live evidence only; leave Finance
Assistant and every Application Adoption unchanged and unavailable.
