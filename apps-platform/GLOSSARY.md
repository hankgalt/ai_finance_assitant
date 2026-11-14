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
