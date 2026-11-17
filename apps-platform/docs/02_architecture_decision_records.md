# App Platform architecture decision records

Version 0.6 | Status: accepted decisions through initial Live qualification planning; no platform infrastructure is implemented

These records capture hard-to-reverse App Platform boundaries. They are authoritative only for this
project and do not transfer ownership of an existing application's resources. Requirement
identifiers refer to [the product requirements](01_product_requirements.md).

## ADR-001 · The platform owns the Shared Edge, not application runtimes

Status: Accepted

Requirements: AP-PR-001, AP-PR-003, AP-PR-006, AP-PR-007, AP-QR-001, AP-QR-002

### Context

Multiple independently governed applications must share one configured hostname. If each
application owns hostname-level resources, catalogue behavior, or routing, then DNS and route
changes can collide and one application's lifecycle can break another. If the platform instead owns
application runtimes and data, it becomes coupled to product-specific scaling, secrets, providers,
rights, recovery, and authorization.

### Decision

The App Platform owns the Shared Edge for a configured hostname. That ownership includes:

- the desired DNS record and its reviewed operator procedure;
- hostname-level addresses, certificates, forwarding, proxies, load balancing, routing, and
  platform-owned operational paths;
- the root application catalogue;
- registration-derived edge resources used only to attach an application to the Shared Edge; and
- enforcement of the admission policy declared by each Application Registration.

A certificate secures a hostname or approved hostname pattern; a route prefix such as
`/finance_assistant` is not a certificate boundary.

Each Registered Application retains ownership of its runtime, application endpoints, data stores,
secrets, providers, provider rights, feature authorization, product behavior, and Application State.
It supplies only the versioned attachment references and metadata required by its Application
Registration. The platform must not import, recreate, mutate, or destroy application-owned resources
as a side effect of an edge lifecycle operation.

An application remains responsible for exposing an attachment compatible with the platform's
fail-closed and no-direct-bypass requirements. The attachment mechanism and validation protocol are
deferred to system design and contracts.

### Considered alternatives

- **Let the first application continue to own the shared hostname:** rejected because application
  teardown or replacement would continue to control every other application's entry point.
- **Let every application manage its own hostname-level edge:** rejected because one hostname cannot
  safely have competing DNS, certificate, forwarding, catalogue, and route owners.
- **Let the platform own application runtimes and data:** rejected because it would merge Platform
  State with product-specific lifecycle, rights, recovery, and authorization concerns.

### Consequences

- Shared-edge and application-runtime lifecycle operations are separate and independently reviewed.
- A Registered Application may be unavailable without transferring its data or runtime into
  Platform State.
- Existing Finance Assistant edge resources remain Finance Assistant-owned until a later migration
  is explicitly adopted and qualified; this decision does not move them.
- Migration must transfer or replace shared-edge ownership deliberately rather than create two
  active owners for the same hostname-level resource.

## ADR-002 · Versioned registrations derive routing without shared state ownership

Status: Accepted

Requirements: AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-009, AP-QR-001, AP-QR-003, AP-QR-006

### Context

The Shared Edge needs application metadata and endpoint references, but sharing Terraform ownership
or relying on manual route edits would couple application releases to the platform and make the
active configuration difficult to validate, reproduce, or roll back.

### Decision

A versioned Application Registration is the only authoritative input for adding an application to
the catalogue and Shared Edge. Before a registration may change active routing, the platform must
validate the complete registration set for schema conformance, unique normalized route prefixes,
reserved-path conflicts, valid lifecycle state, compatible attachment references, and safe catalogue
metadata.

Platform State owns the shared resources and registration-derived edge resources it creates.
Application State owns the application runtime and exports only versioned attachment references; an
exported reference does not transfer ownership. No resource may be managed by both states, and
neither state may delete resources owned by the other.

An accepted registration change produces one reviewed platform configuration. Invalid or partially
applied changes must fail closed and preserve or restore the last reviewed working configuration.
Retiring a registration removes its catalogue and edge presence but does not destroy its application
runtime or data. Direct manual route changes are drift, not an alternative source of authority.

The registration schema, storage format, application-attachment types, update transaction, and
rollback implementation remain contract and system-design decisions.

### Considered alternatives

- **Use one Terraform state for the platform and every application:** rejected because independent
  application lifecycle would be lost and a state operation could mutate unrelated products.
- **Read application resources directly from application state:** rejected as an ownership leak that
  couples the platform to another project's state layout and access policy.
- **Maintain catalogue and routing manually:** rejected because manual edits are not deterministic,
  revision-scoped, or reliably reversible.

### Consequences

- Application onboarding requires a reviewed registration and a compatible app-owned attachment.
- Registration validation and conflict detection must exist before live platform mutation.
- Platform planning can be deterministic without application credentials or application-state write
  access.
- Future contracts must define stable attachment references without expanding platform ownership.

