# App Platform threat model

Version 0.4 | Status: Fixture-qualified threat model and initial Live trust profile; no live infrastructure is implemented

This document defines the security and privacy threats created by the logical App Platform design,
assigns control ownership, and names the evidence required before a control may be called
implemented or qualified. It is authoritative only inside the App Platform project. It does not
configure identity, provision infrastructure, mutate DNS, activate an application, or change a
consuming application's security model.

Requirements: AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006

Decisions: ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006

System design: [App Platform system design](03_system_design.md)

## Scope and status

The threat boundary includes:

- offline registration, contract validation, compilation, review, and evidence;
- the future Shared Edge, root catalogue, routing, admission, and identity delivery;
- Application Attachments and the platform-to-application request seam;
- Platform State, Application State references, lifecycle, rollback, and drift;
- Fixture Applications used for future platform qualification; and
- future Application Adoption where a real application consumes platform contracts.

The boundary excludes application product behavior except where the platform could bypass,
confuse, broaden, or interfere with application-owned controls. Vulnerabilities wholly inside an
application remain the Application Owner's responsibility, while route isolation, identity
delivery, direct-bypass prevention, and cross-application effects remain in scope for the platform.

No runtime control is operational merely because it is specified here. Deterministic contract
evidence, Fixture Application evidence, live provider readback, and application-adoption evidence
are different gates and are never substitutes for one another.

## Security objectives

The platform must preserve these objectives:

1. **Route integrity:** one canonical request path selects at most one reviewed application
   attachment, and every unknown or invalid path fails closed.
2. **Admission integrity:** public, authenticated, and restricted Admission Modes are enforced as
   registered without granting application Feature Entitlements.
3. **Identity authenticity:** only a verified issuer-and-subject assertion for the intended
   application audience can become Verified Identity Context.
4. **Application isolation:** one application's route, identity, failure, compromise, or lifecycle
   action does not expose or mutate another application.
5. **Exclusive ownership:** each managed resource has one state owner and cross-state references
   never become write authority.
6. **Configuration integrity:** only a complete, reviewed Registration Generation can become the
   Shared Edge configuration, and failed change preserves or restores the last reviewed generation.
7. **Data minimization:** the platform stores, renders, logs, and evidences only the data required
   for catalogue, routing, admission, identity verification, and accountable operation.
8. **Truthful evidence:** deterministic, fixture, live, and adoption results state their exact
   revision, environment, limitations, failures, and skipped gates.

## Assets and data classes

| Asset or data | Classification | Protection objective |
| --- | --- | --- |
| Configured hostname, route table, and catalogue | Public behavior, controlled configuration | Integrity and availability |
| Registration Sets and compiled generations | Platform configuration | Integrity, provenance, review, rollback |
| Attachment resource references | Restricted platform configuration | Integrity, non-disclosure where provider identifiers are sensitive |
| Restricted admission membership | Restricted identity policy | Confidentiality, integrity, minimal access |
| Signed identity assertions and identity claims | Restricted authentication data | Authenticity, confidentiality, replay resistance |
| State-owner references and manifests | Restricted operational metadata | Integrity and exclusive ownership |
| Credentials, signing keys, OAuth secrets, and state contents | Secret; prohibited from contracts and Git | Confidentiality and non-persistence |
| Platform logs and qualification evidence | Restricted unless explicitly safe for publication | Redaction, provenance, retention limits |
| Application data and provider payloads | Outside platform ownership | Non-collection and non-disclosure |

Catalogue output is public only after safe projection. Registration input is not public catalogue
content and must not be rendered, logged, or published wholesale.

## Actors and trust assumptions

- An **anonymous Visitor** is untrusted and may send malformed paths, spoofed headers, oversized
  inputs, or abusive traffic.
- An **authenticated identity** has proven only the configured identity assertion. Authentication
  does not imply restricted admission, application resource ownership, or a Feature Entitlement.
- An **Application Owner** is trusted to control only that application's state and to propose
  accurate attachment references. Its registration remains untrusted until validated and reviewed.
- A **Platform Operator** has bounded operational authority and may make mistakes or use a
  compromised workstation or credential. Review and readback remain required.
