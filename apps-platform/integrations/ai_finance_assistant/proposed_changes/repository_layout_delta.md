# Proposed Finance repository-layout delta

Status: **Integration Draft — inactive**

This file proposes future ownership moves. It does not move, delete, or deprecate any Finance file.

## Proposed ownership after adoption

| Current Finance capability | Proposed disposition |
| --- | --- |
| `infrastructure/terraform/modules/private_edge/` | Replace active Finance ownership with platform Shared Edge modules; retain history |
| `infrastructure/terraform/environments/staging-edge/` | Retire after the edge resources have one qualified Platform State owner |
| `infrastructure/terraform/scripts/*private-edge*` | Replace active mutation entry points with a Finance registration/adoption interface |
| `contracts/deployment/private-edge.v1.json` | Retain as historical M11 contract; add a Finance-side adopted registration contract elsewhere |
| Private-edge and private-demo evidence | Retain immutably as pre-migration historical evidence |
| Finance workload Terraform | Retain; consume versioned platform outputs without owning edge resources |
| Finance identity/application-access code | Retain; continue signed assertion validation, Principal derivation, and authorization |
| Finance provider and entitlement contracts | Retain unchanged unless separately approved |

The platform repository would own generic Shared Edge, catalogue, registration, admission, fixture,
and platform evidence paths. It must not absorb Finance source code, application tests, provider
contracts, user data, or historical evidence.

## Extraction and history

The integration package remains an inactive platform-side proposal after subtree extraction. At
Application Adoption, Finance should incorporate approved deltas into its own capability-oriented
locations rather than linking active authority back to this package.
