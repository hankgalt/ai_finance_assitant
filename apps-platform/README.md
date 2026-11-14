# Comfforts App Platform

Status: governance foundation only; no platform runtime or cloud resource is implemented.

Comfforts App Platform is a separately governed project temporarily colocated in the
AI Finance Assistant repository. It is intended to own the shared application catalogue and edge
for `apps.comfforts.com`, but its presence does not change the current Finance Assistant deployment,
requirements, or Terraform ownership.

The project will be implemented and qualified with deterministic fixture applications before any
Finance Assistant migration is proposed. Draft application integrations remain inactive until the
consuming application adopts them through its own requirements and release process.

## Local verification

From the parent repository:

```bash
make -C apps-platform check
```

From this directory:

```bash
make check
```

`check` is credential-free and non-mutating. It does not access GCP, DNS, IAP, provider accounts,
or the live Finance Assistant deployment.

## Project authority

Platform governance and reading order will be maintained in `docs/README.md`. Project-specific
agent instructions will live in `AGENTS.md`. Requirements, architecture decisions, system design,
implementation planning, and evaluation strategy are deliberately deferred to their next approved
documentation slice.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