- The **Platform Owner** approves requirements, registrations, destructive shared-resource change,
  and live qualification. Approval cannot override a failed contract or weaken an accepted ADR
  without changing the authority first.
- A **Registered Application** is mutually untrusted with every other application. A compromised
  application must not gain Shared Edge control, another audience, or another application's state.
- The future **identity provider and cloud provider** are external trust dependencies. The platform
  must verify their configured signals and fail closed, but their internal compromise is residual
  provider risk outside this project's direct control.
- Source control and continuous integration are part of the future configuration control plane.
  Repository write access is privileged but does not by itself authorize live mutation.

Finance Assistant is not a trusted platform test harness. Its Integration Draft is untrusted input
to a future adoption review and grants no platform or Finance authority.

## Trust zones and flows

```text
  [Public Visitor]
         |
         | untrusted requests and headers
         v
  [Shared Edge data plane] <--------> [Identity provider]
         |
         | admitted request + signed identity assertion
         v
  [Application Attachment] ---------> [Application runtime and state]

  [Application Owner proposal]
         |
         | untrusted Registration Set
         v
  [Repository + review] -> [Registration Compiler] -> [compiled generation]
                                                        |
                                                        | future reviewed apply
                                                        v
                                            [Provider control plane + Platform State]
```

The major trust-boundary crossings are:

1. Visitor input crossing into the Shared Edge.
2. Identity-provider output crossing into platform admission.
3. Admitted traffic and identity crossing from the Shared Edge to an attachment.
4. Application-owner input crossing into platform configuration review.
5. Compiled configuration crossing from the repository into a provider adapter.
6. Resource references crossing between Platform State and Application State without shared write
   access.
7. Logs and evidence crossing from restricted operational systems into retained artifacts.

## Control ownership

### Platform-owned controls

- strict registration schemas and semantic validation;
- canonical route parsing, reserved-path enforcement, and closed unmatched behavior;
- safe catalogue projection and output-context escaping requirements;
- attachment-adapter allow-listing and registration-derived edge configuration;
- Admission Mode enforcement and removal of visitor-supplied identity headers;
- whole-generation activation, drift detection, rollback, and Platform State access control; and
- platform log minimization, redaction, and revision-scoped evidence.

### Application-owned controls

- runtime and endpoint access policy, including rejection of direct protected ingress;
- independent assertion signature, issuer, audience, time, and contract-version validation;
- immutable Application Principal derivation and application-data isolation;
- Feature Entitlements, provider rights, product roles, and application revocation; and
- attachment deployment, health, rollback availability, and Application State recovery.

### Jointly coordinated controls

- attachment compatibility, audience and caller-principal exchange, and release ordering;
- lifecycle activation, suspension, retirement, and rollback windows;
- proof that cross-state resource references have one owner; and
- future adoption, state transfer, cutover, and rollback.

Joint coordination does not create joint state ownership. Each resource and control still has one
named owner.

## Evidence classes

| Class | Earliest delivery item | What it can prove | What it cannot prove |
| --- | --- | --- | --- |
| Contract (`C`) | Item 3 | Schema, semantic, transition, ownership, and deterministic compilation behavior | Runtime routing, cryptography, ingress, or cloud state |
| Fixture (`F`) | Item 4 | Observable platform behavior using synthetic registered applications | A real application's compatibility or live cloud configuration |
| Live (`L`) | Item 5 or later | Provider configuration, DNS/TLS, IAM, direct-bypass controls, drift, and operator procedures | Application Adoption or product authorization correctness |
| Adoption (`A`) | Application-owned later slice | One real application's compatibility, state handoff, product isolation, and rollback | Generic platform qualification for other applications |

An evidence requirement marked `F`, `L`, or `A` remains deferred even if all contract tests pass.
Live evidence must be secret-free and revision-scoped; screenshots or unredacted provider payloads
are not default evidence.

### Item 4 deterministic Fixture profile

Delivery item 4 uses the `fixture-in-process-v1` adapter and one synchronous Python
standard-library request pipeline. It has no listening socket, network ingress, external identity
provider, live credential, persistent registration store, provider resource, or concurrency. The
fixture application set contains separate public, authenticated, and restricted applications with
separate Fixture Application State.

