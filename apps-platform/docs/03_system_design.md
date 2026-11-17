# App Platform system design

Version 0.8 | Status: Fixture-qualified logical design and approved AP-M6 runtime profile;
immutable generation loading implemented locally; no provider operation or live infrastructure is
implemented

This document defines the smallest logical design that can support the App Platform requirements
and accepted architecture decisions. It is authoritative only inside the App Platform project. It
does not provision infrastructure, activate an application, qualify runtime behavior, or change a
consuming application.

Requirements: AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006

Decisions: ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009

## Design outcome

The platform has one configuration seam: a complete, versioned Registration Set is validated and
compiled into one immutable Shared Edge configuration. The compiler has no deployment side effects.
Future provider adapters may consume only a successfully compiled generation; they may not read
application state, invent routes, or treat manual edge configuration as another authority.

The design separates three kinds of work:

1. **Offline contract work:** validate registrations, lifecycle transitions, route isolation,
   catalogue safety, admission policy, attachment references, and exclusive ownership; then produce
   deterministic compiled output or ordered violations.
2. **Shared Edge operation:** a future platform-owned adapter realizes a reviewed compiled
   generation as hostname-level catalogue, routing, TLS, and admission behavior.
3. **Application operation:** an Application Owner supplies compatible attachments and retains its
   runtime, data, identity mapping, feature authorization, providers, and Application State.

AP-M3 implements the first kind, and AP-M4 implements and Fixture-qualifies the deterministic
in-process form of the second and third kinds. This revision selects the initial provider topology
for infrastructure planning. It does not implement a provider adapter, Terraform configuration,
cloud resource, DNS change, deployment, or Live qualification.

## Logical topology

```text
                         reviewed Registration Set
                                     |
                                     v
                         +------------------------+
                         | Registration Compiler  |
                         | validate + derive      |
                         +------------------------+
                           |                    |
                 violations                    v
                                      immutable compiled generation
                                                   |
                                         future provider adapter
                                                   |
     Visitor ------> configured hostname ------> Shared Edge
                                                   |  |  |
                                                   |  |  +--> closed default
                                                   |  +-----> derived catalogue
                                                   +--------> admitted route
                                                                  |
                                                        Application Attachment
                                                                  |
                                                     application-owned runtime
```

The configured hostname, cloud project, region, identity provider, and provider-adapter settings
are deployment configuration. They are never embedded in reusable contracts or derived from the
containing Finance Assistant repository.

### Initial Live qualification topology

The initial Live environment is the dedicated non-production GCP project
`comfforts-platform-non-prod` (project number `455651441682`). Regional services are located in
`us-west1`; the global load balancer remains a global resource. The first hostname is
`apps-staging.comfforts.com`. Neither the environment nor its qualification procedure may read,
import, mutate, or destroy Finance Assistant edge resources, DNS, Terraform state, identity, or
deployment.

```text
 Visitor
    |
    | HTTP redirect / HTTPS, SSE, WebSocket, upload, download
    v
 global external Application Load Balancer
    |  reserved address + Google-managed certificate
    |  one serverless backend; no application-prefix routes
    v
 Cloud Run Shared Edge (us-west1)
    |  catalogue + prefix routing + admission + assertion + target selection
    |  dedicated edge caller
    v
 gcp-cloud-run-v1 typed attachment
    |
    v
 application-owned Cloud Run service
```

The provider URL map performs only hostname-level forwarding and HTTP-to-HTTPS behavior. It sends
all application traffic to one edge service, so the active Registration Generation remains the
only application-routing authority. The initial profile has no CDN or WAF. Exact request, response,
streaming, concurrency, timeout, and scaling limits belong to the later approved infrastructure
profile and Live gate.

The desired DNS record is platform-owned configuration, but record creation and cutover are an
explicit, separately approved operator action. A Google-managed certificate covers the hostname,
not application prefixes. No application attachment needs a separate client-facing DNS name or
certificate, and this planning decision does not create either the record or certificate.

## Modules and seams

### Registration Compiler

The Registration Compiler is an in-process, deterministic module. Its interface accepts:

- the last reviewed Registration Generation, when one exists;
- one proposed complete Registration Set; and
- validated platform configuration containing the enabled allow-listed attachment adapter kinds.

It returns exactly one of:

- a canonical Compiled Shared Edge Configuration and State Ownership Manifest; or
- a stable, ordered collection of validation violations with machine-readable codes and paths.

The compiler performs no network, filesystem mutation, cloud lookup, DNS lookup, credential access,
or provider discovery. The same input bytes and compiler version produce the same canonical output
bytes and digest. A caller cannot request partial compilation or bypass a failed rule.

The complete set, rather than an individual registration, is the validation scope because prefix
uniqueness, reserved paths, attachment ownership, and catalogue derivation are cross-registration
properties. The compiler interface is also the deterministic test surface.

The [Version 1 contract index](../contracts/README.md), schemas, canonical serialization rules,
violation codes, and reviewed vectors now own the machine interface described here. They implement
offline Contract evidence only; a runtime or provider adapter cannot fill a later authority gap.

### Shared Edge

The Shared Edge is the future platform-owned module at the configured hostname. Its interface is a
reviewed Compiled Shared Edge Configuration. It owns only:

- hostname-level DNS intent and its explicit operator procedure;
- hostname-level addresses, TLS, HTTP-to-HTTPS behavior, forwarding, and load balancing;
- the root catalogue and platform operational paths;
- registration-derived routes and edge-only attachment resources;
- application admission at the request or new streaming-connection boundary; and
- closed behavior for unknown, malformed, suspended, and retired routes.

