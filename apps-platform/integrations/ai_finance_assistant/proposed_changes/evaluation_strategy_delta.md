# Proposed Finance evaluation-strategy delta

Status: **Integration Draft — inactive**

This file proposes future Finance evaluation gates. It does not modify
`docs/05_evaluation_strategy.md` or qualify migration.

## Deterministic gates

- registration schema, unique route, base-path rewrite, attachment, and lifecycle compatibility;
- one-owner state manifests with no overlapping platform/application resource addresses;
- fail-closed missing/stale audience and forged/unsigned identity cases;
- immutable Application Principal and complete cross-Principal denial after the edge-owner change;
- application-owned Feature Entitlement denial after successful platform admission;
- no direct Cloud Run origin, anonymous invoker, cross-application route, or unmatched-route leak;
- no provider-rights, cache, retention, display, or spending broadening; and
- extraction-safe platform checks that do not import Finance code or credentials.

## Live adoption gates

- unchanged or explicitly approved DNS address and active hostname certificate;
- HTTP-to-HTTPS redirect, root catalogue, exact Finance routes, API rewrite, and closed unmatched
  paths;
- selected Finance admission, signed identity/audience validation, IAP-service-agent-only invocation,
  and direct-origin denial;
- critical Finance frontend/API/SSE, Portfolio, Goal, History, Inspector, knowledge, and provider
  journeys under the adopted Principal boundary;
- before/after Terraform state ownership and drift readback;
- no secret payload in plans, state, repositories, workflows, logs, or evidence; and
- rollback rehearsal that restores a reviewed working route without dual state ownership.

The ownership-migration gate must verify that Finance remains Restricted and owner-only; a passing
migration cannot claim broader application admission.

## Future access-expansion gates

A separately adopted Finance evaluation should prove that:

- a successfully authenticated Google identity outside the former owner allow-list can reach the
  Finance application while anonymous and spoofed identities remain denied;
- the application derives a distinct immutable Principal and preserves complete cross-Principal
  isolation;
- the admitted Principal can use otherwise available product functionality;
- application Feature Entitlements deny Massive Stocks Basic personal-use market data and every
  other unapproved provider-backed feature;
- provider plans, display/retention rights, request limits, and spending controls are independently
  read back and evidenced; and
- revocation and rollback restore the last qualified Admission Mode without altering retained
  application data.

## Evidence semantics

Platform fixture evidence is a prerequisite, not proof of Finance compatibility. Finance adoption
evidence must be revision-scoped, secret-free, retain links to historical M11 evidence, record every
skipped or failed gate, and avoid production-readiness claims.
