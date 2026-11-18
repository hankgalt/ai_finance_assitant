# App Platform migration asset and ownership inventory

Status: **Proposed Finance migration input — inactive**

Reviewed: 2026-11-17

This Finance-owned inventory makes the proposed App Platform migration discoverable and safe to
plan from a new Codex chat. It is not an adopted registration, machine contract, migration runbook,
state command, or authorization to change code or live resources. Read the
[migration handoff](app_platform_migration_handoff.md) first.

## Current revisions and prerequisites

- Finance authority baseline: `f5f7cef84a0d7e2850e496f8ce56f3afdb7944c6`.
- Reviewed App Platform baseline: `22f32da94854bbc265d40c8125f56b4efbbe7558`.
- Finance project: `comfforts-369117` (`730340912967`), region `us-west1`.
- App Platform qualification project: `comfforts-platform-non-prod` (`455651441682`), region
  `us-west1`.
- Initial qualification hostname: `apps-staging.comfforts.com`.
- Existing qualified Finance hostname: `apps.comfforts.com`.

The reviewed platform revision has no deployed Shared Edge, platform Terraform, Live evidence, or
qualified cross-project attachment. Finance adoption work must pin a later merged platform
revision and verify its accepted contracts and evidence before implementation. AP-M7, AP-M8, and
AP-M9 names from the reviewed plan are prerequisites, not claims that those milestones now exist or
have passed.

## Finance-owned source assets

| Concern | Current Finance assets | Required adoption disposition |
| --- | --- | --- |
| Product authority | `docs/01_requirements_specification.md`, `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`, `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md` | Add a post-M11 Finance requirement, accepted decision, milestone, numbered evaluation gates, and exact platform revision. Amend or supersede only the affected PR-017/ADR-030 clauses; retain completed M11 evidence. |
| App identity | `backend/src/ai_finance_assistant/identity/`, `contracts/deployment/application-access.v1.json` | Add a platform-assertion mode with exact issuer, audience, JWKS, expiry, skew, rotation, and failure behavior. Preserve or deliberately migrate Application Principal ownership without using email as identity. Keep IAP compatibility only for the approved rollback window. |
| Frontend boundary | `infrastructure/container/frontend/`, frontend browser/API/SSE code | Add a contract-compatible verified-identity gateway or another approved protected-attachment topology. The current static Nginx frontend does not verify a platform assertion. |
| Application workloads | `infrastructure/terraform/modules/application_workloads/`, `infrastructure/terraform/environments/staging-workloads/` | Keep Cloud Run services, images, data, service accounts, secrets, runtime IAM, and Application State under Finance ownership. Add the exact platform ownership labels, identity-audience annotation, caller grant, reachability, and origin-denial controls approved for the cross-project adapter. |
| Current Finance edge | `infrastructure/terraform/modules/private_edge/`, `infrastructure/terraform/environments/staging-edge/` | Keep unchanged during staging qualification. In a later production transfer, remove or archive active Finance management only after one exclusive target owner has imported or replaced every approved resource. |
| Operator lifecycle | `private-edge-up.sh`, `private-edge-down.sh`, `configure-private-edge.sh`, `demo-runtime-up.sh`, `demo-runtime-down.sh`, `bootstrap-staging.sh`, and related Make targets | Add the teardown safety boundary below before an ownership handoff. Application-runtime teardown remains Finance-owned but must coordinate with active registration. Platform-resource teardown becomes platform-owned. |
| Machine contracts | `contracts/deployment/private-edge.v1.json`, `infrastructure-policy.v1.json`, `private-demo-qualification.v1.json` | Retain these as historical IAP/M11 truth. Add separate versioned Finance adoption, state-ownership, and evidence contracts; do not rewrite historical qualification as platform evidence. |
| Tests and evidence | `backend/tests/test_private_edge.py`, `test_staging_infrastructure.py`, identity/API tests, frontend deployment journeys, `backend/artifacts/release/deployment/` | Add deterministic assertion, Principal continuity, registration, ownership, and teardown-refusal tests plus revision-scoped staging and later cutover evidence. Never store assertions, tokens, state, plans, member sets, or application data. |
| Delivery authority | `.github/workflows/terraform.yml`, protected Finance environments and WIF | Keep Finance plans/applies scoped to Finance-owned resources. Platform plans/applies run from the platform repository. Cross-project IAM grants need one declared owner and must not give either root access to the other's state. |