## ADR-003 · Platform admission does not grant application feature access

Status: Accepted

Requirements: AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008, AP-QR-002

### Context

Requiring one owner allow-list for an entire application conflates two different questions: whether
a request may reach the application and whether that person may use a restricted application
feature. This would unnecessarily block otherwise available functionality and would make the
platform responsible for product-specific provider plans, rights, and authorization rules.

### Decision

The Shared Edge makes an Admission Decision using the Admission Mode in the Application
Registration:

- **Public:** a request may reach the application without authentication; verified identity context
  is not guaranteed.
- **Authenticated:** any identity successfully authenticated by the configured identity boundary may
  reach the application.
- **Restricted:** only an authenticated identity included by the registration's admission policy may
  reach the application. Owner-only access is one restricted policy configuration.

Catalogue visibility is separate from Admission Mode. Being listed does not grant admission, and
being admitted does not grant a Feature Entitlement.

When authentication occurs, the platform supplies minimal Verified Identity Context through a
versioned, verifiable contract. An application derives its own immutable Application Principal from
the verified issuer and subject. Email addresses are display or contact attributes and must not be
used as application resource-ownership keys. Anonymous requests, forwarded user input, and unsigned
or unverified identity headers are not verified identity context.

The Application Owner defines and enforces every Feature Entitlement, including provider-plan and
data-display restrictions. The platform neither interprets those entitlements nor maintains a
cross-application entitlement database. An authenticated person may therefore be admitted to an
application, use its unrestricted functionality, and still be denied a restricted feature such as
live market data.

Admission-policy revocation applies at the next request or new streaming-connection boundary. The
platform does not promise to terminate an already established connection unless a future contract
explicitly requires and qualifies that behavior. Feature-entitlement revocation remains an
application responsibility.

The identity provider, authentication mechanism, identity assertion format, signature validation,
and application-principal derivation contract remain system-design and contract decisions.

### Considered alternatives

- **Restrict every application to one owner allow-list:** rejected because users without restricted
  feature permission may still be allowed to use the rest of an application.
- **Centralize application feature entitlements in the platform:** rejected because provider rights,
  product roles, and application data are outside the platform ownership boundary.
- **Use email addresses as shared resource-owner identifiers:** rejected because addresses are
  mutable attributes and do not form an immutable, application-scoped principal.
- **Let applications trust forwarded identity headers without an edge contract:** rejected because
  direct or spoofed requests could impersonate an authenticated identity.

### Consequences

- Fixture qualification must distinguish public, authenticated, and restricted admission.
- A fixture must prove that an admitted identity can use an unrestricted feature while the fixture
  application denies that identity a market-data-style Feature Entitlement.
- Anonymous access to a public application cannot imply an Application Principal.
- Applications must implement their own principal mapping, data isolation, feature authorization,
  and entitlement revocation.
- Expanding Finance Assistant from owner-only admission remains a future Finance Assistant change;
  this decision does not alter its current access policy.

## ADR-004 · Qualify the platform with fixtures before application adoption

Status: Accepted

Requirements: AP-PR-008, AP-PR-009, AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-006

### Context

Using Finance Assistant as the first platform test would couple platform acceptance to a real
application's runtime, data, access policy, providers, and existing infrastructure. It would also
make platform defects difficult to distinguish from application defects and could transfer resource
ownership before the platform boundary is proven.

### Decision

The App Platform must reach its declared implementation and qualification gates with one or more
deterministic Fixture Applications before any real application may be adopted. A fixture may
live in this project for portability, but it participates as a Registered Application: its runtime,
synthetic data, principals, Feature Entitlements, and fixture Application State remain outside
Platform State.

Together, the fixtures and platform qualification must be able to exercise:

- root catalogue navigation, unique prefix routing, subpaths, and unmatched-path failure;
- public, authenticated, and restricted Admission Modes;
- Verified Identity Context, spoofed-identity rejection, and application principal derivation;
- an admitted identity using an unrestricted feature while being denied a market-data-style Feature
  Entitlement;
- registration, update, suspension, retirement, route isolation, and rollback; and
- rejection of direct access that bypasses a protected Shared Edge.

Fixture behavior and data must be deterministic and synthetic. Fixture qualification must require
no Finance Assistant code, production application data, paid provider, application credential, or
write access to a real application's state.

An Integration Draft may describe how a real application could consume the qualified platform
interfaces, but it is not an application change and is not platform acceptance evidence. Application
Adoption occurs only when the Application Owner incorporates the proposal through that application's
own requirements, decisions, contracts, implementation, tests, state migration, cutover, rollback,
and release approval. A cutover must leave each resource with one active state owner.

The fixture topology, implementation language, synthetic identities, entitlement model, and
qualification evidence schema remain system-design and evaluation decisions.

### Considered alternatives

