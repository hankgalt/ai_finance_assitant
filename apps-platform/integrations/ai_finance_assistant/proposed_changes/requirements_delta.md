# Proposed Finance requirements delta

Status: **Integration Draft — inactive**

This file proposes future Finance requirement changes. It does not amend
`docs/01_requirements_specification.md` or change PR-017.

## Proposed changes at Application Adoption

- Replace Finance ownership of the shared `apps.comfforts.com` edge with a dependency on an adopted,
  versioned App Platform Application Registration for `/finance_assistant`.
- Preserve Finance ownership of Cloud Run workloads, application data, immutable Application
  Principals, per-Principal isolation, providers, provider rights, and Feature Entitlements.
- Require Finance to reject requests lacking the adopted Verified Identity Context even when the
  platform admitted the request.
- Preserve local `/finance_assistant` development and the public browser/API/SSE path contracts.
- Require the Finance deployment to fail closed when registration outputs or the signed-IAP audience
  are absent, invalid, or stale.
- Separate application runtime lifecycle from Shared Edge lifecycle and prevent Finance teardown
  from deleting platform-owned resources.
- Preserve Restricted, owner-only admission during the edge-ownership migration; the cutover may not
  bundle an application-access expansion.
- Record a separate post-migration target of Authenticated admission for any successfully
  authenticated Google identity supported by the adopted identity boundary.
- Keep feature access application-owned so an admitted, isolated Principal may use unrestricted
  Finance functionality while being denied market data or another restricted capability.
- Keep Massive Stocks Basic personal-use market data owner-only unless Finance separately adopts a
  plan and Feature Entitlement policy that permits display to additional users. Reconfirm every
  other provider's rights and limits independently.

## Proposed non-goals

- No Finance data, knowledge collection, provider credential, or provider payload migration
- No new provider display, caching, retention, redistribution, or spending right
- No production-readiness, availability, backup, or disaster-recovery claim
- No current change to PR-017 or its qualified private-demo evidence
