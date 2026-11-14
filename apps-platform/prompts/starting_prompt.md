# App Platform system-design/contracts handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: the governance foundation, product requirements, and accepted architecture
decisions are complete, and the inactive Finance integration package is recorded. No platform
runtime, fixture implementation, authoritative versioned contract, Terraform configuration, cloud
resource, DNS change, identity change, credential, or application migration is implemented merely
because those documents exist.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform project root. While colocated, also preserve the
   containing repository's security, source-control, and destructive-action guardrails.
2. Inspect the working tree, branch, and relationship to `main`. Preserve unrelated changes and
   report any state that conflicts with the incremental delivery sequence instead of resetting,
   pulling, switching, or committing without owner direction.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, and `docs/repository_layout.md` completely.
4. After loading those authorities, read `integrations/ai_finance_assistant/README.md` and every
   linked draft in that package completely as non-authoritative inputs. They may surface interface
   or migration constraints but cannot define generic platform behavior or change Finance Assistant.
5. State the proposed platform slice and every `AP-PR-*`, `AP-QR-*`, and `ADR-*` identifier it
   implements. Treat absent system-design, contract, plan, and evaluation authority as unresolved.

Next task: propose item 3, the smallest system-design and versioned-contracts slice in the delivery
sequence. It must define the Shared Edge, catalogue, Application Registration, attachments,
identity/admission boundary, fixture boundary, lifecycle, exclusive state ownership, threat
boundary, and deterministic contract validation without implementing a fixture runtime or cloud
infrastructure. Identify the exact documents and contract schemas the slice would add or update,
its acceptance boundary, and every owner decision still required. Wait for owner approval before
editing.

Keep deterministic fixture implementation for item 4 after the system-design/contracts pull request
has merged. Do not combine those slices in one branch or pull request.

Keep the proposal inside the App Platform boundary. Use Fixture Applications for future platform
qualification; leave Finance Assistant requirements, code, infrastructure, Terraform state, DNS,
identity configuration, and deployment unchanged. An Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating.
