# App Platform documentation

Version 0.1 | Status: governance foundation; requirements and architecture decisions pending

This directory is the design authority for Comfforts App Platform. The current slice establishes
project governance only. It does not claim that the catalogue, Shared Edge, identity boundary,
fixture applications, Terraform, or any cloud resource exists.

## Current reading order and authority

1. [Project overview](../README.md) states the current operational status and project boundary.
2. [Domain glossary](../GLOSSARY.md) supplies canonical governance terms.
3. [Repository layout](repository_layout.md) defines capability ownership and extraction rules.
4. [Prompt ownership](../prompts/README.md) keeps task entry points separate from specifications.

The next approved documentation slice will add the platform requirements and architecture decision
records. System design, implementation planning, evaluation strategy, threat modeling, contracts,
fixtures, and Terraform remain deferred until their owning slice is approved. An absent authority
must not be inferred from discussion history.

## Future document precedence

Once present, conflicts will be resolved in this order:

1. Requirements specification
2. Accepted architecture decision records
3. System design
4. Implementation plan
5. Evaluation strategy
6. Runbooks and delivery evidence
7. Prompts

Until those documents exist, this governance foundation authorizes documentation and deterministic
governance checks only.

## Scope labels

- **Governance foundation:** project authority, vocabulary, layout, agent routing, and checks without
  product behavior.
- **Proposed:** a requirement or decision awaiting its named validation and approval.
- **Implemented:** repository behavior exists and passes deterministic checks; no live operation is
  implied.
- **Qualified:** the declared evaluation gate has revision-scoped evidence.
- **Integration draft:** a non-authoritative input for a consuming application.
- **Historical evidence:** an immutable account of an earlier implementation or qualification.

## Application boundary

The App Platform will own only capabilities accepted by its future requirements. Application data,
provider rights, feature entitlements, and product behavior remain under each application's own
authority. Nothing under this subtree changes the active Finance Assistant requirements, contracts,
Terraform state, DNS, IAP configuration, or deployment.

## Evidence discipline

Documentation and source files are not operational evidence. Each future capability must name its
deterministic tests and, where applicable, secret-free live evidence. Credentials, Terraform state,
saved plans, authenticated browser state, and unredacted external payloads are never committed.
