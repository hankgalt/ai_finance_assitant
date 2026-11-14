# Proposed Finance implementation-plan delta

Status: **Integration Draft — inactive**

This file proposes a future Finance-owned migration slice. It does not add work to M11 or authorize
changes to `docs/04_implementation_plan.md`.

## Proposed future slice

The Finance plan should add one migration slice only after App Platform fixture qualification. Its
dependencies must include accepted platform system design/contracts, Finance adoption requirements
and ADRs, qualified registration compatibility, protected state backends, and an approved cutover
and rollback procedure.

Proposed deliverables:

1. Freeze and reconcile the qualified Finance edge baseline.
2. Implement the Finance side of the versioned registration and attachment contract without changing
   public routing.
3. Add deterministic compatibility, fail-closed audience, identity, and ownership tests.
4. Qualify the inactive Finance registration against fixture-qualified platform behavior.
5. Review resource/state manifests and replacement-free or explicitly destructive plans.
6. Execute the single-owner edge state handoff and platform reconciliation.
7. Propagate adopted platform outputs to Finance-owned workloads.
8. Run live cutover, product-parity, identity-isolation, provider-boundary, and rollback gates.
9. Retire active Finance edge mutation code only after acceptance; retain historical evidence.

The slice is incomplete until both repositories record compatible revisions and no resource remains
under dual state ownership. Failure before final acceptance must leave one reviewed owner capable of
rollback without deleting Finance application state.

## Separately sequenced access-model slice

Only after the edge-ownership migration is accepted should Finance plan an access-model expansion.
That later slice may change the adopted registration from Restricted owner-only admission to
Authenticated admission for any successfully authenticated Google identity. It must independently
qualify immutable Principal creation, cross-Principal isolation, revocation, abuse and spending
controls, and application-owned Feature Entitlements.

The later slice must prove that a newly admitted, non-entitled user can use otherwise available
Finance functionality but cannot receive Massive Stocks Basic personal-use market data. It must
reconfirm OpenAI, Tavily, and other provider rights separately and must have its own rollback to the
last qualified admission policy.
