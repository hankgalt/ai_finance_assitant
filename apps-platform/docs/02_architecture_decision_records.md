# App Platform architecture decision records

Version 0.1 | Status: accepted decisions; no platform capability is implemented

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