It does not own application runtimes, application endpoints, data, secrets, provider integrations,
Application Principals, Feature Entitlements, or product behavior. A future provider adapter must
apply one whole compiled generation and preserve or restore the Last Reviewed Working Configuration
on failure. Applying that behavior is not part of this documentation slice.

### Application Attachment

An Application Attachment is the only seam from the Shared Edge to an application-owned runtime.
An Application Registration supplies one or more versioned attachment references. Each reference
contains only the information necessary to select an allow-listed adapter and bind an application
subpath to an application-owned target. It is data, not executable configuration.

An attachment reference must include an immutable application identifier, a registration-local
attachment identifier, an adapter kind, a non-secret resource reference, a canonical mount path, a
forwarding mode, and its identity requirement. It must not contain credentials, secret payloads,
arbitrary provider commands, Terraform state addresses, or catalogue content.

Application State owns the target runtime and every access policy attached to that runtime.
Platform State may own edge-only connector resources and may publish a versioned caller-principal or
audience reference for the Application Owner to consume. Neither state may create, update, import,
or delete a resource owned by the other. A resource reference grants no state access and transfers
no ownership.

Protected attachments must accept traffic only through the Shared Edge using both network or
provider admission controls and verified application-side identity validation. A signed identity
header alone is not permission to expose a public origin. The exact provider adapter and live
direct-bypass qualification belong to later slices.

### GCP Cloud Run attachment profile

The first provider adapter kind is `gcp-cloud-run-v1`. Its resource reference is inert data with
the exact grammar
`urn:comfforts:app-platform:gcp:cloud-run:<project-number>:<region>:<service-name>`. It is not a URL,
credential, Terraform address, or permission to discover arbitrary resources.

The future adapter may resolve only the named Cloud Run service through GCP metadata and IAM. A
target is activation-eligible only when provider readback establishes that the exact service exists
in the declared project and region, reports ready, is assigned to the registration's named
Application State owner, and has an Application-Owner-approved grant for the platform edge caller.
No independent DNS check is part of ownership proof.

The first live fixtures may use Cloud Run services in the qualification project while preserving
separate platform and per-fixture state roots. The same reference grammar permits later
cross-project targets, but same-project evidence does not qualify them. Later cross-project GCP
applications use a platform-owned Shared VPC host network, with the application project attached
as a service project through its own adoption procedure. Network attachment does not give Platform
State ownership of the application's Cloud Run service, IAM policy, data, or Terraform state.

Protected services require both provider-level direct-invocation denial and application-side
assertion verification. The load balancer-to-edge and edge-to-application trust details are refined
by the later identity profile; topology selection alone is not evidence that either control works.

## Application Registration and Registration Set

An Application Registration is versioned data within a complete Registration Set. The logical
fields are:

- contract version, immutable application identifier, and human review metadata;
- one canonical route prefix;
- safe catalogue metadata and explicit Catalogue Visibility;
- one Admission Mode and its mode-specific policy;
- one lifecycle state;
- one or more Application Attachments; and
- no application Feature Entitlements or product authorization rules.

A Registration Set has a monotonically increasing generation number, the digest of the preceding
reviewed generation when one exists, and a complete collection of current registrations including
retired tombstones. It is the only authoritative input for catalogue, routing, and admission. An
individual registration file, application state output, manual route, or provider console edit is
not another source of authority.

The compiler rejects unknown fields. This prevents an application from smuggling provider commands,
feature permissions, or platform behavior through metadata that a schema does not understand.

### Application releases and registration updates

An application release and an Application Registration revision are independent. A registration
describes the application's platform-facing interface; it is not an inventory of application
versions, images, dependencies, data migrations, providers, feature flags, or internal
configuration. The platform does not poll Application State or require a registration change for
every application deployment.

No registration update is required when an Application Owner changes application-owned behavior
while preserving the registered attachment references and every platform-facing contract. This
includes deploying new code or an image, changing internal dependencies or data, replacing a
runtime behind a stable attachment reference, and changing application-owned Feature Entitlements.
A temporary application failure also does not change registration unless the owner requests an
explicit platform suspension.

The Application Owner must propose an update under the existing immutable application identifier
when any registered value changes, including:

- route prefix, catalogue metadata, Catalogue Visibility, Admission Mode, restricted membership,
  or lifecycle state;
- attachment resource reference, adapter kind, mount path, forwarding mode, identity requirement,
  or audience; or
- the adopted major version of a platform contract.

This is an update to the existing Registered Application, not re-registration as a new application.
The proposed change participates in a new complete Registration Generation and requires the same
validation and Platform Owner review as every other platform configuration change. An application
never writes Platform State or registration-derived edge resources directly.

When an update replaces an attachment reference, the future operational sequence is:

1. The Application Owner deploys the new attachment through Application State while keeping the
   currently registered attachment available.
2. The owner proposes a Registration Set generation that references the new attachment.
3. The platform validates and atomically activates the complete compiled generation.
4. The old attachment remains available through the declared acceptance and rollback window.
5. Only after acceptance may the Application Owner retire the old attachment through Application
   State.

Failure before activation leaves the current Registration Generation and attachment authoritative.
Failure after activation rolls the Shared Edge back as a whole generation without transferring or
deleting either attachment. Exact acceptance windows and live procedures belong to later
implementation and evaluation authorities.