- **Migrate Finance Assistant before qualifying the platform:** rejected because a real application
  would become both the test harness and the migration subject, obscuring failures and ownership.
- **Treat the existing deployed application as a fixture:** rejected because it contains real access
  policy, credentials, providers, and application state that fixtures must not require.
- **Let platform documents directly amend a consuming application:** rejected because the platform
  cannot authorize changes to another project's requirements, state, or release.
- **Qualify only static configuration:** rejected because routing, admission, identity delivery,
  entitlement separation, lifecycle, and failure behavior are observable runtime boundaries.

### Consequences

- Platform implementation can proceed and be evaluated independently of Finance Assistant.
- Fixture runtime and state must remain separable from Platform State even while colocated.
- Platform qualification proves the platform contracts and controls, not compatibility with every
  application.
- Finance Assistant migration will require a later Finance Assistant-owned slice and evidence.
- History-preserving repository extraction must retain the fixtures and their deterministic checks
  so qualification does not depend on the containing repository.

## ADR-005 · Qualify the first Live topology on GCP with Cloud Run attachments

Status: Accepted

Requirements: AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008, AP-PR-009,
AP-QR-001, AP-QR-002, AP-QR-003, AP-QR-005, AP-QR-006

### Context

The first Live qualification must exercise a real Shared Edge and application attachment without
making Finance Assistant the qualification target, transferring an application's runtime into
Platform State, or duplicating registration-derived routes across provider layers. The topology
must remain inexpensive at demo traffic, support future streaming applications, and admit later
applications that retain their own GCP projects.

### Decision

The first Live qualification uses the dedicated GCP project `comfforts-platform-non-prod`
(project number `455651441682`) and regional resources in `us-west1`. It has no production
environment. The qualification hostname is `apps-staging.comfforts.com`; it does not change
`apps.comfforts.com` or any Finance Assistant hostname, record, certificate, or edge resource.

The platform Shared Edge consists of one global external Application Load Balancer with a reserved
address, a Google-managed certificate, HTTP-to-HTTPS redirection, and one serverless backend that
selects one Cloud Run edge service in `us-west1`. The load balancer does not copy the application
catalogue or registration-derived prefix routes into its URL map. The Cloud Run edge is the single
module that derives catalogue, routing, admission, assertion delivery, and attachment selection
from the active Registration Generation.

The initial live application adapter kind is `gcp-cloud-run-v1`. Its non-secret resource reference
has this exact form:

```text
urn:comfforts:app-platform:gcp:cloud-run:<project-number>:<region>:<service-name>
```

The adapter resolves that typed reference through GCP resource metadata and IAM; it never fetches
an application-supplied URL. Before activation, provider readback must show the exact service in
the declared project and region, a ready target, the named Application State owner in the State
Ownership Manifest, and an application-owner-authorized grant to the platform edge caller. This
joint proof binds the target to the registration without transferring management authority.

The first live Fixture Application targets may share the qualification project with the platform,
but each retains a separate Terraform state root and remains Application State. The reference form
also permits a later target in an application-owned GCP project. Later cross-project GCP
attachments use a platform-owned Shared VPC host network, with each application project attached
as a service project through its own adoption procedure. The platform owns only the host network
and edge identity, while the Application Owner continues to own its Cloud Run service, runtime IAM,
data, and Application State. Cross-project behavior requires its own later evidence.

Protected Cloud Run targets must deny unauthenticated direct invocation and accept the dedicated
edge caller through provider IAM in addition to independently verifying the application-bound
platform assertion. A target needs no independent user-facing hostname or certificate. Public,
authenticated, restricted, and application-entitlement behavior remain Admission and application
authorization choices, not different infrastructure owners.

The edge data path must preserve HTTPS requests required for ordinary responses, SSE, WebSocket,
uploads, and downloads within separately approved limits. Plain HTTP exists only to redirect to
HTTPS. CDN and WAF behavior are not part of the initial qualification topology. DNS record creation
and cutover remain explicit, separately approved operator actions.

### Considered alternatives

- **Reuse an existing application project and edge:** rejected because qualification would couple
  Platform State and lifecycle to an application and complicate later ownership transfer.
- **Put application prefixes in the load balancer URL map:** rejected because the provider map and
  the active Registration Generation could disagree about routing authority.
- **Accept arbitrary application URLs:** rejected because registration could become an SSRF or
  cross-application routing mechanism.
- **Require every application to share the platform project:** rejected because later applications
  must be able to retain project, runtime, data, and state ownership.
- **Qualify Finance Assistant first:** rejected by ADR-004 and because its existing edge, Terraform
  state, and access model remain outside this platform slice.

### Consequences

- The first provider implementation is intentionally GCP-specific; multi-cloud adapters remain
  future independently reviewed capabilities.
- The global load balancer and regional edge have different scopes, and the implementation must
  make that distinction explicit.
