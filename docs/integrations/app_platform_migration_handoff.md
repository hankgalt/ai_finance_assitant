# App Platform migration handoff

Status: **Proposed Finance migration input — inactive**

Reviewed: 2026-11-17

This document preserves the Finance-side discovery path and compatibility review for a possible
migration to Comfforts App Platform. It is not a product requirement, architecture decision,
machine contract, implementation plan, state-migration procedure, or release approval. Current
Finance Assistant authorities and the qualified Finance-owned edge remain in force until a later
Finance-owned Application Adoption pull request changes them.

## Reviewed sources

| Source | Reviewed revision |
| --- | --- |
| Finance Assistant authority baseline | `f5f7cef84a0d7e2850e496f8ce56f3afdb7944c6` |
| Canonical App Platform repository | [`22f32da94854bbc265d40c8125f56b4efbbe7558`](https://github.com/comfforts/apps-platform/tree/22f32da94854bbc265d40c8125f56b4efbbe7558) |
| Inactive Finance integration package | [Pinned package](https://github.com/comfforts/apps-platform/tree/22f32da94854bbc265d40c8125f56b4efbbe7558/integrations/ai_finance_assistant) |
| Draft's original Finance baseline | `9dedac71ad358deb5ef1c02e2f0fea6e21773a71` |

The pinned package contains the original edge-migration proposal and proposed Finance requirements,
ADR, system-design, implementation-plan, evaluation, and repository-layout deltas. Its content
remains an Integration Draft under App Platform authority. This handoff does not copy those deltas
into Finance authority or imply that their older baseline is compatible with either reviewed
repository revision.

## Finance migration packet

This review is the entry point for two additional Finance-owned, inactive assets:

- [Migration asset and ownership inventory](app_platform_migration_assets.md) records the exact
  Finance files, current Terraform roots, provisional staging registration, later edge-transfer
  candidates, and mandatory teardown-script safety boundary.
- [Future Codex starting prompt](app_platform_migration_starting_prompt.md) bounds a new migration
  chat to the approved Finance authorities and the staging-first sequence.

The three documents are planning inputs only. They do not replace the Finance requirements,
accepted ADRs, implementation plan, machine contracts, or release evidence.

## Current boundary

Finance Assistant currently owns and has qualified the `apps.comfforts.com` IAP edge, its Terraform
state and operator procedures, the `/finance_assistant` browser and API contract, two Cloud Run
workloads, signed-IAP verification, Application Principals, product data, providers, Feature
Entitlements, and historical evidence. PR-017, ADR-030, the private-edge contract, and their
revision-scoped evidence remain authoritative.

App Platform has accepted Version 1 Registration and Attachment contracts, deterministic Fixture
evidence, provider-runtime code tested with fakes and process-local loopback, and infrastructure
planning. At the reviewed revision it has no Terraform implementation, deployed Shared Edge, Live
evidence, cross-project qualification, Finance registration, or Application Adoption.

The proposed destination keeps Finance workloads, data, providers, Application Principals, Feature
Entitlements, and Application State under Finance ownership. App Platform would own the hostname
Shared Edge, root catalogue, Registration Generation, Platform Admission, Platform Sessions,
application-bound identity assertions, and registration-derived routing. That destination is a
proposal until both projects approve compatible revision-scoped authorities and evidence.

## Recommended two-stage adoption sequence

### Stage A — qualify Finance on the non-production Shared Edge

The smallest first adoption should register Finance at
`https://apps-staging.comfforts.com/finance_assistant` only after App Platform has qualified the
exact Live Shared Edge, `gcp-cloud-run-v1` adapter, identity profile, and cross-project attachment
path at a merged revision. The provisional registration uses application ID
`finance-assistant`, route prefix `/finance_assistant`, and separate frontend and backend Cloud Run
attachments in Finance project `730340912967`, region `us-west1`. The exact proposed fields and
current incompatibilities are recorded in the asset inventory.

This stage requires Finance-side identity, protected-frontend, workload-metadata, network, and
qualification changes, but it transfers no existing edge resource or Terraform state. It does not
change the `apps.comfforts.com` DNS record, certificate, IAP edge, OAuth client, Finance `edge`
state, or current rollback path. The qualified Finance edge remains available while the staging
route proves registration, routing, platform assertion verification, cross-project reachability,
product journeys, provider boundaries, and data continuity.

The first implementation slice after Finance adoption authority is approved must change and test
the `down` scripts; no live `down` script may run first. That slice introduces the exclusive
ownership manifest, makes every Finance teardown refuse platform-owned or mixed-owner state before
any mutation-capable command, and proves the refusal with credential-free tests.

After the candidate registration and identity path are qualified, an owner-approved Stage A
teardown rehearsal may suspend or retire that registration, destroy only Finance-owned candidate
workloads and disposable application state, and verify that
`apps-staging.comfforts.com/finance_assistant` is unavailable. The platform root catalogue,
Fixture Applications, Shared Edge, admission/session/signing resources, network, DNS, and Platform
State must remain available and unchanged. The existing `apps.comfforts.com` IAP deployment remains
outside this rehearsal.

### Stage B — separately transfer or replace the production edge

Only after Stage A is accepted may a later Finance and App Platform release decide whether the
existing `apps.comfforts.com` resources remain in the Finance project under Platform State or are
replaced in the platform project before DNS cutover. That release requires its own resource
inventory, exclusive state-owner manifest, protected state backups, exact mutation commands,
maintenance window, rollback procedure, teardown-script changes, and Live evidence. Stage A does
not prejudge or authorize that choice.

## Preserved migration invariants

Any future Finance adoption must preserve all of these boundaries:

1. Each cloud resource has exactly one active Terraform state owner at every phase.
2. The qualified Finance edge remains authoritative until an approved cutover reaches its
   acceptance gate.
3. `/finance_assistant` browser, API, SSE, and application-data behavior remains stable unless a
   separately reviewed Finance requirement changes it.
4. Platform Admission never grants a Finance role, Feature Entitlement, provider right, display
   right, cache right, retention right, or spending authority.
5. Finance independently verifies platform identity, derives an Application Principal, and checks
   every product resource and feature after Platform Admission.
6. Anonymous access, visitor-supplied identity, cross-application identity reuse, unknown routes,
   and direct protected-origin access fail closed.
7. Secret payloads, assertions, sessions, restricted-member sets, application data, Terraform
   state, and saved plans remain outside repositories and ordinary evidence.
8. Application runtime/data lifecycle remains separate from Shared Edge lifecycle.
9. Edge-ownership migration preserves restricted owner-only access; broader authenticated access is
   a later Finance release with separate provider-rights and entitlement evidence.
10. Historical Finance contracts and qualification evidence remain immutable historical evidence.

## Compatibility gap review

The original Integration Draft is useful ownership-transfer input, but it is not adoption-ready.
The labels below are review aids, not requirement or decision identifiers.

| Gap | Finding | Required closure before adoption |
| --- | --- | --- |
| G-01 · Stale baselines and traceability | The draft predates the reviewed Finance baseline and App Platform ADR-005 through ADR-009, AP-M6, and the accepted Version 1 contracts. Its platform constraint list stops at ADR-004. | Reconcile every proposed delta against exact current revisions and record the adopted requirement, ADR, contract, plan, evaluation, and threat identifiers. |
| G-02 · Platform qualification dependency | The draft treats Fixture qualification as a principal activation condition. The reviewed platform has no AP-M7 Terraform, AP-M8 deployment, AP-M9 Live evidence, or qualified cross-project attachment. | Require merged platform infrastructure authority, deployed Fixture qualification, Live qualification, and explicit cross-project evidence for the exact adapter and identity profile before Finance cutover implementation. |
| G-03 · Identity authority replacement | Finance accepts `X-Goog-IAP-JWT-Assertion` from issuer `https://cloud.google.com/iap`. App Platform rejected IAP as its admission system and instead issues an application-bound ES256 assertion in `X-Comfforts-Verified-Identity` after Google OIDC and a Platform Session. | Adopt one Finance platform-assertion verifier with exact issuer, audience, JWKS, lifetime, skew, rotation, failure, and header-replacement behavior. Retire or isolate IAP verification only through a reviewed compatibility and rollback sequence. |
| G-04 · Principal and retained-data continuity | Finance derives `principal_id` from issuer plus subject and requires email to admit and assign owner/viewer roles. The platform assertion uses a different issuer and intentionally contains no email. A direct switch would derive a different Principal and could orphan existing Principal-owned records. | Choose and test a Finance-owned identity-mapping or Principal-migration policy, pre-provision roles without trusting mutable email, preserve or deliberately migrate retained ownership, and define rollback behavior. |
| G-05 · Frontend assertion verification | App Platform requires every attachment behind authenticated or restricted admission to request verified identity and independently verify the assertion. Finance's backend verifies IAP today, while its static frontend relies on the edge and has no platform assertion verifier. | Decide whether to add a verified frontend gateway, change the application attachment topology, or approve another contract-compatible design. The current frontend cannot be registered as a protected attachment unchanged. |
| G-06 · Shared browser origin | Path-hosted catalogue applications share the `apps.comfforts.com` browser origin. A compromised application path could attempt same-origin Finance requests using the Visitor's Platform Session; `SameSite=Lax` does not isolate applications on the same origin. | Choose a separate-host boundary or qualify application-level same-origin request defenses, including CSRF/origin policy and browser-content isolation, across every Finance mutation and stream. |
| G-07 · Cloud Run reachability | Finance sets internal/load-balancer ingress and disables both default Cloud Run URLs. The current `gcp-cloud-run-v1` adapter resolves a provider-derived `run.app` target, obtains an edge-caller identity token, and requires an edge service-account Invoker grant. | Prove a supported cross-project network path, Shared VPC/service-project relationship, target URL posture, ingress mode, edge-caller IAM, and direct-origin denial. Update Finance workload configuration only after this topology is qualified. |
| G-08 · Exact Registration and Attachment mapping | No reviewed Finance registration names the application ID, catalogue projection, restricted Google issuer/subject, two attachment URNs, mounts, forwarding modes, application audience, labels, annotations, or lifecycle. | Compile and test a staged Version 1 registration. Preserve `/finance_assistant` for the frontend and the `/finance_assistant/api` to `/api` rewrite, and prove each attachment's owner, readiness, audience, and caller binding. |
| G-09 · Project and state transfer | Existing address, certificate, URL maps, backend services, endpoint groups, IAP policy, and state live in the Finance project and `edge` state. The platform qualification project and planned Platform State are separate, and project-bound resources may not be movable while retaining identity. | Choose identity-preserving management in place or explicit replacement/DNS cutover. Record exact resource IDs and state addresses, supported import/remove operations, backups, plan/readback gates, and the point at which Finance mutation authority is revoked. |
| G-10 · OAuth, session, and logout transition | The existing custom IAP OAuth client and secret do not implement the platform's authorization-code-with-PKCE flow, Firestore Platform Sessions, KMS signer, JWKS, eight-hour expiry, or platform-owned logout. | Approve the platform OAuth client/redirects, secret custody, session store, key lifecycle, cookie/logout behavior, and coexistence or retirement of the IAP client without copying secret payloads. |
| G-11 · Rollback across trust boundaries | Platform generation rollback retains its previous configuration and attachment for at least 24 hours, but returning to the Finance IAP edge also requires a compatible application identity mode, IAP audience, IAM path, state owner, and DNS/TLS posture. | Define pre-transfer, post-transfer, and post-identity-cutover rollback separately. Keep only the minimum dual-compatible application code/configuration needed for the reviewed window; never enable both edge state owners concurrently. |
| G-12 · Existing-host DNS and TLS cutover | Platform planning qualifies a new `apps-staging.comfforts.com` record and explicitly excludes the current Finance hostname. The draft does not resolve how an existing active hostname and certificate move between project-owned edges. | Approve the exact `apps.comfforts.com` address/certificate strategy, TTL, maintenance window, certificate readiness, DNS action, verification, failure stop, and reverse action without treating DNS as Registration rollback. |
| G-13 · Runtime and observability compatibility | Platform proxy limits, header replacement, cookies, five-minute non-streaming timeout, SSE limits, correlation header, streaming cancellation, and response filtering have only generic local evidence. Finance has real upload, REST, SSE, telemetry, and browser behavior. | Run contract tests and Live adoption journeys for request sizes, API rewrite, uploads, redirects, cookies, SSE replay/cancellation, trace correlation, errors, accessibility, and redaction at the exact adopted revisions. |
| G-14 · Independent application releases | The draft does not distinguish a Finance image rollout that preserves an attachment reference from a release that replaces a service or registration-derived fact. | Define the Finance release-to-registration matrix: ordinary compatible image revisions require no re-registration; changed service references, mounts, admission, catalogue data, or identity facts require a reviewed generation and rollback attachment. |
| G-15 · Finance authority identifiers | PR-017 and ADR-030 explicitly require IAP and current IAP evidence. The proposed delta says it does not change PR-017, which conflicts with replacing IAP and edge ownership. The draft also assigns no new Finance milestone or evaluation identifiers. | Amend or supersede the affected PR-017 and ADR-030 clauses through a new Finance-owned decision, add a new post-M11 migration milestone, and define numbered deterministic, Live, rollback, and non-regression gates. Do not rewrite completed M11 evidence. |
| G-16 · Teardown authority after ownership transfer | `private-edge-down.sh` currently delegates to `configure-private-edge.sh down`, which initializes Finance's `edge` state and can destroy the load balancer, forwarding rules, certificate, endpoint groups, backend services, IAP bindings, and global IP. `demo-runtime-down.sh` separately destroys Finance workloads and runtime state. Neither script understands a future Platform State owner or active platform registration. | Before any state handoff, make the private-edge down path fail closed before Terraform initialization whenever the ownership manifest is not `finance`; remove transferred resources from Finance configuration and state through the approved handoff; and require runtime teardown to prove the active Registration Generation no longer references the targets. Platform-owned resources may be destroyed only by the platform's separately approved workflow. |

## Required Finance authority work

A later owner-approved Finance adoption-planning pull request must update these authorities together:

- `docs/01_requirements_specification.md` for the adopted edge dependency, identity boundary,
  Principal continuity, release separation, and non-goals;
- `docs/02_architecture_decision_records.md` for the exact PR-017/ADR-030 supersession boundary and
  accepted identity, origin, project, state, and rollback trade-offs;
- `docs/03_system_design.md` for registration, attachments, assertion verification, Principal
  mapping, same-origin security, network reachability, and lifecycle flows;
- `docs/04_implementation_plan.md` for a new post-M11 planning, compatibility, migration, cutover,
  rollback, and retirement sequence;
- `docs/05_evaluation_strategy.md` for deterministic compatibility, cross-project, Live adoption,
  identity/data continuity, provider-rights, product-parity, and rollback evidence;
- `docs/repository_layout.md` for the eventual disposition of Finance-owned edge modules, scripts,
  contracts, and historical evidence; and
- machine contracts for the adopted registration input, attachment outputs, identity assertion,
  state ownership, and migration evidence.

The future implementation must also update the Finance `private-edge-down`,
`configure-private-edge`, and `demo-runtime-down` behavior in the same adoption sequence described
by the [asset inventory](app_platform_migration_assets.md). Documentation alone does not make the
current scripts safe after a state-owner change.

The first future implementation pull request after those authorities are accepted must implement
only the ownership manifest, Finance teardown scope/refusal behavior, and deterministic tests. The
separate Live rehearsal follows after merge and platform/candidate readiness; it must not be hidden
inside the script-change pull request.

Those changes must reference exact platform contract and evidence revisions. A link to this handoff
or to the Integration Draft is not Application Adoption.

## Owner decisions still required

Before approving the Finance adoption plan, the owner must select:

- whether existing edge resources remain managed in the Finance project or are replaced by
  platform-project resources;
- whether preserving the current global IP and certificate identifiers is mandatory;
- the Finance Principal continuity and role-provisioning policy for the IAP-to-platform identity
  transition;
- the protected frontend verification topology;
- the accepted same-origin browser risk control or separate-host alternative;
- the qualified cross-project Cloud Run reachability and Shared VPC design;
- the exact owner Google issuer/subject used by restricted Platform Admission;
- catalogue visibility, title, summary, application ID, attachment IDs, and forwarding modes;
- OAuth-client transition, Platform Session, logout, and rollback behavior;
- the maintenance window, rollback objective, and retained compatibility window; and
- the point at which Finance edge workflows lose mutation authority and later become historical.

The recommended answer for the first migration slice is to defer every production-edge ownership
decision: qualify the cross-project Finance attachments on `apps-staging.comfforts.com`, preserve
the complete Finance-owned IAP edge, and collect the evidence needed for the later choice.

## Acceptance boundary

This handoff is complete when the source package is discoverable from Finance documentation, its
reviewed baselines and compatibility gaps are explicit, and no reader can mistake it for adoption.
It authorizes no Finance requirement change, platform registration, code modification, Terraform
operation, state command, IAM or identity change, OAuth action, DNS change, deployment, cutover,
access expansion, or cleanup of the qualified Finance edge.
