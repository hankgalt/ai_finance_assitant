# Finance Assistant edge migration contract draft

Status: **Integration Draft — inactive**

Finance source baseline: `9dedac71ad358deb5ef1c02e2f0fea6e21773a71`

Platform constraints: AP-PR-002, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-009;
AP-QR-001, AP-QR-002, AP-QR-006; ADR-001, ADR-002, ADR-003, ADR-004

This document proposes how ownership of the current Finance Assistant edge could move to App
Platform without transferring the Finance runtime, data, provider rights, Feature Entitlements, or
Application Principals. It is not a machine contract, executable runbook, state-migration command,
or authorization to mutate either deployment.

## Current Finance-owned boundary

At the recorded baseline, Finance Assistant owns and qualifies:

- the desired Squarespace `apps.comfforts.com` A record and operator procedure;
- the global IPv4 address, Google-managed hostname certificate, HTTP redirect, HTTPS proxy and
  forwarding rule, URL maps, serverless network endpoint groups, and frontend/backend backend
  services;
- IAP enablement and resource-level admission bindings on both backend services;
- IAP-service-agent Cloud Run invoker bindings and the generated backend-service audience consumed
  by FastAPI;
- the external OAuth client selection, regional Secret Manager container, numeric secret-version
  reference, and write-only Terraform flow;
- exact `/finance_assistant` frontend and `/finance_assistant/api` rewrite behavior;
- edge Terraform in `infrastructure/terraform/modules/private_edge/` and
  `infrastructure/terraform/environments/staging-edge/`, using the `edge` prefix in the Finance
  staging state bucket;
- private-edge operator scripts, GitHub environment variables, machine contracts, tests, and
  historical qualification evidence.

Finance Assistant separately owns its Cloud Run workloads, signed-IAP validation, Application
Principal mapping, product-resource isolation, application roles, provider rights, Feature
Entitlements, data services, and application lifecycle. Those remain Finance-owned after migration.

## Proposed target boundary

App Platform would become the sole owner of the configured hostname's Shared Edge and root
catalogue. Registration-derived platform configuration would attach the Finance-owned frontend and
backend workloads at `/finance_assistant`, apply the adopted Admission Mode, and export the verified
identity/audience information required by the Finance application contract.

The target Platform State is expected to own hostname-level and registration-derived edge resources,
including the global address, certificate, redirect, forwarding/proxy resources, shared URL maps,
catalogue route, application route entries, edge backend services, edge-only endpoint groups, and
IAP admission policy. Exact ownership of Cloud Run invoker bindings, OAuth client/secret metadata,
and cross-project attachment resources remains unresolved until platform system design prevents
overlapping state ownership.

Finance Application State would continue to own the frontend/backend services and every product,
data, provider, principal, entitlement, and runtime concern. It would consume versioned registration
outputs without gaining write access to Platform State.

## Resource-transfer matrix

| Boundary | Current owner | Proposed owner | Transfer constraint |
| --- | --- | --- | --- |
| `apps.comfforts.com` desired DNS record | Finance edge procedure | App Platform procedure | Preserve one reviewed record; registrar credentials remain human-held |
| Global IPv4 address | Finance `edge` state | Platform State | Prefer identity-preserving state handoff so DNS need not change |
| Managed hostname certificate | Finance `edge` state | Platform State | Preserve active hostname coverage or qualify replacement before cutover |
| HTTP redirect and HTTPS forwarding/proxy resources | Finance `edge` state | Platform State | Preserve HTTPS-only behavior throughout cutover |
| URL maps and unmatched-path behavior | Finance `edge` state | Platform State | Add the root catalogue and registration-derived routes; unmatched paths remain closed |
| Frontend/backend edge services and endpoint groups | Finance `edge` state | Platform State | Prefer preserving backend IDs so the signed-IAP audience does not change unexpectedly |
| IAP admission policy | Finance `edge` state | Platform State | Initial adopted policy may not broaden Finance admission or provider rights |
| IAP OAuth client and secret metadata | Finance shared/edge procedures | Unresolved platform boundary | Never copy or expose the secret payload; approve reuse, transfer, or rotation explicitly |
| Cloud Run invoker bindings | Finance edge state on app-owned services | Unresolved attachment boundary | One state owner; retain IAP-service-agent-only invocation and no direct origin |
| Finance Cloud Run services and images | Finance workload state | Finance Application State | Referenced by registration; never imported into Platform State |
| FastAPI IAP audience configuration | Finance workload state | Finance Application State | Consume a platform output; fail closed before a valid audience is adopted |
| Finance data, providers, and Feature Entitlements | Finance Application State | Finance Application State | No migration through this edge cutover |
| Historical contracts and qualification evidence | Finance repository | Finance repository | Retain as historical evidence; do not rewrite or relocate |

## Transfer invariants

1. Every live resource has exactly one active state owner at every cutover phase.
2. The current Finance edge remains authoritative until Finance approves Application Adoption and a
   revision-scoped cutover.
3. The platform may not broaden Finance admission, feature access, provider use, display rights,
   caching, retention, or spending rights.
4. The public URL and `/finance_assistant` browser/API contracts remain stable unless Finance adopts
   a separate interface change.
5. Anonymous access, spoofed identity, unmatched routes, cross-application routing, and direct Cloud
   Run origin access remain denied.
6. Secret payloads never enter a repository, plan, state, ordinary Terraform variable, workflow,
   evidence record, or transfer log.
7. Finance runtime/data teardown and platform edge teardown remain separate operations.
8. A state handoff must not destroy or recreate an identity-bearing resource unless the reviewed
   plan declares the resulting audience, DNS, TLS, downtime, and rollback effects.