- The edge remains a hostname-wide concentration of risk and requires later IAM, identity,
  rollback, observability, and cost evidence before Live qualification.
- A same-project fixture result does not qualify cross-project Shared VPC attachment or any real
  application adoption.
- This decision selects topology only. It creates no Terraform configuration, provider resource,
  DNS record, certificate, credential, deployment, or Live evidence.

## ADR-006 · Use edge-managed Google OIDC and application-bound ES256 assertions

Status: Accepted

Requirements: AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008, AP-QR-002, AP-QR-004,
AP-QR-005, AP-QR-006

### Context

Admission Modes require one consistent authentication boundary at the Shared Edge, while
applications retain their own principals and Feature Entitlements. Existing applications may use
IAP or browser libraries such as `@react-oauth/google`, but trusting those independent mechanisms
inside the platform would create multiple identity authorities, inconsistent logout, and
application-controlled claims at a shared boundary.

The edge caller's workload identity and the Visitor's identity answer different questions. Cloud
Run IAM proves which workload invoked an application target; a signed platform assertion proves
which Visitor, if any, passed platform admission. Neither may substitute for the other.

### Decision

The initial Live identity provider is Google OIDC. The Shared Edge owns the authorization-code flow
with PKCE, provider-token validation, redirect and failure behavior, Platform Sessions, and logout.
Only identities with a valid Google issuer and immutable subject are authenticated. Consumer Google
accounts and Google Workspace accounts are eligible; no other OIDC provider is accepted initially.
The platform requires no MFA claim in the first qualification profile.

The browser receives only an opaque, host-only session cookie with `Secure`, `HttpOnly`,
`SameSite=Lax`, and `Path=/`. Minimal server-side session state is stored in Firestore Native in the
qualification project and region. A Platform Session has an absolute lifetime of eight hours and
cannot be silently extended beyond that boundary; expiry requires Google reauthentication. The
platform stores no Google access token or refresh token because it does not call Google APIs on a
Visitor's behalf. OAuth client secrets and transient verification material remain outside Git and
Terraform state.

A valid Platform Session may supply optional identity to a public route; absence of a session never
prevents public admission and never invents an identity. Authenticated and restricted routes
require a valid session. Restricted membership remains reviewed Registration Set configuration and
matches the exact Google issuer-and-subject pair. Email may be retained only as a display attribute
in the session boundary; it is not an admission key, assertion claim, Application Principal, or
resource-ownership key.

Logout is a platform-reserved operation reachable from the root hostname and from application
paths. It deletes the server-side Platform Session, clears the cookie, and returns only to a
validated platform-relative location. It does not promise to sign the Visitor out of the global
Google account. Invalid or expired sessions fail protected admission and are never forwarded as
Verified Identity Context.

After admission, the Shared Edge removes every visitor-supplied
`X-Comfforts-Verified-Identity` value and issues a new application-bound assertion. One signer
serves the qualification environment, but every protected attachment retains its distinct
`urn:comfforts:app-platform:audience:<application-id>` audience. The signer uses a software-protected
Cloud KMS `EC_SIGN_P256_SHA256` key in `us-west1`; the assertion envelope identifies `ES256` and a
specific key version. Private signing material is non-exportable and only public verification
material is published at the platform-reserved `/.well-known/jwks.json` path.

Assertions have a maximum lifetime of 60 seconds and verifiers allow at most 30 seconds of clock
skew. The edge issues a new assertion for each forwarded request or newly established streaming
connection. Admission changes take effect at the next request or connection as required by
ADR-003; an assertion does not promise mid-connection revocation.

The signing key rotates at least every 90 days. A new public key is published before it becomes the
active signer, exactly one version signs new assertions, and the preceding public key remains
available for a 24-hour verification overlap. Applications may cache the published key set for at
most 15 minutes and may refresh once when an unknown key identifier is observed; inability to
obtain valid, non-stale verification material fails closed.

The demo environment does not claim distributed replay prevention. Correlation identifiers remain
unique, assertions remain short-lived and audience-bound, and applications may add a bounded local
replay check, but no platform-wide replay store or guarantee exists until separately implemented
and qualified.

### Considered alternatives

- **Use provider-managed IAP as the platform admission system:** rejected for the initial platform
  because per-application policy and provider headers do not supply one registration-derived
  session, logout, and assertion boundary for all Admission Modes.
- **Trust each application's client-side Google login:** rejected because an application-controlled
  token flow cannot become the Shared Edge's Verified Identity Context and would fragment session
  and failure behavior.
- **Share an HMAC secret with every application:** rejected because verification would also grant
  assertion-signing capability and make rotation a multi-application secret-distribution event.
- **Use one signing key per application immediately:** rejected because application-specific
  audiences already prevent cross-application use while one environment signer reduces demo-scale
  key and rotation overhead.
- **Require distributed replay storage initially:** deferred because the short assertion boundary
  and non-production risk do not justify a new shared availability dependency without measured
  need.

