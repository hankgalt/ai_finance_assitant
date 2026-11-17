# Comfforts App Platform

Status: AP-M5 infrastructure planning authority implemented and deterministically validated;
AP-M4 remains Fixture-qualified. No networked platform service, Terraform configuration, cloud
resource, deployment, Live evidence, or Application Adoption is implemented or qualified.

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
model, AP-M3 through AP-M5 plan and evaluation authority, and Version 1 contracts are authoritative
within their declared boundaries. The contract layer supplies Contract (`C`) evidence, and the
in-process harness supplies Fixture (`F`) evidence only; AP-M5 supplies planning authority rather
than provider or deployed evidence.

AP-M3 through AP-M5 deterministic gates pass at this repository revision. Delivery item 5 is
complete only after this pull request merges. After the merge, use the
[provider-runtime handoff](prompts/starting_prompt.md) from updated `main` to propose AP-M6 and
resolve its remaining runtime decisions before implementation. The handoff authorizes no Terraform,
cloud, DNS, identity, deployment, or Live mutation.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