## Recorded access-model sequencing intent

The edge-ownership migration must preserve Finance Assistant's current Restricted, owner-only
Admission Mode. The ownership transfer and access-model expansion are separate releases so an
admission defect cannot be hidden inside a state and routing cutover.

After the ownership migration is accepted and stable, the recorded owner intent is a separate
Finance-owned change targeting Authenticated admission for any successfully authenticated Google
identity supported by the adopted identity boundary. That follow-on change must preserve immutable
Application Principals, per-Principal data isolation, and application-owned Feature Entitlements.
An admitted person without a restricted entitlement should be able to use otherwise available
Finance functionality while being denied the restricted feature.

In particular, the current Massive Stocks Basic personal-use right does not permit market-data
display to other users. Platform admission cannot broaden that right: non-owner or otherwise
unentitled users remain denied Massive-backed market data unless Finance separately adopts a
provider plan and entitlement policy that permits it. OpenAI, Tavily, and every other provider remain
subject to their then-current Finance-owned rights, limits, and spending decisions.

This section preserves owner intent for later Finance adoption. It does not change the current
owner-only deployment or authorize the future access expansion.

## Preconditions for an executable cutover

- Platform system design and versioned Application Registration/attachment contracts are accepted.
- Fixture qualification covers route isolation, the selected Finance Admission Mode, Verified
  Identity Context, spoof rejection, direct-origin denial, rollback, and state-owner exclusivity.
- Finance adopts the proposed authority deltas and reconfirms its audience, admission, provider, and
  feature-entitlement posture.
- Both state backends are protected, independently addressable, drift-free, and backed up outside
  Git according to an approved operator procedure.
- A read-only inventory maps each live cloud resource identifier to its current and target state
  address without recording secret payloads.
- Saved plans demonstrate no unintended replacement of the global address, certificate, backend
  services, Cloud Run services, or Secret Manager payloads.
- The owner approves the maintenance window, DNS behavior, expected authentication interruption,
  rollback gate, and exact destructive/state commands.

## Proposed cutover phases

1. **Freeze and observe:** pause edge mutation; capture drift-free plans, resource identifiers,
   current audiences, IAM readback, DNS/TLS status, and qualified baseline evidence.
2. **Stage registration:** validate an inactive Finance Application Registration against the
   qualified platform without changing public routing or admission.
3. **Approve ownership manifest:** review the exact source and destination state addresses,
   non-transferable resources, secret treatment, and rollback owner.
4. **Transfer state ownership:** execute the future approved state procedure so each resource leaves
   Finance state before Platform State assumes it. No resource remains managed by both states.
5. **Reconcile the Shared Edge:** apply only the reviewed platform plan, preserving resource identity
   where promised and keeping Finance workloads private.
6. **Propagate application inputs:** update Finance-owned configuration only for adopted platform
   outputs such as the signed-IAP audience, then verify immutable Application Principal behavior.
7. **Qualify before finalization:** prove root catalogue navigation, exact Finance routes, TLS,
   selected admission, signed identity, no direct origin, unmatched-path denial, product journeys,
   provider boundaries, and state drift.
8. **Retire active Finance edge automation:** only after acceptance, remove or disable obsolete
   Finance edge mutation paths while retaining historical contracts and evidence.

These phases describe required outcomes, not commands. The future runbook must use provider-supported
state operations and show every plan before mutation.

## Rollback boundary

- Before state ownership transfer, rollback means discarding the inactive registration and leaving
  the Finance edge unchanged.
- After transfer but before platform mutation, an approved reverse ownership handoff may return the
  exact resources to Finance state.
- After platform mutation, rollback is owned by Platform State using the last reviewed working
  platform configuration. Finance state must not resume management concurrently.
- Reversing Application Adoption requires a separate reviewed state handoff and Finance release; it
  is not achieved by running an old Finance edge script.
- A rollback may not restore broader admission, an invalid IAP audience, public workload origins, or
  an exposed secret.

## Adoption evidence

The future Finance release must record, without secret or authenticated payloads:

- source and target revisions plus the adopted registration version;
- before/after state-owner manifests and drift-free plans;
- preserved or intentionally changed cloud resource identifiers;
- DNS, certificate, routing, IAP, audience, IAM, and direct-origin readback;
- owner and approved negative admission journeys;
- Finance Principal-isolation and critical feature-parity results;
- provider-rights and Feature Entitlement non-regression;
- rollback rehearsal result and any accepted limitation; and
- retained paths for pre-migration Finance historical evidence.

## Unresolved owner and design decisions

- whether the first Platform State and edge resources remain in `comfforts-369117` or use a separate
  GCP project;
- whether the current global address, certificate, backend services, and generated IAP audience are
  imported intact or replaced during an approved maintenance window;
- whether the current OAuth brand/client is transferred, shared, or replaced, and which project owns
  its Secret Manager metadata;
- whether platform or application state owns the IAP-service-agent invoker binding on an
  application-owned Cloud Run service;
- how versioned attachment references cross project/repository boundaries without reading another
  project's Terraform state directly;
- the root catalogue runtime, default unmatched-route service, logging boundary, and lifecycle;
- the post-migration Google identity-provider configuration, abuse/cost controls, and release gates
  for the separately adopted Authenticated admission expansion;
- which provider-backed features may be used by newly admitted identities under then-current plans,
  rights, spending limits, and application Feature Entitlements; and
- the exact state-transfer, rollback, WIF, GitHub environment, and evidence procedures.