## Route model

### Application prefix

Version 1 uses one lowercase top-level segment as the public application prefix. Its canonical form
matches `^/[a-z0-9][a-z0-9_-]*$`. The root `/`, `/_platform` and its descendants, and
`/.well-known` and its descendants are platform-reserved.

Registration authors must supply the canonical form. The compiler rejects uppercase characters,
trailing slashes, empty segments, dot segments, percent encoding, encoded separators, query or
fragment syntax, control characters, and Unicode lookalikes instead of silently rewriting them.
Two registrations may not hold the same canonical prefix, including staged, suspended, or retired
tombstones. A retired prefix is not silently reassigned to another application.

A request belongs to an application only when its path equals the registered prefix or begins with
that prefix followed by `/`. Textual prefix matches such as `/app2` for `/app` are forbidden.

### Attachment mount

An attachment mount is `/` or a canonical segment path relative to the application prefix. Multiple
attachments are selected by longest segment-bounded mount; equal or otherwise ambiguous mounts are
invalid. Version 1 supports only these explicit forwarding modes:

- preserve the complete external request path;
- remove the application prefix; or
- remove the application prefix and selected attachment mount.

Arbitrary regular expressions, templates, executable rewrites, and application-controlled host
selection are outside the contract. Query data is forwarded as request data and never participates
in route selection.

The root catalogue, reserved platform paths, and application routes are disjoint. Unknown,
malformed, staged, suspended, or retired paths fail closed and never fall through to another
application or expose an attachment reference.

## Catalogue

The catalogue is a read-only projection derived from the same compiled generation as routing. It is
not maintained separately. Only an `active` registration whose Catalogue Visibility is `listed`
appears. `unlisted` is the only other Version 1 visibility value and does not change Admission Mode.

Each entry contains only the immutable application identifier, bounded plain-text title and
summary, canonical route prefix, and an admission label suitable for display. Version 1 catalogue
metadata contains no HTML, scripts, images, arbitrary links, attachment references, allow-list
members, operator metadata, provider data, or secrets. A renderer must escape all text for its
output context and must not interpret catalogue text as markup.

Being listed does not grant admission. Being unlisted does not create a secret route. Catalogue
visibility and admission are validated independently.

## Admission and verified identity

The Registration Compiler accepts exactly the Admission Modes already defined by ADR-003:

- `public`: authentication is not required and Verified Identity Context is not guaranteed;
- `authenticated`: a valid identity from the configured identity boundary is required; and
- `restricted`: a valid identity is required and its exact `(issuer, subject)` pair must be in the
  registration's managed set.

Owner-only access is a restricted set containing the approved owner identity. Email is not an
admission key. Feature Entitlements are prohibited from the registration contract and remain an
application concern after admission.

When identity is present, the Shared Edge supplies a compact signed assertion in the versioned
`X-Comfforts-Verified-Identity` header. The edge must remove any visitor-supplied value before
setting its own. The Version 1 claims contract contains only contract version, issuer, immutable
subject, intended application audience, issued-at time, expiry time, and request correlation
identifier. Email and a shared cross-application principal are not required claims.

A protected application must independently verify the assertion signature, configured issuer,
application-specific audience, time bounds, and contract version before deriving its immutable
Application Principal. A missing, malformed, unsigned, expired, wrong-issuer, or wrong-audience
assertion fails closed. A public application may receive no identity and must not invent an
Application Principal for an anonymous request.

The initial provider, session, signing, key-discovery, algorithm, lifetime, skew, and rotation
profile is defined below. It binds the existing Version 1 claims without adding email, provider
tokens, product roles, or Feature Entitlements to Verified Identity Context.

Admission-policy revocation takes effect at the next request or new streaming-connection boundary.
This design does not promise termination of an already established connection. Application feature
revocation remains application-owned.

### Initial Live identity and session profile

The Shared Edge uses Google OIDC authorization code with PKCE and accepts only a verified Google
issuer and immutable subject. Both consumer Google and Google Workspace accounts may authenticate.
The Registration Set, not the identity provider, decides whether that identity is admitted to a
restricted application. The initial profile requires no MFA claim.

The edge creates an opaque Platform Session backed by minimal Firestore Native state in the
qualification project and region. The browser cookie is host-only, `Secure`, `HttpOnly`,
`SameSite=Lax`, and scoped to `/`. The session expires absolutely after eight hours and cannot be
silently renewed past that boundary. The platform retains no Google access or refresh token and
does not use Visitor identity to call Google APIs.

A valid session may add Verified Identity Context to a public request, while an absent or invalid
session leaves a public request anonymous. A protected request without a valid session enters the
edge-owned login flow or fails closed. Restricted membership compares exact issuer-and-subject
pairs from the reviewed Registration Generation. Email is display-only session metadata and never
enters the Version 1 assertion.

The platform-reserved logout operation deletes the server-side session, clears the host cookie,
and accepts only a validated platform-relative return location. It does not revoke the global
Google session. An application may link to this operation from any registered path but cannot
implement a second authoritative logout for the Platform Session.

After admission, the edge strips the identity header and creates a compact assertion with a maximum
60-second lifetime and at most 30 seconds of verifier clock skew. A new assertion is issued for each
forwarded request or new streaming connection. One environment signer uses a software-protected
Cloud KMS `EC_SIGN_P256_SHA256` key in `us-west1`, emits `ES256` with a version-specific key
identifier, and binds every assertion to the registered
`urn:comfforts:app-platform:audience:<application-id>` value.