The fixture pipeline accepts only `GET`, an empty body, paths and queries of at most 1,024 UTF-8
bytes each, at most 32 headers, header names of at most 64 ASCII bytes, header values of at most
1,024 UTF-8 bytes, at most 8,192 aggregate header bytes, and responses of at most 65,536 UTF-8
bytes. A 16-byte method limit is applied before method selection. There is no connection or stream
to limit; live connection, rate, concurrency, and timeout controls remain unresolved.

Synthetic protected admission uses a deterministic fixture-only HMAC-SHA-256 assertion envelope
around the Version 1 Verified Identity Context. Public test key material is injected, assertion
lifetime is at most 60 seconds, clock skew is zero, and each fixture owns a 256-entry fail-closed
replay store. These choices permit deterministic testing of signature, issuer, subject, audience,
time, cross-application, and replay failures. They are not evidence for a production identity
provider, algorithm, key custody, rotation, or network-origin control.

Fixture registration inputs are reviewed complete generations. Successful compilation installs a
complete generation into an in-memory reviewed-generation collection and atomically changes one
current pointer; rejection preserves the prior generation. There is no registration API or
database. Fixture Application State remains independently constructed and is never rolled back or
deleted by a platform generation change.

The detailed topology and evidence exclusions are owned by the [system design](03_system_design.md).
Until the separate item 4 plan, implementation, and evaluation record are accepted, this profile
is design authority and produces no Fixture (`F`) evidence.

## Threat register

### AP-TM-001 · Registration injection and unsafe catalogue content

**Scenario:** An Application Owner or compromised repository change supplies unknown fields,
executable-looking values, control characters, markup, oversized text, credentials, provider
commands, or private metadata. The values could alter compilation, create stored script injection,
or leak data through the root catalogue.

**Required controls:** Strict schemas reject unknown and out-of-bound values. Catalogue fields are a
small plain-text projection with no HTML, scripts, images, arbitrary links, attachments, allow-list
members, or secrets. Renderers escape every value for its output context. Registration data never
becomes an executable provider command.

**Evidence:** `C` covers valid and invalid vectors, size limits, unknown fields, unsafe characters,
and deterministic safe projection. `F` covers rendered catalogue behavior. `L` covers deployed
headers and renderer configuration where applicable.

**Residual risk:** Item 4 selects bounded HTML rendering for Fixture evidence. Live renderer
technology, response headers, and provider limits remain later decisions.

### AP-TM-002 · Route confusion, shadowing, and traversal

**Scenario:** Ambiguous prefixes, textual prefix matching, encoded separators, dot segments,
case-folding, Unicode lookalikes, attachment-mount overlap, or reserved-path collision routes a
request to the wrong application or platform handler.

**Required controls:** Registration uses canonical lowercase segment paths, fixed reserved paths,
segment-bounded matching, deterministic longest attachment-mount selection, and rejection rather
than normalization of alternate encodings. The complete Registration Set is validated for
conflicts. Unknown and malformed paths fail closed without fallback to another application.

**Evidence:** `C` covers canonicalization, conflicts, mount selection, and closed compilation.
`F` covers exact paths, subpaths, near-prefixes, encodings, reserved paths, and unmatched requests.
`L` confirms the provider adapter implements the same behavior.

**Residual risk:** Provider-specific path decoding can differ from the logical contract and requires
adapter-level conformance tests before live qualification.

### AP-TM-003 · Malicious or mistaken attachment reference

**Scenario:** A registration names an arbitrary URL, credential-bearing value, another
application's runtime, an unsupported adapter, or a resource the proposer does not own. Validation
or routing could become server-side request forgery, credential disclosure, or cross-application
access.

**Required controls:** Attachment kinds and resource-reference forms are allow-listed and bounded.
References are treated as inert data; offline validation performs no fetch or provider discovery.
The immutable application identifier, attachment identifier, mount, forwarding mode, identity
requirement, and ownership entry must agree. Secrets and Terraform state addresses are forbidden.
Provider adapters resolve only their own typed references with least-privilege credentials.