### Consequences

- Applications migrated to the platform must trust only the platform assertion for platform-route
  identity; current IAP and `@react-oauth/google` behavior remains unchanged until each Application
  Adoption explicitly replaces or isolates it.
- A compromise of the environment signer affects every application in that environment, while
  application-specific audiences limit assertion reuse rather than signer blast radius.
- Firestore session availability and KMS/JWKS availability become protected-admission dependencies
  and must fail closed without blocking anonymous use of a public route.
- Cloud Run IAM caller authentication remains mandatory and separate from Visitor assertions.
- This decision selects the trust profile only. It creates no OAuth client, session database, key,
  secret, IAM binding, runtime, or Live evidence.

## ADR-007 · Separate state roots and use federated protected-main operations

Status: Accepted

Requirements: AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009, AP-QR-001, AP-QR-003,
AP-QR-004, AP-QR-005, AP-QR-006

### Context

Terraform state contains sensitive resource metadata and confers lifecycle authority over the
resources it tracks. Combining the Shared Edge and application runtimes in one root would violate
exclusive ownership even if those resources initially share a GCP project. Long-lived service
account keys or routine workstation applies would also weaken the binding between reviewed source,
the proposed plan, and the resulting provider change.

The dedicated GitHub repository identity is not yet known because extraction has not occurred.
Planning can select the authority model, but no Workload Identity Federation binding or live apply
may be enabled until the repository and workflow subjects are exact.

### Decision

Terraform uses a remote GCS backend with native state locking and object versioning. The state
layout has these independently initialized roots:

```text
infrastructure/terraform/bootstrap/
infrastructure/terraform/platform/
infrastructure/terraform/fixtures/<application-id>/
```

The bootstrap root owns only state-backend resources and their recovery controls. The platform root
owns only Shared Edge, session, signing, observability, and registration-derived platform
resources. Each Fixture Application has its own root for its Cloud Run runtime and other fixture
Application State. A future real application owns its backend in its own project and authority
chain; the platform never relocates that state into these roots.

The bootstrap and platform roots use a dedicated platform-state bucket with distinct object
prefixes because both are Platform State. Each Fixture Application uses a separate state bucket so
the platform and other fixtures can be denied object access at the bucket boundary. Bucket names
are environment configuration selected only after global-name availability is checked; they are
not embedded in reusable modules or contracts.

Every state bucket uses uniform bucket-level access, public-access prevention, object versioning,
and recovery history that retains a noncurrent version until it is at least 90 days old and at
least 20 newer generations exist. Terraform state, lock objects, saved plans, and recovery copies
are never committed or used as qualification evidence.

The bootstrap procedure is a one-time, explicitly approved owner operation from reviewed source.
It uses short-lived human credentials to create the backend resources, migrates the temporary
local bootstrap state into the new backend, verifies lineage and provider readback, and removes the
temporary copy only after recovery is proven. Bootstrap and backend destruction are not normal
platform lifecycle operations.

Cross-state exchange uses versioned, non-secret references reviewed through Application
Registrations and the State Ownership Manifest. No platform root uses `terraform_remote_state`,
GCS object access, or application credentials to inspect an application's backend. An exported
resource reference is data, not state access or management authority.

Normal cloud operations run in GitHub Actions using OIDC and GCP Workload Identity Federation.
There is no stored service-account key. After extraction, federation conditions must bind the
dedicated repository, exact protected branch, approved workflow, and protected GitHub environment.
The repository owner may review, approve, and trigger the workflow; one person may hold those roles
for this personal demo, but the source, environment, and workload permissions remain distinct.

Pull requests run `make check`, Terraform formatting and validation, and a reviewable read-only
plan for each affected root. A pull-request plan is advisory because the merge revision differs.
After merge, the protected-main workflow creates a new plan for the exact main commit, records its
source and plan digests, requires explicit environment approval, and applies only that plan. A
concurrency guard and backend lock permit at most one mutation for a state root at a time.

Plan, apply, rollback, import, state-recovery, and destroy are separate workflow authorities.
Planning identities may read provider and state metadata required to plan but cannot mutate cloud
resources. Routine apply identities are scoped to one state owner. Import, force-unlock, state
push, backend change, and destroy are break-glass operations requiring explicit owner approval,
exact targets, pre-action state backup, post-action readback, and retained evidence. A partial
provider failure stops for inspection; it does not automatically unlock, push state, destroy, or
roll back.

Local scripts may run deterministic checks, formatting, validation, read-only plans, and readback.
Routine workstation apply is prohibited. If GitHub Actions is unavailable during an owner-declared
emergency, the repository owner may use short-lived local GCP credentials for the smallest approved
operation, record the exact source and commands, read back the result, and reconcile it through a
reviewed commit. No emergency procedure permits a stored key or silent console change.

