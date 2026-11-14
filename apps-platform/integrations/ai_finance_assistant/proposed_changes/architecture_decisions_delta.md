# Proposed Finance architecture-decision delta

Status: **Integration Draft — inactive**

This file proposes a future Finance-owned ADR update. It does not amend or supersede ADR-030.

## Proposed decision boundary

At Application Adoption, Finance would accept App Platform as the sole owner of the Shared Edge for
`apps.comfforts.com` and consume a versioned registration/identity contract. Finance would continue
to own and enforce signed identity validation, immutable Application Principal derivation,
per-Principal resource isolation, application roles, provider rights, and Feature Entitlements.

The future Finance ADR should narrow only the edge-ownership portions of ADR-030. ADR-030's qualified
history, base-path contract, no-direct-origin requirement, signed-assertion validation, data
isolation, local-development identity, and provider-rights boundaries remain applicable unless a
separate Finance decision changes them.

## Required recorded trade-offs

- shared platform ownership versus continuing Finance-specific edge ownership;
- preserving existing edge resource identities versus planned replacement and downtime;
- shared authentication infrastructure versus app-specific Application Principals;
- platform admission versus Finance feature authorization; and
- state transfer versus parallel reconstruction, with dual ownership prohibited.

The accepted Finance decision must name the adopted platform contract versions and the exact ADR-030
clauses it supersedes. A platform ADR cannot supersede a Finance ADR.

The ownership decision should preserve the current Restricted, owner-only Admission Mode during
migration. A later Finance ADR may target Authenticated admission for any successfully authenticated
Google identity, but it must keep application Feature Entitlements and provider rights separate from
platform admission. Under the current Massive Stocks Basic personal-use right, that later admission
change cannot authorize market-data display to other users.
