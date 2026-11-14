# Comfforts App Platform

Status: product requirements and accepted architecture decisions defined; no platform runtime or
cloud resource is implemented.

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

Read `AGENTS.md` before changing this project and follow the authority and reading order in
`docs/README.md`. Product requirements and accepted architecture decisions are now authoritative.
System design, implementation planning, and evaluation strategy remain deferred to their approved
documentation slices.

Use the [system-design/contracts handoff](prompts/starting_prompt.md) to begin the next chat without
copying specifications or relying on this conversation's history.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