Provider-console changes are drift, never authority. The next plan must surface drift, and the
owner must either restore the reviewed configuration or adopt the difference through source review.

### Considered alternatives

- **Use one Terraform root for the platform and fixtures:** rejected because an apply or destroy
  could mutate resources with different owners and lifecycles.
- **Let the platform read application state outputs directly:** rejected because it leaks backend
  structure and access across ownership boundaries.
- **Use only local Terraform state:** rejected because workstation loss, concurrent changes, and
  weak recovery would make the reviewed configuration difficult to restore.
- **Store a GCP service-account key in GitHub:** rejected because long-lived credentials are not
  bound to a repository revision, workflow subject, or short lifetime.
- **Allow routine local applies:** rejected because they bypass protected-main approval, revision
  binding, concurrency controls, and retained workflow evidence.
- **Remove all emergency local authority:** rejected because a personal demo still needs a bounded
  recovery path when the normal control plane is unavailable.

### Consequences

- The first bootstrap requires an owner-controlled, carefully evidenced exception before federated
  CI can exist.
- Separate fixture buckets add a small amount of configuration in exchange for clear state-access
  and recovery boundaries.
- Pull-request plans inform review but cannot be reused after merge; the exact protected-main plan
  is the only apply input.
- The repository owner can approve and apply, but cannot bypass the reviewed-source, protected-main,
  short-lived-identity, exact-plan, and readback requirements during normal operation.
- This decision creates no backend bucket, state, workflow, identity, credential, plan, provider
  mutation, or Live evidence.

## ADR-008 · Activate immutable generations through one reviewed edge revision

Status: Accepted

Requirements: AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-004, AP-PR-005, AP-PR-007,
AP-PR-008, AP-PR-009, AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006

### Context

Application registrations change infrequently and have one operator, so the initial platform does
not need a registration API, mutable registration database, or continuously reconciled multi-writer
control plane. It does need a persistent and observable equivalent of the fixture harness's atomic
generation pointer. Catalogue, routes, admission, attachments, identity settings, and ownership
must never activate independently.

The initial qualification hostname is new. Its DNS and certificate sequence must be independently
reviewed without treating removal of that new record as rollback of a Registration Generation or
touching existing Finance Assistant records.

### Decision

Complete Registration Sets remain reviewed Git inputs. The deterministic compiler validates the
declared predecessor and produces one canonical generation digest before Terraform planning. A
content-addressed, immutable compiled configuration object is staged in a platform-owned GCS
configuration bucket under that digest. The object is restricted platform configuration: it may
contain the issuer-and-subject membership required by a restricted Admission Mode, but it contains
no secret, credential, signed assertion, request payload, or application data and is never a public
catalogue or evidence artifact.

Each candidate Cloud Run edge revision is immutable and binds all of these values:

- source commit and compiler version;
- Registration Generation number and digest;
- compiled configuration object name and GCS object generation;
- edge container image digest; and
- applicable identity, attachment-adapter, and platform-configuration versions.

The Cloud Run service's traffic assignment to one immutable edge revision is the current Live
Registration Generation pointer. There is no separate registration endpoint or database. The
load-balancer URL map remains unchanged by an application registration because catalogue and prefix
routing stay inside the selected edge revision.

Activation is one operator workflow with two explicit phases. The staging phase publishes the
immutable configuration, verifies the predecessor, plans the exact candidate revision, validates
every attachment and IAM dependency, and creates the candidate without assigning user traffic. The
activation phase requires owner approval and changes 100 percent of edge traffic to that one
revision. It never applies catalogue, route, admission, attachment, identity, or ownership fragments
separately.

The predecessor digest, protected-main concurrency guard, Terraform backend lock, and provider
revision precondition reject stale or concurrent activation even though the initial environment has
only one operator. A provider error or incomplete apply stops for inspection. The workflow does not
automatically retry a destructive action, unlock state, change DNS, roll back, or destroy either
application target.

Successful readback must agree across source, state, provider, and runtime. It proves at least:

- the protected-main commit, reviewed plan digest, compiler version, Registration Generation, and
  generation digest agree;
- the Cloud Run service sends 100 percent of traffic to the expected immutable edge revision and
  image digest;
- the edge reports the expected generation digest through an operator-authorized platform status
  operation;
- the root catalogue, registered prefixes, attachment targets, Admission Modes, assertion issuer,
  application audiences, and published key identifier match the generation;
- unknown, suspended, retired, and malformed paths remain closed;
- protected targets reject direct unauthenticated invocation and accept only the reviewed edge
  caller plus valid application-bound assertions; and
- the provider inventory agrees with the State Ownership Manifest without reading application
  Terraform state.

Readback records identifiers, digests, coarse outcomes, and limitations only. It never records an
assertion, session, restricted member set, request body, application data, credential, Terraform
state, or saved plan.

