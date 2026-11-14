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
