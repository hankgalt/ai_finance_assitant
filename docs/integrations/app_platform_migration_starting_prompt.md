# App Platform migration Codex starting prompt

Status: **Proposed Finance migration input — inactive**

Use this prompt only after the owner confirms that App Platform is ready to accept a Live Finance
registration. Update the pinned revisions before starting.

```text
Continue the separately governed AI Finance Assistant project from its dedicated repository root.
The task is to plan Finance Assistant Application Adoption by the canonical
https://github.com/comfforts/apps-platform project. An Integration Draft or a platform registration
does not change Finance authority.

Before editing:

1. Read and follow AGENTS.md. Inspect the working tree, branch, remotes, and relationship to main.
   Preserve unrelated work and report conflicts; do not pull, switch, reset, commit, or mutate live
   systems without owner direction.
2. Read docs/README.md, docs/01_requirements_specification.md,
   docs/02_architecture_decision_records.md, docs/03_system_design.md,
   docs/04_implementation_plan.md, docs/05_evaluation_strategy.md, GLOSSARY.md, and
   docs/repository_layout.md as Finance authority.
3. Then read docs/integrations/app_platform_migration_handoff.md and
   docs/integrations/app_platform_migration_assets.md completely as inactive planning inputs.
4. Read the canonical App Platform AGENTS.md, documentation authority, current accepted contracts,
   implementation plan, threat model, Live evidence, and inactive Finance integration package at an
   exact merged revision. Do not use a stale pinned revision merely because it appears in the
   Finance handoff.
5. State the proposed post-M11 Finance slice and every PR-*, QR-*, ADR-*, milestone, evaluation, and
   platform contract identifier it would implement. Treat absent Finance authority or absent
   platform Live/cross-project evidence as unresolved and stop before implementation.

First propose only Stage A: qualify Finance as cross-project Cloud Run attachments at
https://apps-staging.comfforts.com/finance_assistant. Preserve the existing
https://apps.comfforts.com/finance_assistant IAP edge, DNS, certificate, OAuth client, global IP,
Terraform edge state, and rollback path. Stage A transfers no existing edge resource and performs
no production DNS cutover.

After Finance adoption authority is approved, change and test the down scripts before running any
of them. Make teardown ownership isolation the first implementation pull request: add the exclusive
ownership manifest, make every Finance down path fail before any mutation-capable command on
missing, stale, mixed, or platform ownership, and add deterministic command-substitution tests. Do
not run a Live teardown in that pull request. Never filter or target-destroy a mixed-owner
Terraform state; transferred addresses must already be absent from Finance state and exclusively
owned by Platform State.

The proposal must reconcile:

- the exact Version 1 or current Registration Set and attachment schemas;
- application ID finance-assistant and route /finance_assistant;
- separate web and api attachment mappings and path forwarding;
- restricted owner admission using an immutable Google issuer/subject;
- platform ES256 assertion verification without trusting email or visitor headers;
- Application Principal and retained-data continuity from the current IAP issuer/subject;
- a protected frontend verifier/gateway, backend verification, Shared VPC/cross-project reachability,
  Cloud Run labels/annotation/IAM, and direct-origin denial;
- the recommended use of separately named, Finance-owned Stage A Cloud Run candidate services so
  qualification does not alter the current IAP workload targets, or an explicitly approved and
  verified dual-edge trust design if the current services are reused;
- REST, SSE, uploads, redirects, cookies, logout, correlation, provider rights, accessibility,
  same-origin/browser security, rollback, and independent application releases; and
- deterministic and Live evidence at exact Finance and platform revisions.

Explicitly inventory every Finance Terraform root and operator script. The current
private-edge-down path can destroy the load balancer, certificate, forwarding rules, endpoint
groups, backend services, IAP bindings, and global IP. Before any later ownership transfer, require
an exclusive versioned ownership manifest and change Finance edge teardown to fail closed before
Terraform initialization whenever Platform State owns any target. Require application-runtime
teardown to refuse while an active platform generation references its attachments. Finance scripts
must never destroy, detach, import, remove, plan, or apply platform-owned resources or Platform
State.

Once the script changes are merged and the platform/candidate registration is qualified, propose a
separately approved Live teardown rehearsal. Suspend or retire the Finance registration first, then
destroy only Finance-owned candidate application runtime and data. Prove the Finance path is
unavailable while the platform root catalogue, Fixture Applications, Shared Edge,
identity/session/signing resources, network, DNS, and Platform State remain healthy and unchanged.
Use apps-staging.comfforts.com first. After production adoption, the same invariant applies at
apps.comfforts.com: only /finance_assistant may become unavailable; the shared hostname and other
applications must remain available.

After Stage A is accepted, propose Stage B separately: either import existing production edge
resources into Platform State while they remain in the Finance GCP project, or create replacement
platform-project resources and perform an explicit DNS/TLS cutover. Explain that Terraform import
changes state management but does not move a GCP resource between projects. Prohibit dual state
ownership and require separately approved state/DNS/IAM/destructive commands and rollback.

For the first response, report prerequisite evidence, current gaps, exact documents/contracts to
change, small proposed commits, acceptance boundary, and every owner decision still required. Wait
for owner approval before editing. Do not run Terraform, gcloud mutation, state, DNS, IAM, OAuth,
secret, deployment, or teardown commands. All proposal verification must be credential-free,
deterministic, and non-mutating.
```

The future chat must replace the historical revision pins with the exact revisions it actually
reviews. It must not infer readiness from file presence or from the inactive integration package.
