# Comfforts App Platform

Status: AP-M3 system design, Version 1 machine contracts, and deterministic offline validation
implemented; no platform runtime, Fixture Application, or cloud resource is implemented or
qualified.

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
`docs/README.md`. Product requirements, accepted architecture decisions, system design, threat
model, AP-M3 plan and evaluation strategy, and Version 1 contracts are authoritative within their
declared boundaries. The schemas and reference compiler provide Contract (`C`) evidence only; they
do not prove runtime or provider behavior.

AP-M3 repository behavior passes its deterministic gate at this revision. Delivery item 3 is not
complete until its pull request merges, and delivery item 4 has no approved plan or evaluation
authority yet. After the merge, use the
[deterministic-fixture planning handoff](prompts/starting_prompt.md) from updated `main`.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