## Proposed Stage A registration

This is a compatibility target for planning, not an adopted Registration Set. The future Finance
authority and exact current platform schemas control the final values.

| Field | Provisional value | Status |
| --- | --- | --- |
| Host | `apps-staging.comfforts.com` | Owner-selected non-production qualification host |
| Application ID | `finance-assistant` | Recommended |
| Route prefix | `/finance_assistant` | Required to preserve the product browser contract |
| Lifecycle | `staged`, then `active` only after all gates pass | Required |
| Admission | `restricted` | Preserves current owner-only posture; exact Google issuer and immutable subject remain required |
| Catalogue | Title `Finance Assistant`; visibility and final summary | Owner decision |
| Assertion audience | `urn:comfforts:app-platform:audience:finance-assistant` | Recommended; must be accepted by Finance authority |
| Frontend attachment | ID `web`; `gcp-cloud-run-v1`; mount `/`; forwarding `preserve`; identity `verified`; recommended candidate reference `urn:comfforts:app-platform:gcp:cloud-run:730340912967:us-west1:aifa-platform-staging-frontend` | Blocked until the service and a protected frontend verifier/gateway exist |
| Backend attachment | ID `api`; `gcp-cloud-run-v1`; mount `/api`; forwarding `strip_application_prefix`; identity `verified`; recommended candidate reference `urn:comfforts:app-platform:gcp:cloud-run:730340912967:us-west1:aifa-platform-staging-backend` | Blocked until the service, platform assertion, and cross-project reachability are qualified |

The safer Stage A default is to add these separately named, Finance-owned, zero-minimum candidate
services rather than alter `aifa-staging-frontend` and `aifa-staging-backend`, which remain the
targets of the qualified IAP edge. The candidate backend may use the existing Finance-managed data
services only after Principal continuity, authorization, concurrency, retention, and rollback are
qualified. Reusing the existing Cloud Run services instead is an owner decision and would require
an explicit dual-edge trust design that binds each accepted assertion type to its verified caller,
rejects ambiguous or visitor-supplied identity, and proves neither edge can impersonate the other.

The current services use internal/load-balancer ingress, disabled default Cloud Run URLs, and
IAP-specific configuration; those facts are compatibility inputs for the candidate topology, not
proof it works. Platform activation additionally expects `environment`, `managed_by`,
`state_owner=application`, and `application_id=finance-assistant` labels, the exact assertion
audience in `comfforts.com/identity-audience`, a provider-derived ready target, and an unconditional
`roles/run.invoker` grant to the exact platform edge caller. The current Finance labels use
`managed-by`, not the platform's recorded `managed_by` key. Those changes do not transfer any Cloud
Run service into Platform State.

Stage A must leave all of the following untouched: the `apps.comfforts.com` DNS record and managed
certificate; the Finance load balancer, IAP and OAuth configuration; Finance's `edge` state; the
current global IP; and the existing Finance rollback path. A platform staging failure therefore
does not require state transfer or production DNS rollback.

## Current Terraform state boundaries

| State prefix | Current owner | Adoption rule |
| --- | --- | --- |
| `bootstrap` | Finance | Remains Finance; never read by Platform State |
| `shared` | Finance | Remains Finance unless a later asset-specific decision says otherwise; current registry, WIF, budget, and IAP secret metadata are not implicitly platform assets |
| `foundation` | Finance | Remains Finance Application State for database, jobs, identities, secrets, and current application networking |
| `workloads` | Finance | Remains Finance Application State for frontend/backend Cloud Run services |
| `edge` | Finance | Remains Finance throughout Stage A; later transfer or replacement requires an exclusive state-owner manifest |
| Platform State | App Platform | Owns the staging Shared Edge, catalogue, registration-derived routes/connectors, platform identity/session/signing resources, and platform-owned Shared VPC resources at its accepted revision |