**Evidence:** `C` covers unsupported kinds, malformed references, secrets, duplicate ownership, and
cross-registration conflicts. `F` covers attachment selection and application isolation. `L`
confirms resource identity, IAM, and absence of arbitrary egress.

**Residual risk:** `gcp-cloud-run-v1` and its typed resource grammar are selected for the first Live
profile, but no provider lookup, IAM grant, ownership readback, or target validation is implemented
or qualified. The fixture adapter remains the only executable adapter.

### AP-TM-004 · Direct protected-origin bypass

**Scenario:** A Visitor reaches an application runtime without crossing platform admission, or
spoofs the platform identity header against a publicly reachable origin.

**Required controls:** Application State restricts protected runtime ingress to the Shared Edge
caller using provider or network controls. The Shared Edge strips visitor-supplied identity headers.
The application independently verifies the signed assertion and application-specific audience. A
header alone never compensates for a public protected origin.

**Evidence:** `C` can prove only that protected attachments declare the required identity and
ingress posture. `F` exercises spoofed headers and direct calls to protected fixture entry points,
but can prove only assertion-side denial in one process. `L` must read back and test the actual
ingress and IAM configuration. `A` repeats the gate for a real application.

**Residual risk:** The planned load-balancer, Cloud Run ingress, edge caller, and application-side
verification layers name a future network direct-bypass control; they are not implemented until
separately approved infrastructure and deployment slices complete. Fixture denial must never be
reported as origin isolation.

### AP-TM-005 · Identity spoofing, replay, and confused audience

**Scenario:** An unsigned, expired, replayed, wrong-issuer, wrong-audience, or visitor-controlled
assertion is treated as Verified Identity Context. An assertion for one application is reused
against another, or mutable email is treated as an ownership key.

**Required controls:** Admission and the application validate signature, configured issuer,
immutable subject, application-specific audience, issued and expiry times, and contract version.
Visitor values are removed before edge forwarding. Restricted policy matches exact issuer-and-
subject pairs. Applications derive their own principals and never use email as an ownership key.

**Evidence:** `C` covers claim shape and rejection semantics, not cryptographic validity. `F` covers
missing, forged, expired, wrong-issuer, wrong-audience, and cross-application assertions. `L` covers
signer, key discovery, algorithms, audience issuance, and clock behavior.

**Residual risk:** The Live profile selects Google OIDC, ES256 in Cloud KMS, application audiences,
a 60-second assertion, 30-second skew, and overlapping public keys, but none is implemented or
qualified. The demo accepts residual cross-instance replay risk because it makes no distributed
replay-prevention claim.

### AP-TM-006 · Admission mistaken for feature authorization

**Scenario:** Successful platform admission is interpreted as permission to use restricted
application features, provider data, or another user's resources.

**Required controls:** Registration schemas contain no Feature Entitlement or product-role fields.
The platform makes only an Admission Decision. Each application derives an Application Principal,
isolates application data, and independently enforces every entitlement and provider right.

**Evidence:** `C` rejects feature-authorization fields in platform contracts. `F` proves an admitted
identity can use an unrestricted fixture feature while the fixture denies a market-data-style
entitlement. `A` qualifies a consuming application's actual product and provider boundaries.

**Residual risk:** Platform qualification cannot prove any real application's authorization or
provider rights.

### AP-TM-007 · Stale, concurrent, partial, or unsafe lifecycle change

**Scenario:** Two proposals race, a stale generation overwrites a reviewed one, catalogue and route
updates diverge, a suspension leaves a route active, or a failed attachment replacement destroys
the rollback target.

**Required controls:** Each complete Registration Set carries a monotonic generation and preceding
digest. The compiler enforces lifecycle transitions and produces one canonical generation. Future
activation is atomic across catalogue, routes, admission, attachments, and ownership. The old
attachment and Last Reviewed Working Configuration remain available through the declared rollback
window.

**Evidence:** `C` covers stale digests, invalid transitions, deterministic generations, and
all-or-no-output failure. `F` covers register, update, suspend, retire, attachment replacement, and
rollback journeys. `L` covers provider partial-failure recovery and drift.

**Residual risk:** Item 4 can qualify only an in-memory, single-caller generation swap. Persistent
storage, locking, provider transactions, acceptance windows, and operator rollback procedures
remain later implementation and evaluation decisions.