Only public verification keys are exposed through `/.well-known/jwks.json`. A new key is published
before activation, one version signs, and the preceding key remains published for a 24-hour overlap.
Rotation occurs at least every 90 days. Applications may cache keys for 15 minutes, refresh once on
an unknown key identifier, and otherwise fail closed when verification material is unavailable or
stale.

The initial Live profile makes no distributed replay-prevention claim. Short lifetimes, unique
correlation identifiers, audience binding, TLS, Cloud Run caller IAM, and optional bounded local
replay checks reduce but do not eliminate replay risk. The Cloud Run edge-caller identity proves
workload origin; it is not the Visitor and never becomes Verified Identity Context.

Existing application-managed login remains outside this trust boundary. IAP and
`@react-oauth/google` may continue on existing deployments, but a future Application Adoption must
remove or isolate them from the platform route before their claims can be treated as application
identity.

## Lifecycle and atomic change

Version 1 defines four lifecycle states:

- `staged`: contract-valid but absent from catalogue and routing;
- `active`: eligible for the declared catalogue visibility, routing, and admission behavior;
- `suspended`: retained for review but absent from catalogue and routing;
- `retired`: terminal tombstone, absent from catalogue and routing.

A new application first enters `staged`. Valid transitions are `staged -> active`,
`staged -> retired`, `active -> suspended`, `active -> retired`, `suspended -> active`, and
`suspended -> retired`. Content may be revised while staged, active, or suspended through a new
Registration Generation. Retired registrations cannot change or reactivate, and their application
identifiers and route prefixes remain reserved.

The compiler compares the proposed set with the preceding generation and rejects skipped,
conflicting, stale, or otherwise invalid transitions. Activation is a whole-generation operation:
catalogue, route, admission, attachment, and ownership outputs cannot be accepted independently.

If validation fails, no compiled generation is produced. If a future adapter cannot realize a
compiled generation completely, it must preserve or restore the Last Reviewed Working
Configuration. Suspension or retirement removes the application's platform presence but never
deletes or mutates its Application State.

### Initial Live generation activation

The reviewed Registration Set remains in Git and compiles before planning into an immutable,
content-addressed GCS configuration object. One candidate Cloud Run edge revision binds the exact
source commit, compiler, generation digest, object generation, container image digest, identity
profile, and adapter configuration. The candidate receives no user traffic while attachment,
ownership, IAM, and provider dependencies are validated.

The current Live generation pointer is the Cloud Run service's 100-percent traffic assignment to
one immutable edge revision. Owner-approved activation changes that pointer once. The load balancer
continues to forward all application traffic to the edge and contains no registration-derived
prefix map. There is no registration API or database in the initial profile.

Readback compares protected-main source and plan digests, Terraform state, provider revision and
traffic data, the edge's operator-authorized generation status, observable catalogue and route
behavior, attachment and identity configuration, direct-origin denial, and the State Ownership
Manifest. Any disagreement makes the generation unqualified even if the apply command returned
success.

Rollback changes the traffic pointer to the retained preceding revision as a whole and repeats
readback. The objective is restored traffic assignment and readback within 15 minutes after owner
approval. Rollback does not change Application State. The previous configuration object, edge
revision, and replaced application attachment remain available for at least 24 hours; later cleanup
requires a separate owner-approved action.

Provider partial failure stops for inspection. There is no automatic rollback, unlock, state push,
target deletion, or DNS change. The predecessor digest, workflow concurrency, state lock, and
provider revision precondition reject stale or competing changes.

### Initial DNS and TLS sequence

`apps-staging.comfforts.com` is a new qualification record with a 1,800-second TTL. The load
balancer, reserved address, closed-default edge, and certificate configuration are read back before
the Platform Owner separately approves record creation. The operator checks authoritative and
recursive DNS with `dig`, waits for the Google-managed certificate to report active, and then runs
the Live route and identity readback.

The TTL controls resolver caching rather than guaranteeing propagation time. Failure may cause the
owner to remove or restore only the new qualification record after inspection, with cached answers
remaining possible through the TTL. DNS action never changes a Registration Generation and never
touches `apps.comfforts.com` or any Finance Assistant hostname, record, certificate, load balancer,
or state.

## Exclusive state ownership

Every managed resource has exactly one owner recorded in the versioned State Ownership Manifest.
Logical ownership is fixed as follows:

| Resource or concern | Exclusive owner |
| --- | --- |
| Hostname-level edge, catalogue, routing, admission, and edge-only connectors | Platform State |
| Application runtime, endpoint policy, data, secrets, and providers | Named Application State |
| Application Principal mapping and Feature Entitlements | Named Application State |
| Fixture runtime, data, principals, and entitlements | Fixture Application State |

The manifest records canonical, non-secret resource references, owner class, owner identifier, and
contract revision. The same canonical resource reference cannot appear under two owners. A
platform-managed resource may refer to an application-owned attachment, and an application-managed
resource may consume a platform output, but a reference is not management authority.

No platform lifecycle action imports, recreates, or destroys an application resource. No
application lifecycle action mutates or destroys the Shared Edge. Future adoption or state-transfer
procedures must prove that a resource leaves one state before another state assumes it.

### Initial Terraform state and operator profile

