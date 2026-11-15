# Comfforts App Platform

Status: AP-M4 deterministic in-process Fixture harness implemented and Fixture-qualified; no
networked platform service, cloud resource, Live evidence, or Application Adoption is implemented
or qualified.

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
model, AP-M3/AP-M4 plan and evaluation authority, and Version 1 contracts are authoritative within
their declared boundaries. The contract layer supplies Contract (`C`) evidence, and the in-process
harness supplies Fixture (`F`) evidence only; neither proves provider or deployed behavior.

AP-M4 repository behavior passes its deterministic gate at this revision. Delivery item 4 is
complete only after this pull request merges. After the merge, use the
[infrastructure-planning handoff](prompts/starting_prompt.md) from updated `main` to propose item 5
authority; it does not authorize infrastructure implementation or live mutation.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