### AP-TM-008 · Dual state ownership or destructive cross-state action

**Scenario:** Platform State and Application State manage the same resource, one side deletes the
other's resource during lifecycle change, or a migration imports before the previous owner releases
management.

**Required controls:** The State Ownership Manifest assigns each canonical resource reference to
one owner. Platform lifecycle never mutates application-owned runtime or data; application
lifecycle never mutates Shared Edge resources. Cross-state exchange is versioned reference data,
not backend access. Destructive actions identify exact targets and require explicit review.

**Evidence:** `C` rejects duplicate owners and ownership/type mismatches. `F` covers independent
fixture and platform lifecycle. `L` covers state inventories, plans, readback, and destructive-action
guards. `A` proves exclusive ownership at every transfer phase for a real application.

**Residual risk:** A manifest is a declaration until provider/state readback confirms it. Item 3
cannot qualify live ownership.

### AP-TM-009 · Cross-application lateral movement

**Scenario:** A compromised application receives another route, reuses another audience, accesses
another attachment, influences the catalogue, or obtains platform credentials capable of changing
the Shared Edge.

**Required controls:** Routes and attachment identifiers are unique and registration-derived.
Identity audiences and Application Principals are application-scoped. Applications receive no
Platform State credentials or registration write access. Provider adapters and edge callers use
least-privilege identities, and one unavailable application never becomes another's fallback.

**Evidence:** `C` covers unique identifiers, ownership, and audience binding. `F` covers route,
identity, failure, and lifecycle isolation between at least two registrations. `L` covers actual IAM
and credential scope.

**Residual risk:** Shared Edge compromise has hostname-wide impact and requires provider hardening,
operator separation, audit, and recovery evidence in later slices.

### AP-TM-010 · Secret, identity, or application-data leakage

**Scenario:** Credentials, restricted membership, signed assertions, provider payloads, request
bodies, application data, Terraform state, or authenticated browser artifacts enter contracts,
logs, plans, test vectors, evidence, or Git.

**Required controls:** Contracts accept only non-secret references and bounded identity policy.
Synthetic values are used in tests. Logs and evidence allow only contract versions, generation
digests, application and route identifiers, coarse outcomes, violation codes, and correlation
identifiers. Secret payloads and application data are prohibited and externally stored.

**Evidence:** `C` includes secret-pattern and prohibited-field checks over committed contract
artifacts. `F`, `L`, and `A` inspect generated evidence and logs for redaction without recording the
prohibited payloads themselves.

**Residual risk:** Log sink access, retention, deletion, and incident response remain deployment
decisions. Pattern checks supplement but never replace secret storage and access control.

### AP-TM-011 · Unauthorized control-plane change, drift, or supply-chain substitution

**Scenario:** A repository, dependency, workflow, operator credential, or provider-console change
alters routing or admission outside the reviewed Registration Generation. Validation tooling or
contract schemas are substituted between review and apply.

**Required controls:** Canonical output is bound to input and compiler versions by digest. Protected
review covers schemas, registrations, validation code, and provider plans. Default checks are
deterministic and credential-free. Live mutation uses separate explicit operator actions. Manual
provider changes are drift and never become configuration authority.

**Evidence:** `C` covers deterministic output, schema identifiers, test-vector expectations, and
extraction-safe checks. `L` covers revision binding, workload identity, least privilege, drift
readback, plan review, and audit records.

**Residual risk:** Branch protection, reviewer policy, artifact signing, dependency pinning,
workload identity, and provider audit settings remain repository and infrastructure decisions.

### AP-TM-012 · Availability and cost abuse

**Scenario:** Oversized registrations, catalogue fields, path inputs, authentication attempts,
request bodies, streaming connections, or traffic volume exhaust validation, edge, identity,
logging, application, or billable provider capacity.

**Required controls:** Contracts place numeric size and count limits on every collection and string.
Compiler work is bounded and performs no external calls. Future adapters set request, header, body,
connection, and timeout limits; isolate application failures; and expose explicit cost-bearing
resources and operator actions. Rate or abuse controls must not silently broaden admission.