The planned Terraform layout contains one backend-bootstrap root, one Platform State root, and one
Fixture Application State root per fixture. The bootstrap and platform roots use different keys in
one platform-state GCS bucket. Every fixture uses its own GCS bucket and root. Future application
projects retain their own backends. This physical separation supports, but does not replace, the
State Ownership Manifest and provider readback.

GCS locking serializes each root. Object versioning retains a noncurrent state version until both
90 days have elapsed and at least 20 newer generations exist. Backend contents, locks, plans, and
recovery copies are restricted operational data and never enter Git or evidence artifacts.

The only normal mutation path is an exact protected-main plan executed by GitHub Actions through
OIDC and GCP Workload Identity Federation after explicit environment approval. Pull requests receive
deterministic checks and advisory read-only plans; the merge commit is planned again and bound to
the apply by source and plan digests. Each workflow identity is limited to its named root and
operation. One concurrency guard and the backend lock prevent competing mutations.

The dedicated repository, branch, workflow, and environment values must be known after extraction
before a federation binding can exist. Until then, this is planning authority only. Local checks,
validation, read-only planning, and readback remain available, but normal local apply is prohibited.
An owner-declared break-glass operation uses short-lived credentials, exact targets, state backup,
readback, and reconciliation; it never uses a stored service-account key.

Bootstrap, import, force-unlock, state push, backend changes, rollback, and destroy are explicit
operator procedures rather than hidden Terraform side effects. A provider error stops for
inspection. Manual console changes remain drift and cannot become the reviewed baseline without a
source change.

## Failure and rollback behavior

- Schema, semantic, transition, or ownership failure produces ordered violations and no compiled
  output.
- An unmatched or malformed request receives a closed platform response and is not forwarded.
- An unavailable attachment fails for that application only; the edge does not retry against a
  different application.
- Missing or invalid identity fails protected admission and application-side verification.
- Staged, suspended, and retired registrations produce no live route or catalogue entry.
- Provider-console or hand-written route changes are drift and cannot become the reviewed baseline.
- Rollback selects a previously reviewed whole generation; it never rolls back or deletes
  Application State.

Runtime status, provider health, and live rollback require measured evidence from later evaluation
gates. Static configuration or a successful compiler run is not runtime qualification.

## Threat and data boundary

Registrations, catalogue text, attachment references, identity headers, request paths, provider
payloads, and operator-supplied configuration are untrusted inputs. Every interface is bounded,
strictly parsed, and allow-listed before it can influence derived configuration. The dedicated
[threat model](06_threat_model.md) owns the detailed trust zones, abuse cases, controls, residual
risks, and future qualification mappings.

Platform logs and evidence may contain contract versions, generation digests, immutable application
identifiers, route identifiers, coarse admission outcomes, violation codes, and correlation
identifiers. They must not contain secret payloads, raw credentials, restricted allow-list contents,
signed assertions, provider payloads, application request bodies, or application data. A
correlation identifier is not an identity or authorization signal.

The initial logging, evidence, incident, and cost profile is defined below. Its selection does not
make a sink, retention policy, alert, responder, quota, or budget operational.

### Initial logging, evidence, incident, and cost profile

The edge emits one structured completion event per request or streaming connection into a dedicated
Cloud Logging bucket in the qualification project and `us-west1`. Seven-day retention and
owner-only access apply. Events contain only generation, application and route identifiers, coarse
outcomes, status class, latency, correlation identifier, and non-secret platform versions. They
exclude identity, visitor metadata, payloads, application data, assertions, sessions, secrets,
state, saved plans, and stream chunks. Logs have no external sink.

Control-plane events record digest-bound plan, apply, activation, rollback, DNS/TLS, key, IAM,
state, drift, break-glass, incident, and destructive-cleanup outcomes without copying protected
payloads. Provider-required administrative audit metadata remains restricted inside the project and
is not copied into platform evidence.

Secret-free Live evidence is a 30-day, owner-readable bundle in a dedicated GCS evidence bucket.
It contains revision and plan digests, generation and image digests, redacted provider and runtime
readback, commands, timestamps, results, failures, limitations, and evidence-class labels. A
screenshot or raw provider export is not an authoritative record. Git may hold only a reviewed safe
index or digest.

The App Platform Owner is the initial incident responder. Response stops new mutation, identifies
the revision and generation, preserves permitted evidence, and requires an explicit decision for
suspension, rollback, secret rotation, or cleanup. Only budget notifications are automated in the
first profile; later security or availability alerts require measured operating needs and a new
reviewed decision.

The project budget is USD 20 per month with owner notifications at 50, 80, and 100 percent. The
80-percent threshold pauses new billable changes, and the 100-percent threshold requires an owner
continuation, suspension, or teardown decision. No threshold disables billing or mutates resources
automatically.

The Shared Edge uses zero minimum and two maximum 1-vCPU, 512-MiB Cloud Run instances at concurrency
20. Each Fixture Application uses zero minimum and one maximum instance with the same CPU and memory
at concurrency 10. Streams last at most 55 minutes and hold concurrency while open. The initial
profile has one non-production edge and load balancer and no CDN, WAF, HSM, production replica,
always-on instance, Firestore backup, or Firestore point-in-time recovery.

Firestore holds only expiring Platform Sessions. KMS keeps only active and required overlapping
verification versions. Artifact Registry retains active, rollback, and current-candidate images;
cleanup begins in dry-run and deletion remains owner-approved. Terraform checks reject unbounded or
larger runtimes, extra environments or edges, unapproved billable services, longer retention, and
missing `environment`, `managed_by`, `state_owner`, or applicable `application_id` labels.

