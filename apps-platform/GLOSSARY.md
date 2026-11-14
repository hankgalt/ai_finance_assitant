# App Platform glossary

Status: governance vocabulary; product requirements may refine these definitions without changing
their ownership boundary.

## App Platform

The separately governed system intended to own the shared application catalogue and edge for a
configured hostname. The current governance foundation implements no runtime or cloud resource.

## Colocated Project

A standalone project whose canonical files temporarily live under another repository directory.
It has its own authority, tooling, tests, and extraction path and is not a module of the containing
application.

## Shared Edge

The hostname-level DNS, TLS, address, load-balancing, routing, and identity foundation used by
multiple Registered Applications. This term names a planned capability, not current ownership.

## Registered Application

An application accepted through a versioned Application Registration. Registration does not make
the platform authoritative for the application's data, providers, or capability entitlements.

## Application Registration

The planned versioned contract that binds a unique route prefix to application attachments,
admission policy, catalogue metadata, and lifecycle state.

## Admission Mode

The planned platform policy deciding whether a request may reach an application attachment, such as
public, any authenticated identity, an allow-list, or owner-only. Feature authorization remains an
application responsibility.

## Platform State

Terraform state that exclusively owns shared platform resources. It must never overlap with
Application State ownership.

## Application State

State owned by a Registered Application, including its runtime, data, provider configuration, and
application-specific authorization. Its exact future boundary is defined by approved contracts.

## Fixture Application

A deterministic, non-production application used to qualify routing, identity delivery, admission,
registration, and lifecycle behavior without depending on a real application migration.

## Integration Draft

A non-authoritative migration input prepared for another application. It becomes active only when
that application adopts it through its own documentation, contracts, tests, and release process.

## Qualification

Versioned evidence that implemented behavior passed its declared evaluation gate. The presence of
documentation, code, or a cloud resource alone is not qualification.