No platform root may read Finance Terraform state, and no Finance root may read Platform State.
Exchange only versioned, non-secret resource references and verified provider readback.

## Meaning of platform ownership

Application Registration supplies a reference; it does not transfer any ownership. Four distinct
authorities must not be conflated:

- **GCP project custody:** an existing resource stays in `comfforts-369117`; Terraform import cannot
  move it into `comfforts-platform-non-prod`.
- **Terraform state ownership:** Platform State can manage a resource in the Finance project only
  after Finance state releases it, Platform State imports it, and the platform provider identity
  receives narrowly scoped authority in that project.
- **Operational ownership:** after acceptance, only the platform repository and its approved
  workflow may plan, change, roll back, or destroy a platform-owned resource.
- **Application ownership:** Finance continues to own its Cloud Run services, data, identities,
  provider rights, Feature Entitlements, and Application State even when the platform references
  them as attachments.

Therefore App Platform can establish Terraform and operational ownership over approved existing
edge assets, but not merely through registration and not by changing their GCP project. Whether the
accepted platform topology is allowed to manage production Shared Edge assets in the Finance
project remains an owner and platform-authority decision.

## Later production edge ownership candidates

Finance's current `edge` state manages the following resource classes under
`module.private_edge`: the global IPv4 address; managed certificate; HTTP and HTTPS forwarding
rules, target proxies, and URL maps; frontend/backend serverless endpoint groups and backend
services; IAP access bindings; IAP service identity; and IAP-service-agent Cloud Run invoker
bindings. The current Finance OAuth secret metadata is in shared Finance state, while its payload is
outside Terraform state.

The configured Terraform addresses to inventory against live readback are:

```text
module.private_edge.google_project_service_identity.iap
module.private_edge.google_compute_region_network_endpoint_group.serverless["backend"]
module.private_edge.google_compute_region_network_endpoint_group.serverless["frontend"]
module.private_edge.google_cloud_run_v2_service_iam_member.iap_invoker["backend"]
module.private_edge.google_cloud_run_v2_service_iam_member.iap_invoker["frontend"]
module.private_edge.google_compute_backend_service.application["backend"]
module.private_edge.google_compute_backend_service.application["frontend"]
module.private_edge.google_iap_web_backend_service_iam_member.application_access[<instance-key>]
module.private_edge.google_compute_global_address.application
module.private_edge.google_compute_managed_ssl_certificate.application
module.private_edge.google_compute_url_map.https
module.private_edge.google_compute_target_https_proxy.application
module.private_edge.google_compute_global_forwarding_rule.https
module.private_edge.google_compute_url_map.http_redirect
module.private_edge.google_compute_target_http_proxy.redirect
module.private_edge.google_compute_global_forwarding_rule.http
```

The future read-only inventory must expand every `application_access` instance key and bind each
address to its provider resource identifier. It must obtain that evidence from protected state and
provider readback without copying state or secret-bearing values into the repository.

App Platform cannot claim those resources merely because a Registration exists. A later owner
decision must choose one of two models:

1. **Manage in place.** Resources stay in project `comfforts-369117`. The approved platform
   Terraform provider and operator identity receive narrowly scoped authority in that project;
   each resource is backed up and released from Finance `edge` state, then imported into Platform
   State with a no-create/no-update/no-delete reconciliation plan. Terraform state operations do
   not move a GCP resource between projects.
2. **Replace and cut over.** Platform creates replacement resources in its project, qualifies TLS
   and routing, then the owner changes DNS during an approved window. Existing Finance edge
   resources remain the rollback target until the retention gate permits their separate cleanup.

Both models prohibit dual state ownership. Exact commands, imports, IAM grants, address/certificate
feasibility, and rollback differ and remain owner decisions. No command sequence is approved by
this inventory.

## Mandatory teardown-script safety boundary

