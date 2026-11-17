# App Platform glossary

Status: platform requirements and decision vocabulary; no runtime behavior is implied.

## App Platform

The separately governed system intended to own the shared application catalogue and edge for a
configured hostname. The current governance foundation implements no runtime or cloud resource.

## Colocated Project

A standalone project whose canonical files temporarily live under another repository directory.
It has its own authority, tooling, tests, and extraction path and is not a module of the containing
application.

## Shared Edge

The hostname-level DNS, TLS, address, load-balancing, routing, and identity foundation used by
multiple Registered Applications. It is an accepted platform ownership boundary, not a claim that
any resource is implemented.

## Registered Application

An application accepted through a versioned Application Registration. Registration does not make
the platform authoritative for the application's data, providers, or capability entitlements.

## Application Registration

The versioned declaration that binds a unique route prefix to application attachments, admission
policy, catalogue metadata, and lifecycle state.

## Registration Set

The complete versioned collection of current Application Registrations, including retained retired
tombstones, proposed and reviewed as one atomic configuration input.

## Registration Generation

An immutable, numbered revision derived from one valid Registration Set and linked to the preceding
reviewed generation by digest.

## Compiled Shared Edge Configuration

The deterministic catalogue, routing, admission, and attachment configuration derived from one
valid Registration Generation. It is future provider-adapter input, not proof of deployment.

## Last Reviewed Working Configuration

The most recent whole Registration Generation accepted for platform operation and eligible for
restoration when a later generation fails. It does not include or roll back Application State.

## Application Attachment

A versioned, non-secret reference that binds an application subpath to an application-owned runtime
through an allow-listed platform adapter. Referencing the runtime does not transfer its ownership.

## Catalogue Visibility

The explicit policy deciding whether an active Registered Application appears in the root
catalogue. It is independent of Admission Mode and does not grant access.

## Admission Mode

The platform policy deciding whether a request may reach an application attachment, such as public,
any authenticated identity, an allow-list, or owner-only. Feature authorization remains an
application responsibility.

## Admission Decision

The platform result that determines whether one request may reach a Registered Application. It does
not authorize any feature inside that application.

## Verified Identity Context

Minimal issuer-and-subject identity information validated by the platform and supplied to a
Registered Application. It is an input to application identity, not a shared user profile.

## Platform Session

A platform-owned, time-bounded browser authentication context established from verified identity.
It is neither an Application Principal nor a Feature Entitlement.

## Application Principal

An immutable, application-scoped identity derived by a Registered Application from Verified
Identity Context. It is owned by that application and is not a platform-wide user identifier.

## Feature Entitlement

An application-owned permission to use a specific product capability or restricted data source.
Application admission never implies a Feature Entitlement.

## Platform State

Terraform state that exclusively owns shared platform resources. It must never overlap with
Application State ownership.

## Application State

State owned by a Registered Application, including its runtime, data, provider configuration, and
application-specific authorization. Its exact future boundary is defined by approved contracts.

## State Ownership Manifest

A revision-scoped declaration that assigns each managed resource reference to exactly one Platform
State or named Application State owner. References between states do not transfer management
authority.

## Fixture Application

A deterministic, non-production Registered Application used to qualify platform behavior without a
real application migration. Its runtime and state remain application-owned test assets, not Platform
State.

## Integration Draft

A non-authoritative migration input prepared for another application. It becomes active only when
that application adopts it through its own documentation, contracts, tests, and release process.

## Application Adoption

The consuming Application Owner's explicit acceptance of an Integration Draft through that
application's own authorities, implementation, migration, evidence, and release process.

## Qualification

Versioned evidence that implemented behavior passed its declared evaluation gate. The presence of
documentation, code, or a cloud resource alone is not qualification.