Rollback is an owner-confirmed whole-generation operation that returns 100 percent of edge traffic
to the retained preceding edge revision. It targets a reviewed generation digest and never rolls
back, imports, destroys, or rewrites Application State. The initial rollback-time objective is 15
minutes from owner approval to restored traffic assignment and mandatory readback. No automatic
rollback is authorized; an observed failure stops for inspection and an explicit owner decision.

The preceding compiled configuration, edge revision, and any replaced application attachment stay
available for at least 24 hours after successful activation. Cleanup after that window is a separate
owner-approved operation with current-generation and state-ownership checks. It is not automatic,
and retirement or suspension never triggers application-resource deletion.

Initial DNS and TLS enablement are separate operator actions. The load balancer, reserved address,
closed-default edge, and certificate configuration are read back before the new hostname record is
requested. The operator creates only the `apps-staging.comfforts.com` record with a 1,800-second TTL,
checks authoritative and recursive resolution with `dig`, waits for the Google-managed certificate
to become active, and then runs the Live readback. DNS propagation is observed rather than assumed;
the TTL is a cache lifetime, not a promise that every resolver updates within 30 minutes.

If initial hostname qualification fails, the owner may remove or restore only that new record after
inspection and must allow for cached answers through the TTL. This does not change the active
Registration Generation, does not touch `apps.comfforts.com`, and does not modify any Finance
Assistant record, certificate, load balancer, or state.

### Considered alternatives

- **Store a mutable current-generation row in a registration database:** rejected because the
  initial low-frequency, single-operator workflow does not justify another control-plane service or
  source of configuration authority.
- **Rewrite provider routes directly for each registration:** rejected because partial URL-map and
  runtime updates could diverge from the reviewed generation.
- **Fetch a mutable configuration object under a fixed name:** rejected because caches, concurrent
  writes, and ambiguous rollback would weaken digest and revision binding.
- **Automatically roll back on any failed check:** rejected because a partial provider failure may
  require inspection before another mutation is safe.
- **Delete replaced targets immediately:** rejected because whole-generation rollback would no
  longer restore service even if the edge revision were retained.
- **Manage the DNS zone or existing records as part of registration activation:** rejected because
  hostname lifecycle is separate from application registration and existing records are outside
  this qualification boundary.

### Consequences

- A registration change deploys a new edge revision even when the edge application code and image
  digest are unchanged.
- Immutable configuration objects and revisions consume modest storage during retention but make
  provenance and rollback explicit.
- The 15-minute rollback objective begins after owner approval; detection and decision time are
  recorded separately.
- A 24-hour retention window is a minimum recovery opportunity, not permission for automatic
  cleanup at its expiration.
- This decision creates no registration file, configuration bucket, object, edge revision, DNS
  record, certificate, deployment, mutation, or Live evidence.

## ADR-009 · Bound demo observability, evidence, and spend

Status: Accepted

Requirements: AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008, AP-QR-002,
AP-QR-004, AP-QR-005, AP-QR-006

### Context

The qualification environment is a low-traffic public demo with no production availability
commitment. Detailed visitor or application logging would create privacy exposure without improving
the generic platform evidence boundary. Unbounded Cloud Run scaling, retention, image history, or
diagnostic exports could also exceed the owner's small budget even when application traffic is low.

Budget notifications are not a hard spending cap, and Cloud Run instance limits can be exceeded
briefly during a deployment or traffic spike. The platform therefore needs layered controls and an
explicit owner response rather than claiming that one provider setting prevents all excess spend.

### Decision

Platform runtime logs use structured records in a dedicated Cloud Logging bucket in the
qualification project and `us-west1`. Log access is restricted to the App Platform Owner, retention
is seven days, and no sink exports logs outside the cloud project.

One edge event per completed request or streaming-connection boundary may record only:

- source revision and Registration Generation digest;
- immutable application identifier and normalized route identifier;
- coarse admission, routing, dependency, and response outcome;
- response status class, latency, and correlation identifier; and
- platform component and non-secret version identifiers needed for readback.

The platform does not log raw assertions, session cookies or identifiers, restricted member sets,
issuer-subject pairs, email addresses, request or response bodies, query strings, raw application
paths, application data, provider payloads, secrets, Terraform state, saved plans, or streaming
chunks. The edge does not intentionally retain source IP addresses, user-agent strings, or other
visitor metadata. Provider-mandated administrative audit metadata remains inside the project under
provider access controls and is not copied into platform logs or evidence.

Control-plane audit events include compilation rejection, reviewed plan creation, apply, generation
activation and rollback, DNS or TLS action, key rotation, IAM or state-backend change, denied
operator action, drift detection and reconciliation, break-glass use, incident start and closure,
and destructive cleanup. These events use digests and coarse outcomes rather than embedding the
affected state or secret material.