The current scripts are safe only for the current Finance-owned topology. Today,
`private-edge-down.sh` invokes `configure-private-edge.sh down`, which can destroy every resource in
Finance's `edge` state after DNS removal and confirmation. `demo-runtime-down.sh` invokes
`bootstrap-staging.sh down`, which destroys Finance workloads and disposable runtime state but does
not destroy the separate edge state. `live-providers-staging-down.sh` changes only Finance provider
mode and disposable provider-secret resources.

Before any production edge resource leaves Finance ownership, the adoption implementation must:

1. Add a versioned, non-secret ownership manifest whose generation and digest identify every
   transferred, retained, and replaced resource and its sole state owner.
2. Change `private-edge-down.sh` and `configure-private-edge.sh down` to fail closed **before any
   Terraform initialization, plan, state, DNS, audience, IAM, or apply action** unless the manifest
   declares the complete target set Finance-owned.
3. Remove transferred resource blocks and state addresses from the active Finance edge root only
   through the separately approved state-handoff procedure. A destroy plan is not a state-transfer
   procedure.
4. Retire or replace the `private-edge-down` Make target after transfer with a non-mutating status
   message directing operators to the platform-owned rollback/destroy workflow. Finance must not
   retain a second mutation path.
5. Change `demo-runtime-down.sh`/`bootstrap-staging.sh down` to require readback that no active
   Registration Generation references the Finance attachments before deleting those app-owned
   workloads. It must never initialize, plan, import, remove, or apply Platform State or detach a
   platform-owned Shared VPC relationship.
6. Keep provider rollback application-owned: `live-providers-staging-down.sh` may restore Finance
   provider configuration and delete only Finance-owned provider secrets; it may not mutate
   Platform Admission, sessions, routes, identity keys, network, DNS, or edge resources.
7. Add credential-free tests that substitute Terraform/GCP commands and prove an ownership mismatch
   exits before the first mutation-capable command. Also prove runtime teardown refuses while an
   active generation references either attachment.
8. Preserve the old Finance edge state backup and configuration as access-controlled rollback
   evidence. Do not re-enable its mutation scripts while Platform State owns the resources.

Changing shell logic is necessary but insufficient. A Finance state root containing even one
platform-owned address is a mixed-owner root and must make teardown fail. The migration must either
move those addresses to Platform State through the approved exclusive handoff or replace the
resources under Platform State before Finance teardown is enabled. A filtered or targeted destroy
against mixed-owner state is prohibited because dependency changes, refresh, or later drift could
still mutate the wrong owner's resource.

After transfer, only the platform repository's separately approved operator workflow may destroy
platform-owned assets. Finance `down` scripts may still destroy Finance-owned application runtime
and data after the registration lifecycle gate, but never platform edge, catalogue, registration,
identity, signing, Shared VPC, DNS, or state assets.

## Required first migration implementation slice

After a new Finance requirement, accepted ADR, milestone, and evaluation gate authorize adoption,
the first implementation pull request must change and test the `down` scripts before any of them is
run live:

1. Add the versioned Finance-consumed ownership manifest and validate its generation, digest,
   environment, resource identities, and exclusive owners without reading Platform State.
2. Make `private-edge-down.sh`, `configure-private-edge.sh down`, `demo-runtime-down.sh`, and
   `bootstrap-staging.sh down` refuse missing, stale, invalid, mixed-owner, or platform-owned input
   before any mutation-capable command.
3. Separate application-runtime teardown from legacy-edge retirement. Once App Platform owns the
   Shared Edge, Finance has no platform-edge `down` implementation.
4. Add deterministic command-substitution tests proving every refusal happens before Terraform,
   GCP, DNS, IAM, audience, registration, or state mutation.
5. Keep the pull request credential-free and non-mutating. Do not run a live teardown as part of
   code review or merge verification.

The next, separately approved operator step may run a Live teardown rehearsal only after App
Platform and the Finance candidate registration are ready. Its ordered acceptance is:

1. capture exact revisions, registration generation/digest, ownership manifest, application-state
   backup posture, and redacted pre-teardown readback;
2. suspend or retire the Finance registration and prove the active generation no longer routes to
   either attachment;
