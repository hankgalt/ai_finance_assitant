# Finance Assistant integration draft

Status: **Integration Draft — inactive**

Consumer: AI Finance Assistant

Finance source baseline: `9dedac71ad358deb5ef1c02e2f0fea6e21773a71`

This package preserves the proposed migration from the Finance Assistant-owned edge at
`apps.comfforts.com` to Comfforts App Platform. It is an input to future Application Adoption, not
authority for either project. It does not modify Finance requirements, decisions, design, plans,
evaluation, Terraform, DNS, IAM, OAuth, secrets, state, or deployed resources.

## Authority and precedence

- App Platform requirements and accepted ADRs remain authoritative for platform behavior.
- The Finance Assistant repository remains authoritative for its application and current deployed
  edge until it explicitly adopts a migration through its own release process.
- Current Finance documents, contracts, Terraform, and evidence take precedence over every proposed
  delta in this package.
- The draft must be reconciled against the then-current revisions of both projects before adoption;
  the recorded source baseline is not a permanent compatibility claim.

## Package contents

- [Edge migration contract draft](edge_migration_contract.draft.md) records the proposed ownership
  transfer, cutover invariants, rollback boundary, and unresolved design decisions.
- [Requirements delta](proposed_changes/requirements_delta.md) lists future Finance requirement
  changes.
- [Architecture decisions delta](proposed_changes/architecture_decisions_delta.md) lists future ADR
  changes and supersession boundaries.
- [System-design delta](proposed_changes/system_design_delta.md) describes the proposed integration
  boundary.
- [Implementation-plan delta](proposed_changes/implementation_plan_delta.md) proposes a future
  Finance-owned migration slice.
- [Evaluation-strategy delta](proposed_changes/evaluation_strategy_delta.md) proposes adoption and
  rollback evidence.
- [Repository-layout delta](proposed_changes/repository_layout_delta.md) identifies ownership moves
  without moving files now.

## Activation boundary

This package becomes actionable only after all of the following occur:

1. App Platform system design, versioned registration/attachment contracts, implementation plan,
   evaluation strategy, and threat model are approved.
2. Fixture Applications qualify the relevant Shared Edge, admission, identity, lifecycle, and
   rollback behavior.
3. The Finance Application Owner adopts revised content in the Finance authorities named above.
4. Both projects approve one revision-scoped cutover and rollback procedure with exclusive resource
   ownership at every phase.

Copying, merging, or extracting this package does not satisfy Application Adoption.