The platform project pays for Shared Edge and initial same-project qualification resources. Later
application projects pay for their runtime, data, networking, and provider services unless their
Application Adoption explicitly records another allocation.

### AP-M6 networked runtime profile

AP-M6 implements one deep Shared Edge module behind this external interface:

```text
create_app(runtime_configuration, adapters) -> ASGI application
```

The returned application is the interface used by the server and by integration tests. It accepts
all network requests through one pipeline and hides catalogue projection, reserved paths, route
selection, admission, identity assertion, attachment resolution, forwarding, limits, failure
mapping, and completion-event redaction. Framework routes may identify platform-reserved paths and
one catch-all entry, but they may not duplicate registration-derived application routes.

The implementation uses Python 3.12 or newer, Starlette as the ASGI framework, and Uvicorn as the
server. Provider and network behavior is accepted through internal seams for immutable generation
loading, Google OIDC, Platform Sessions, assertion signing and public-key discovery, Cloud Run
metadata, upstream HTTP/WebSocket transport, trusted client classification, and time. Each seam has
both a production adapter and a deterministic fake before it is treated as real. Callers do not
assemble the request pipeline or depend on those internal interfaces.

The application-side verifier is a separate deep module with one interface that accepts an
assertion, expected issuer, expected application audience, verification material, and time, then
returns either Version 1 Verified Identity Context or an ordered verification violation. It does
not perform admission, create an Application Principal, or grant a Feature Entitlement.

Direct dependencies are declared in `pyproject.toml`; complete transitive resolution is committed
in `uv.lock`. Runtime work adds a dependency only with its first production use. The selected
families are Starlette and Uvicorn for ASGI, HTTPX and `websockets` for upstream transport, Authlib
and `cryptography` for OIDC and ES256, and official Google Cloud clients for Storage, Firestore,
KMS, Cloud Run metadata, and service identity. Production code may not hand-build provider signing,
token, or discovery protocols. `make check` consumes an already synchronized locked environment;
it performs no installation or network access.

AP-M6-W3 accepts at most one mebibyte from the exact configured Cloud Storage object generation
through an injected source adapter; the ranged read includes only one additional byte needed to
detect overflow. Startup verifies the raw SHA-256 content digest, applies the Version 1
duplicate-safe JSON and compiled-configuration schema profile, and verifies the compiled generation
digest before binding the generation in memory. Any missing adapter, source failure, invalid
document, invalid contract, or digest mismatch fails startup with a coarse code. Loading does not
discover storage, compile registrations, follow a mutable pointer, activate a provider revision, or
reload during the process lifetime.

The initial `qualification-v1` request profile applies before target selection and permits lower
environment settings but no higher value without a reviewed profile change:

- ASCII methods of at most 16 bytes, raw paths of at most 4,096 bytes, and queries of at most 8,192
  bytes;
- at most 64 request headers, with an ASCII name of at most 128 bytes, a value of at most 8,192
  bytes, and at most 32,768 aggregate header bytes;
- at most 25 MiB per request body and per buffered response body;
- at most 100 MiB per streamed HTTP response, SSE connection, or WebSocket connection, with at most
  1 MiB in one WebSocket message;
- a 10-second upstream connection timeout, a 300-second non-streaming request timeout, a 300-second
  streaming idle timeout, and the already selected 55-minute absolute streaming lifetime; and
- at most 20 active requests and 10 streaming connections per edge instance, with at most four
  streams for one trusted client key.

The profile uses an in-memory, per-instance token bucket of 120 request starts per minute per
trusted client key with a burst of 40, 10 login starts per 10 minutes per key, and 20 WebSocket
messages per second with a burst of 40. It also caps all request starts at 600 per minute per
instance with a burst of 100. Client keys come only from load-balancer-authenticated metadata, are
held for at most 10 minutes, and are never logged or persisted. When trusted client metadata is
unavailable, only the instance-wide cap applies. This is bounded demo abuse resistance, not a
distributed rate-limit or WAF claim; two instances can independently permit their full limits.

