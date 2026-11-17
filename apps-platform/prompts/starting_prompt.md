# App Platform Terraform-and-workflow handoff

Continue the separately governed Comfforts App Platform project. While it is colocated, its project
root is `apps-platform/`; after repository extraction, use the dedicated repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, AP-M5 supplies accepted infrastructure-planning authority, and AP-M6 implements the
networked Shared Edge and production-adapter logic locally through deterministic fakes and process-
local loopback. The complete AP-EVAL-M6 repository gate passes. No Terraform configuration,
backend, workflow authority, cloud resource, DNS change, credential, deployment, Application
Adoption, or Live (`L`) evidence is implemented or qualified merely because those earlier slices
exist.

Use this handoff only from updated `main` after the AP-M6 pull request has merged. If AP-M6 is not
in `main`, the working tree is not clean, or the requested branch already contains AP-M7 changes,
report that conflict and stop instead of switching, pulling, resetting, committing, or combining
slices without owner direction.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform project root. While colocated, also preserve the
   containing repository's security, source-control, secret-handling, and destructive-action
   guardrails.
2. Inspect the working tree, branch, and relationship to `main`. Preserve unrelated changes and
   report any state that conflicts with the incremental delivery sequence instead of resetting,
   pulling, switching, or committing without owner direction.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/04_implementation_plan.md` and `docs/05_evaluation_strategy.md` completely. Treat the
   current AP-M7 text and AP-EVAL-M7 future boundary as inputs to a detailed authority proposal,
   not as sufficient authority to implement Terraform or workflows.
5. Read `contracts/README.md`, `fixtures/registrations/README.md`, `Makefile`, `.gitignore`, and the
   current repository workflow wrappers needed to preserve extraction and default-check behavior.
6. State the proposed AP-M7 slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-TM-*`, `AP-M7`, and
   `AP-EVAL-M7` identifier it implements. Treat absent detailed work packages, configuration
   contracts, evaluation commands, and acceptance authority as unresolved.
7. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize Application
   Adoption.

Next task: propose AP-M7, the smallest Terraform-and-workflow implementation-authority slice. It
must refine the system design, implementation plan, threat controls, repository layout, and
AP-EVAL-M7 before implementation. Identify the exact documents, configuration contracts, Terraform
roots and reusable modules, workflow templates, static policy checks, deterministic tests, small
commits, and acceptance boundary it would add or update. Wait for owner approval before editing.

The proposal must preserve separate backend-bootstrap, Platform State, and per-Fixture-Application
State roots; typed non-secret cross-state inputs without `terraform_remote_state`; explicit plan,
apply, rollback, unlock, and destroy authorities; source-revision binding; extraction-safe workflow
templates; and credential-free formatting, validation, policy, and configuration tests. Reusable
modules must not own environment state or silently embed operator-specific values.

Treat globally unique bucket names, the dedicated GitHub organization and repository, workflow
subjects, DNS managed-zone resource, OAuth client references, notification destination, and the
initial Live Registration Set as unresolved operator inputs. Separate their reviewed configuration
from reusable behavior rather than querying a provider or inventing defaults.

Do not initialize a Terraform backend, run an authenticated plan or apply, create or read a
credential, call GCP, modify repository settings, configure identity or DNS, deploy a service,
create state or a saved plan, or claim deployed or Live evidence. AP-M7 belongs on a new bounded
branch and pull request after AP-M6 merges. Static configuration is not provider or deployment
evidence.

Keep the proposal inside the App Platform boundary. Leave Finance Assistant requirements, code,
infrastructure, Terraform state, DNS, identity configuration, deployment, and access unchanged. An
Integration Draft is not Application Adoption.

The default verification command is `make check` from the project root or
`make -C apps-platform check` while colocated. It must remain credential-free, deterministic, and
non-mutating.