Live qualification evidence is a redacted, revision-scoped bundle stored in a dedicated private GCS
evidence bucket in the qualification project. It records source and plan digests, generation and
image digests, provider and runtime readback outcomes, exact evaluation commands, timestamps,
failures, limitations, and evidence-class labels. Evidence retention is 30 days and access is
limited to the App Platform Owner. Evidence is not exported outside the project. Screenshots,
authenticated browser state, raw provider responses, and unredacted logs are never authoritative
evidence. Git may retain only an approved secret-free evidence index or digest, not the bundle.

The App Platform Owner is the initial security, availability, privacy, and cost incident contact.
Incident handling stops new changes, records the affected revision and generation, preserves
permitted evidence, assesses whether a route suspension or owner-confirmed rollback is safe, and
records recovery and follow-up. It does not authorize automatic deletion, credential disclosure,
or silent provider-console repair. Automated security and availability alerts beyond the budget
notifications are deferred until post-qualification operating needs are known; a mandatory Live
gate failure is itself a failed qualification, not an alert substitute.

The qualification project has a monthly budget of USD 20 with owner notifications at 50, 80, and
100 percent of forecast or actual spend as configured by the provider. At 50 percent the owner
reviews attribution. At 80 percent new billable changes pause pending review. At 100 percent the
owner decides whether to continue, suspend nonessential registrations, or perform an explicitly
approved teardown. Billing is not disabled automatically, and no budget event destroys state,
evidence, DNS, keys, or application resources.

The initial Cloud Run limits are:

| Runtime | Minimum instances | Maximum instances | CPU | Memory | Concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shared Edge | 0 | 2 | 1 vCPU | 512 MiB | 20 |
| Each Fixture Application | 0 | 1 | 1 vCPU | 512 MiB | 10 |

Scale-to-zero and reasonable cold starts are accepted. SSE and WebSocket connections are supported
for at most 55 minutes per connection and consume concurrency while open. The platform does not
pre-warm an instance. A provider may briefly exceed the maximum during deployment or traffic
spikes, so these values are cost guards rather than absolute spend guarantees.

The initial environment has exactly one non-production Shared Edge, global load balancer, and
qualification hostname. It enables no CDN, WAF, HSM key, production replica, always-on instance,
Firestore backup, or Firestore point-in-time recovery. Firestore contains only minimal expiring
Platform Session data; access rejects the eight-hour expiry independently of asynchronous cleanup.
KMS retains only the active signing version and the preceding verification version required by the
approved overlap.

Artifact Registry retains the active, rollback, and current-candidate image for each service.
Cleanup policy is evaluated in dry-run mode first. Deleting an unreferenced image, old edge revision,
compiled generation, or replaced application target requires owner approval and the applicable
rollback-window checks; it is never inferred from a budget alert.

Terraform validation must reject an unapproved billable service, additional environment or load
balancer, nonzero Cloud Run minimum, absent maximum, larger initial CPU or memory allocation,
longer retention, backup or PITR enablement, CDN, WAF, HSM, or missing ownership labels. Billable
resources use at least `environment`, `managed_by`, `state_owner`, and, where applicable,
`application_id` labels.

The platform project pays for Shared Edge resources and the initial same-project qualification
fixtures. A future application-owned project pays for its runtime, data, networking, and provider
services unless an Application Adoption explicitly approves another allocation. Cross-project
references never give the platform access to application billing or Terraform state.

### Considered alternatives

- **Retain detailed request logs for troubleshooting:** rejected because identity, paths, payloads,
  and visitor metadata create unnecessary privacy and evidence risk for a demo.
- **Export logs to an external analytics service:** rejected because it expands access, retention,
  cost, and incident scope before a measured need exists.
- **Treat screenshots as Live evidence:** rejected because they are difficult to redact, bind to a
  source revision, reproduce, or validate mechanically.
- **Set minimum Cloud Run instances to avoid cold starts:** rejected because low traffic and
  reasonable cold starts are accepted while an always-on baseline would consume the small budget.
- **Automatically disable billing or destroy resources at USD 20:** rejected because a partial
  shutdown can lose recovery controls, leave DNS inconsistent, or destroy application-owned state.
- **Enable every provider security and availability service initially:** rejected because CDN, WAF,
  HSM, backups, and production redundancy are not required by the demo threat or availability
  commitment and need separate cost justification.

### Consequences

- Seven-day logs support short investigations but do not provide long-term visitor analytics.
- Evidence must be reviewed or promoted before its 30-day retention expires; expiration never turns
  a missing gate into a pass.
- Long-lived streams may hold both permitted edge instances and delay other requests at the selected
  concurrency, which is acceptable for initial low traffic and must be measured during Live gates.
- The USD 20 budget provides notification and response thresholds, not guaranteed maximum spend.
- This decision creates no log or evidence bucket, budget, alert, runtime limit, label, cleanup
  policy, incident automation, provider mutation, or Live evidence.