3. run only the Finance application-runtime `down` workflow with explicit data-loss approval;
4. prove the Finance path is unavailable without attempting either former origin;
5. prove the platform root catalogue, Fixture Applications, identity/session/signing services,
   Shared Edge, network, DNS, and Platform State remain healthy and drift-free; and
6. preserve evidence and require a separate owner decision before recreation or cleanup.

For the first non-production rehearsal, the unavailable path is
`https://apps-staging.comfforts.com/finance_assistant`. After a later production adoption, the same
invariant applies to `https://apps.comfforts.com/finance_assistant`: the Finance path may be
unavailable, but the platform hostname and unrelated applications must remain available.

## Identity migration requirement

The candidate deployment cannot use the current IAP-only identity implementation unchanged. It
must add a platform-assertion mode that:

- accepts identity only from the edge-controlled `X-Comfforts-Verified-Identity` header after
  independently verifying contract version, ES256 signature, exact issuer, Finance audience,
  subject, issued/expiry times, key identifier, and allowed clock skew;
- obtains public keys only from the reviewed platform JWKS boundary, applies the approved cache and
  rotation policy, and fails closed when valid material is unavailable;
- never trusts email, a Platform Session cookie, visitor authorization, or an edge-caller service
  account as the Application Principal;
- maps the verified immutable identity to a Finance-owned Principal and role/entitlement policy,
  with an explicit continuity or migration rule for data created under the IAP issuer/subject;
- rejects missing, visitor-supplied, ambiguous, wrong-audience, wrong-issuer, or expired assertions,
  and claims replay protection only to the extent implemented and accepted by the threat model; and
- keeps IAP mode available only to the unchanged legacy deployment for the approved rollback
  window. The candidate platform deployment has one authoritative identity mode and no second
  client-side login.

Platform Admission still does not grant a Finance role, Feature Entitlement, provider right,
spending authority, or access to another Principal's data.

## Qualification and handoff checklist

Stage A cannot activate until evidence shows:

- exact compatible Finance and platform revisions and contract digests;
- a deployed platform Shared Edge and qualified cross-project `gcp-cloud-run-v1` path;
- restricted owner admission using the immutable Google subject, not email;
- independent Finance verification of the platform assertion on every protected attachment;
- deliberate Application Principal continuity or migration with retained data access and rollback;
- frontend, API, upload, REST, SSE, redirects, cookies, logout, correlation, accessibility, and
  provider-rights behavior at `apps-staging.comfforts.com/finance_assistant`;
- direct-origin, visitor-header spoof, cross-application, cross-Principal, and same-origin request
  defenses;
- registration lifecycle and 24-hour attachment rollback behavior; and
- unchanged, usable `apps.comfforts.com` IAP service and Finance `edge` state.

The teardown rehearsal adds these gates: the Finance candidate path is unavailable, neither former
origin receives a request, every Finance candidate workload/data resource named by the approved
destroy manifest is absent, every platform-owned resource remains present and unchanged, and
unrelated platform routes still pass.

The later production transfer additionally requires before/after state-owner manifests, protected
state backups, zero destructive changes during import reconciliation, exact DNS/TLS readback,
teardown-refusal tests, a rehearsed owner-approved rollback, and proof that Finance no longer has a
mutation path to platform-owned resources.

## Owner decisions still open

- protected frontend verifier/gateway topology;
- separately named Stage A candidate services versus dual-edge use of the current IAP services;
- Finance Principal continuity and role provisioning without an email assertion;
- same-origin browser control for a shared hostname;
- exact cross-project Shared VPC/service-project and Cloud Run ingress design;
- immutable owner issuer/subject, catalogue visibility, and final catalogue text;
- whether production resources are managed in place or replaced in the platform project;
- whether preserving the global IP, certificate, or backend-service identities is mandatory;
- which project/state owns cross-project invoker and Shared VPC association resources;
- maintenance window, rollback objective, retained compatibility window, and cleanup approval; and
- the exact future Finance requirement, ADR, milestone, evaluation, and contract identifiers.
