# Comfforts App Platform

Status: AP-M6 implementation in progress; immutable generation loading, catalogue, routing,
Platform Sessions, admission, identity assertions, and application verification are implemented
locally, while attachment-provider and proxy behavior remain unavailable. AP-M4 remains
Fixture-qualified and AP-M5 remains planning-validated.
No Terraform configuration, cloud resource, deployment, Live evidence, or Application Adoption is
implemented or qualified.

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
model, AP-M3 through AP-M6 plan and evaluation authority, and Version 1 contracts are authoritative
within their declared boundaries. The contract layer supplies Contract (`C`) evidence, and the
in-process harness supplies Fixture (`F`) evidence only; AP-M5 supplies planning authority rather
than provider or deployed evidence.

AP-M3 through AP-M5 are merged and pass their deterministic gates. AP-M6-W1 is accepted, and
AP-M6-W2 supplies the locked dependency environment and closed-default ASGI foundation. AP-M6-W3
adds bounded compiled-generation parsing, exact object/content/generation binding, and an injected
Cloud Storage source adapter. It performs no provider call during construction or verification and
cannot discover, compile, activate, or mutate a generation. AP-M6-W4 renders the compiled catalogue
and performs canonical, lifecycle-aware route and mount selection. Its deterministic handoff
remains closed with `503`; it resolves no target and forwards no application request or response.
AP-M6-W5 adds Google OIDC authorization-code-with-PKCE behavior, opaque host-only eight-hour
Platform Sessions, Firestore and in-memory session adapters, optional public identity, exact
issuer-and-subject restricted admission, and platform-owned logout. Deterministic tests replace
provider and Firestore I/O; no OAuth credential or provider operation is required. Later work
packages own attachment-provider, proxy, and operational behavior. No AP-M6 package authorizes
Terraform, cloud, DNS, identity configuration, deployment, or Live mutation.

AP-M6-W6 replaces admitted identity at the route handoff with a minimized, application-audience-
bound ES256 assertion. It adds deterministic and Cloud KMS signing adapters, public-only JWKS with
current/overlap keys, and an independent application verifier with bounded caching and fail-closed
refresh behavior. Fixed synthetic keys and provider fakes exercise the adapters locally; no KMS
key, credential, external request, or provider resource is used.

All canonical platform files remain under `apps-platform/` so this directory can later be extracted
as the root of a dedicated repository while preserving its Git history.
