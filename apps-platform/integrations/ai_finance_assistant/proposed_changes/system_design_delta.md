# Proposed Finance system-design delta

Status: **Integration Draft — inactive**

This file proposes a future change to `docs/03_system_design.md`; it does not modify the current
Finance deployment design.

## Proposed integration boundary

The future design should show App Platform as an external upstream system that owns the hostname,
root catalogue, TLS termination, HTTP redirect, URL maps, edge backend services/attachments, and
Admission Decision. Finance-owned frontend and backend workloads remain private attachments behind
the Shared Edge.

The versioned interface must carry:

- the Finance route prefix and frontend/backend attachment references from Finance to the platform;
- adopted catalogue metadata and Admission Mode from the Finance registration;
- minimal Verified Identity Context and the backend signed-assertion audience from the platform to
  Finance; and
- readiness and lifecycle states without granting either state owner write access to the other.

The migration design must register Finance as Restricted and owner-only. A later Finance-owned
access release may adopt Authenticated admission for any successfully authenticated Google identity
by changing the versioned registration and application policy, without transferring Feature
Entitlements to the platform and without repeating the edge-ownership migration.

FastAPI must continue to verify the signed identity assertion, derive its own immutable Application
Principal, and authorize every Finance resource and Feature Entitlement. Email remains metadata.
Direct workload access, unsigned identity, unknown routes, and cross-application identity reuse
remain closed.

## Design work still required

- versioned registration and attachment schemas;
- identity assertion and audience lifecycle;
- IAP/OAuth and Cloud Run invoker-binding ownership;
- root catalogue and unmatched-route behavior;
- health, logging, correlation, redaction, and audit boundaries;
- platform/app release ordering and compatibility windows; and
- state-transfer and rollback sequence diagrams.