**Evidence:** `C` covers boundary values and deterministic rejection. `F` covers representative
limit and isolation behavior without load or availability claims. `L` covers provider quotas,
timeouts, alerts, and billable-resource inventory.

**Residual risk:** The initial platform is demo-scale with no high-availability commitment. Item 4
selects exact in-process request and response limits but cannot exercise connection, traffic-rate,
concurrency, network timeout, provider quota, alert, or spending controls. Those remain later owner
decisions.

### AP-TM-013 · External dependency failure or stale trust material

**Scenario:** DNS, TLS, identity-provider keys, certificates, attachment resolution, or provider
control-plane operations fail or become stale. The platform falls back to insecure routing or
accepts identity it can no longer verify.

**Required controls:** Protected admission and identity verification fail closed. Unknown routes do
not fall back to an application. Provider failure for one attachment does not reroute to another.
Configuration retains the Last Reviewed Working Configuration and records unavailable or partial
status without implying success.

**Evidence:** `F` covers logical dependency failure using deterministic adapters. `L` covers actual
DNS, TLS, key rotation, certificate, provider failure, and recovery behavior.

**Residual risk:** Provider availability and disaster recovery beyond the demo commitment remain
outside the initial qualification claim.

### AP-TM-014 · Integration Draft or fixture mistaken for Application Adoption

**Scenario:** A draft integration, synthetic fixture result, or platform qualification is treated as
permission to migrate a real application, broaden admission, transfer resources, or supersede the
application's requirements and security decisions.

**Required controls:** Integration Drafts remain outside both authority chains until adopted.
Fixtures use synthetic state and cannot depend on a real application. Adoption names compatible
contract revisions, application-owned authority changes, state-owner transitions, cutover,
rollback, and product-specific evidence. One project cannot approve another project's change.

**Evidence:** `C` preserves authority labels and dependency checks. `F` proves only generic platform
behavior. `A` is mandatory for every real application and retains its prior historical evidence.

**Residual risk:** Human process can still misstate adoption; truthful status checks, review, and
release ownership are required at every handoff.

## Unresolved security decisions

The following decisions must be approved by their owning later slice before the named evidence can
pass:

| Decision | Required before |
| --- | --- |
| OAuth client values, session-store realization, KMS/JWKS resources, and identity IAM bindings for the selected trust profile | Infrastructure implementation |
| Live request, header, body, connection, rate, concurrency, and timeout limits | Live qualification |
| Terraform modules, state backends, resource names, ingress realization, and IAM bindings for the selected GCP topology | Infrastructure implementation |
| Operator roles, review separation, branch protection, workload identity, and audit policy | Live mutation |
| Logging backend, retention, access, redaction, deletion, and incident handling | Live evidence collection |
| Cost thresholds, quotas, alerts, and approved billable resources | Live qualification |
| Application-specific principals, data isolation, providers, and entitlements | Each Application Adoption |

An unresolved decision causes its dependent gate to remain unavailable; it is not an accepted risk
by silence.

## Threat-model acceptance boundary

This document is accepted when every in-scope trust crossing has an owner, every threat has required
controls and an evidence class, deferred decisions are explicit, and no deterministic claim is used
as runtime or adoption evidence. Acceptance of the document does not implement any control.

The implementation plan and evaluation strategy for this delivery item must reference these threat
identifiers. Versioned schemas and deterministic validation must cover every `C` requirement. Later
fixture, infrastructure, and adoption plans must carry forward the applicable `F`, `L`, and `A`
requirements without weakening them.

## Threat trace

| Threats | Requirements | Decisions |
| --- | --- | --- |
| AP-TM-001 through AP-TM-003 | AP-PR-001, AP-PR-002, AP-PR-003; AP-QR-002, AP-QR-003, AP-QR-004 | ADR-001, ADR-002, ADR-005 |
| AP-TM-004 through AP-TM-006 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002 | ADR-003, ADR-004, ADR-005, ADR-006 |
| AP-TM-007 through AP-TM-009 | AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005 |
| AP-TM-010 through AP-TM-013 | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-005, ADR-006 |
| AP-TM-014 | AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-006 | ADR-004 |
