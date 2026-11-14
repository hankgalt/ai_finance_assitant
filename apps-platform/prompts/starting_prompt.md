# App Platform system-design handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: the governance foundation, product requirements, and accepted architecture
decisions are complete. No platform runtime, fixture, contract, Terraform configuration, cloud
resource, DNS change, identity change, credential, or application migration is implemented merely
because those documents exist.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform project root. While colocated, also preserve the
   containing repository's security, source-control, and destructive-action guardrails.
2. Inspect the working tree and preserve unrelated changes.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, and `docs/repository_layout.md` completely.
4. After loading those authorities, read `integrations/ai_finance_assistant/README.md` and every
   linked draft in that package completely as non-authoritative inputs. They may surface interface
   or migration constraints but cannot define generic platform behavior or change Finance Assistant.
5. State the proposed platform slice and every `AP-PR-*`, `AP-QR-*`, and `ADR-*` identifier it
   implements. Treat absent system-design, contract, plan, and evaluation authority as unresolved.

Next task: propose the smallest system-design slice that can define the Shared Edge, Application
Registration, identity/admission boundary, fixture boundary, and exclusive state ownership without
implementing them. Identify the exact documents the slice would add or update, any contract work
that must remain separate or be proposed explicitly, its acceptance boundary, and every owner
decision still required. Wait for owner approval before editing.

Keep the proposal inside the App Platform boundary. Use Fixture Applications for future platform
qualification; leave Finance Assistant requirements, code, infrastructure, Terraform state, DNS,
identity configuration, and deployment unchanged. An Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating.