Limit or saturation rejection occurs before application selection where possible, returns a closed
`413`, `429`, or protocol-appropriate close result, and records only the coarse outcome and
correlation identifier. The runtime drains or cancels bounded work and does not continue an
upstream operation after the visitor connection or platform timeout closes it. The body and header
caps remain below the selected provider limits while retaining room for provider-added metadata.
Specifically, 25 MiB is below Cloud Run's 32-MiB HTTP/1 request and buffered-response limits, the
55-minute stream lifetime is below its 60-minute request maximum, and the 32-KiB aggregate header
cap plus bounded path and query leaves room below the global external Application Load Balancer's
60-KiB combined request-header and URL limit. See the provider's
[Cloud Run quotas](https://cloud.google.com/run/quotas),
[request-timeout guidance](https://cloud.google.com/run/docs/configuring/request-timeout), and
[load-balancer quotas](https://cloud.google.com/load-balancing/docs/quotas). Larger uploads or
downloads require a later reviewed profile rather than an application-specific exception.

## Fixture boundary

Fixture Applications are contract consumers, not internal compiler branches or privileged platform
runtimes. Each fixture registers and attaches through the same Version 1 contracts as any other
application. Its runtime, synthetic data, Application Principals, Feature Entitlements, and Fixture
Application State remain outside Platform State.

Contract test vectors may use synthetic application names and identities to validate schemas and
compiler behavior. They are not Fixture Applications and cannot qualify routing, identity delivery,
direct-bypass denial, lifecycle operations, or rollback. Delivery item 4 must introduce independent
fixture registrations and application-owned fixture implementations.

### Deterministic reference topology

Item 4 uses one Python standard-library, in-process request pipeline. Its external seam is one
bounded `handle(request) -> response` operation over ordinary immutable request and response values.
It opens no listening socket and performs no HTTP, DNS, TLS, filesystem, subprocess, credential, or
cloud operation. An injected clock and explicitly constructed adapters make every result
deterministic.

```text
 reviewed fixture Registration Set
                |
                v
      Registration Compiler
                |
                v
 immutable compiled generation ---> in-memory generation activation
                                           |
 synthetic request ------------------------v
                               Deterministic Reference Edge
                                 | catalogue / closed response
                                 | admission + identity assertion
                                 v
                         fixture-in-process-v1
                                 |
                                 v
                       Fixture Application State
```

The Deterministic Reference Edge is a fixture adapter for the logical Shared Edge interface. It
must derive catalogue, route, admission, attachment, and lifecycle behavior only from one compiled
generation. It may not add a route, admission exception, or catalogue entry through constructor
options or fixture-specific branching. Provider-facing behavior, network ingress, TLS, concurrency,
streaming, availability, and performance are outside this adapter and outside Fixture evidence.

The only enabled attachment adapter kind is `fixture-in-process-v1`. Its resource references use
`urn:comfforts:app-platform:fixture:<application-id>:<attachment-id>` and are inert lookup keys into
an explicitly supplied read-only attachment map. Resolution performs no import, fetch, discovery,
or dynamic execution. This selection does not define a live provider adapter or change the Version
1 attachment schema.

### Fixture Application set

The fixture qualification set contains exactly three independent applications:

| Fixture | Catalogue | Admission | Application-owned behavior |
| --- | --- | --- | --- |
| `fixture-public` | Listed | Public | Returns synthetic public content and exposes two mounts for forwarding and longest-match checks |
| `fixture-authenticated` | Unlisted | Authenticated | Derives an application-scoped principal only after independently verifying the edge assertion |
| `fixture-restricted` | Listed | Restricted | Admits one exact synthetic issuer-and-subject pair and separately denies an admitted principal a synthetic premium Feature Entitlement |

Each fixture has its own runtime object, mutable synthetic state, principal map, entitlement policy,
and assertion verifier inside separately constructed Fixture Application State. The platform holds
only the attachment reference and callable adapter supplied at construction. One fixture cannot
read or mutate another fixture or the platform's generation state. Finance Assistant code, data,
infrastructure, identity, state, and migration are never fixture dependencies.

### Request, catalogue, and response profile

The item 4 pipeline accepts `GET` only and applies these fixture-only limits before routing or
admission:

- an ASCII method of at most 16 bytes;
- a raw path of at most 1,024 UTF-8 bytes and query data of at most 1,024 UTF-8 bytes;
- at most 32 headers, with an ASCII name of at most 64 bytes, a value of at most 1,024 UTF-8 bytes,
  and at most 8,192 aggregate header bytes;
- an empty request body; and
- a response body of at most 65,536 UTF-8 bytes.

Unsupported methods, malformed text, duplicate security-sensitive headers, limit violations, and
non-empty bodies fail before attachment selection. These bounds qualify only this synchronous,
in-process profile. Connection, streaming, network timeout, traffic-rate, concurrency, and live
provider limits remain unresolved.

The root `/` response is UTF-8 HTML derived from the compiled catalogue. The renderer escapes every
text field for HTML and constructs each link only from the canonical registered route prefix. It
does not accept templates, raw markup, arbitrary links, attachment references, or operator data.
Deterministic tests inspect the parsed links and literal text; they do not require a browser.

Unknown, malformed, reserved, staged, suspended, and retired paths return a closed platform
response and never invoke an attachment. Authentication failures are distinct from restricted
membership denial, but neither response reveals membership, attachment, or application-state
details. An unavailable or oversized fixture response fails only the selected application and is
never retried against another fixture.

### Synthetic identity and application verification

The fixture identity adapter recognizes only an explicit in-memory mapping from synthetic session
labels to immutable `(issuer, subject)` pairs. Those labels and identities are test data, not
credentials or an identity-provider simulation. Before routing, the edge removes every
visitor-supplied `X-Comfforts-Verified-Identity` value.

After successful protected admission, a fixture-only signer wraps the existing Version 1 Verified
Identity Context in a deterministic HMAC-SHA-256 envelope. The signer uses injected, explicitly
public test key material; it is not a production algorithm or key-management choice. Assertions
have a maximum 60-second lifetime, allow zero clock skew, and use their correlation identifier as
the replay identifier. Each protected fixture independently verifies the envelope, contract
version, signature, issuer, application-specific audience, issued and expiry times, and replay
identifier before deriving an Application Principal. A bounded 256-entry replay store removes only
expired entries and fails closed when no safe capacity remains.

Tests must call a protected fixture directly with a missing, forged, expired, wrong-issuer,
wrong-audience, cross-application, and replayed assertion and observe denial. This is evidence of
application-side assertion verification only. An in-process call cannot prove network origin
isolation, provider IAM, key protection, or denial of a live direct-origin request; those remain
Live and Adoption gates.

### Registration, activation, and lifecycle

Fixture registrations are committed, reviewed files that form complete Registration Sets. Item 4
adds no external registration endpoint, self-service registration flow, or database. A proposed
fixture change is compiled through the Version 1 compiler, then the complete generation is either
installed in an in-memory reviewed-generation collection and selected by one current-generation
pointer or rejected without changing runtime state.

Activation swaps catalogue, routes, admission, attachments, and ownership as one generation.
Rollback selects a retained, previously reviewed complete generation. It does not reverse or
delete Fixture Application State. Tests must cover initial registration, an application release
that preserves its registration, a registration update, suspension, retirement, attachment
replacement, failed activation, and rollback. A process restart deliberately loses this in-memory
activation state; persistence, concurrent writers, and an operator control plane remain later
design decisions.

This Git-reviewed, in-memory mechanism is the item 4 qualification harness, not a commitment that
future real applications must use an external API or a database. Application Adoption must select
and authorize its onboarding and operational workflow without weakening complete-generation review
or exclusive state ownership.

### Fixture evidence boundary

Fixture evidence may qualify deterministic catalogue rendering, routing, forwarding, admission,
synthetic identity delivery and application verification, application-owned entitlement denial,
lifecycle behavior, rollback, failure isolation, state isolation, limits, and redaction through the
same in-process seams used by callers. It may not qualify network reachability, DNS, TLS, OAuth,
real credentials, signing-key custody, provider resources, IAM, direct-origin network denial,
availability, performance, persistence, Application Adoption, or any Finance Assistant behavior.

This section is design authority only. No Fixture (`F`) evidence exists until a later approved item
4 plan, implementation, and evaluation record exercise these claims.

Finance Assistant code, data, infrastructure, identity, state, and migration are never fixture
dependencies. Its Integration Draft remains an inactive compatibility input.

## Configurability and extraction

Canonical documents, schemas, validation code, test vectors, and tests use project-relative paths
inside the App Platform root. Contract identifiers do not encode the containing repository, a cloud
project, a deployment region, or Finance Assistant. Default verification performs no network or
credential access and no cloud, DNS, identity, or application mutation.

Extraction to a dedicated repository changes the project root but not contract identifiers,
compiler behavior, paths relative to that root, or ownership boundaries.

## Explicitly unresolved implementation decisions

This design intentionally does not implement:

- Terraform modules, bucket names, backend objects, workflows, repository-bound federation,
  resource names, state-transfer commands, or IAM grants for the selected state and operator model;
- OAuth client registration values, Firestore session configuration, KMS key versions, secret
  versions, credentials, or IAM bindings for the selected identity profile;
- a live catalogue, Shared Edge runtime, `gcp-cloud-run-v1` resolver, external registration
  endpoint, registration database, or operator control plane;
- a configuration bucket, compiled generation object, candidate edge revision, traffic change,
  DNS record, certificate activation, readback execution, or rollback execution;
- a log or evidence bucket, sink, retention rule, budget, alert, runtime scaling setting, cleanup
  policy, label policy, incident automation, or cost-response action;
- Finance Assistant registration, Application Adoption, migration, access expansion, or cutover.

AP-M6 now resolves the network framework, dependency policy, and initial header, body, timeout, and
abusive-traffic limits as implementation authority. Their presence in this design does not make the
runtime, production adapters, provider resources, or Live behavior implemented or qualified.

The implementation plan, evaluation strategy, threat model, versioned schemas, and deterministic
validation added by this delivery item may constrain later work. They cannot describe an unresolved
runtime or control as operational.

## Design acceptance boundary

This system design remains documentation authority rather than operational evidence. AP-M3 provides
revision-scoped Contract evidence that the Version 1 schemas and deterministic reference compiler
satisfy their declared offline gate. AP-M4 supplies the Fixture evidence defined by Version 0.2.
Version 0.3 selects the initial GCP Live topology, Version 0.4 selects its identity trust profile,
Version 0.5 selects state and operator authority, Version 0.6 selects activation, DNS, readback, and
rollback behavior, Version 0.7 selects observability, evidence, incident, and cost controls, and
Version 0.8 selects the AP-M6 network module, dependency, and bounded-request profile. None supplies
Terraform, provider, network, identity, deployment, or Live evidence. Adoption qualification
remains a later application-owned gate.

## Design trace

| Design area | Requirements | Decisions |
| --- | --- | --- |
| Shared Edge and catalogue | AP-PR-001, AP-PR-003; AP-QR-002, AP-QR-006 | ADR-001, ADR-002 |
| Registration, routing, and compiled generations | AP-PR-002, AP-PR-003, AP-PR-007; AP-QR-004, AP-QR-006 | ADR-002 |
| Attachments and exclusive ownership | AP-PR-002, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-003 | ADR-001, ADR-002, ADR-004, ADR-007 |
| Admission and verified identity | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002 | ADR-003, ADR-004, ADR-006 |
| Lifecycle, failure, and rollback | AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-005, AP-QR-006 | ADR-002, ADR-004, ADR-008 |
| Fixture and adoption boundary | AP-PR-008, AP-PR-009; AP-QR-003, AP-QR-004, AP-QR-006 | ADR-004 |
| Initial GCP Live topology and Cloud Run attachments | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-003, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005 |
| AP-M6 network module and bounded-request profile | AP-PR-001 through AP-PR-008; AP-QR-002 through AP-QR-006 | ADR-001 through ADR-006, ADR-008, ADR-009 |
| Terraform state and operator authority | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-007 |
| Observability, evidence, incidents, and cost | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-009 |
