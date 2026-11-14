# AI Finance Assistant documentation

Version 3.10 | Status: M0–M9.1/M6.1 and M2.1 complete; M11 credential-free MVP and owner-only live-provider posture qualified; M10 planned | 2026-11-13

This directory is the design authority for AI Finance Assistant. The product mission is to provide an intelligent, trustworthy, and accessible financial education and analysis platform for U.S. users and U.S. markets. The coursework capstone is an important release and evidence obligation, but it does not define the product's long-term identity.

## Colocated project authority

The [`apps-platform/`](../apps-platform/) subtree is a separately governed project. Its
[documentation](../apps-platform/docs/README.md) is authoritative only for App Platform. Platform
governance and inactive integration drafts do not alter the Finance Assistant requirements,
decisions, design, plans, contracts, deployment status, or qualification evidence recorded here.

## Reading order and authority

1. [Requirements specification](01_requirements_specification.md) defines product capabilities, quality attributes, release scope, and planned enhancements.
2. [Architecture decision records](02_architecture_decision_records.md) records consequential choices and their tradeoffs.
3. [System design](03_system_design.md) defines module interfaces, runtime flows, data contracts, six-agent responsibilities, and failure behavior.
4. [Implementation plan](04_implementation_plan.md) sequences delivery and maps the previous milestones to the revised plan.
5. [Evaluation strategy](05_evaluation_strategy.md) defines product release gates and coursework evidence.
6. [Coursework acceptance criteria](coursework_acceptance_criteria.md) preserves capstone and grading obligations separately from product requirements.
7. [Codex M0 starting prompt](06_codex_starting_prompt.md) is the bounded implementation prompt for the foundation milestone. It is an instruction artifact, not a record that M0 has been executed.
8. [Domain glossary](../GLOSSARY.md) provides canonical product terminology.
9. [Repository layout](repository_layout.md) defines capability ownership for committed data,
   artifacts, machine contracts, tests, and cross-product release evidence.
10. [M1 Qdrant, model, and source-use research](research/M1_qdrant_models_sources.md) records the primary-source evidence used for M1 decisions; it is not itself an ADR.
11. [M1 corpus-expansion research](research/M1_corpus_expansion_sources.md) records the bounded Finance and Tax source review and disabled-source decisions.
12. [M1 IRS publication closure research](research/M1_irs_publication_expansion_2025.md) verifies the requested 2025 editions, applicability, source-use boundaries, and retrieval cases.
13. [M2 calculation policy](M2_calculation_policy.md) records the implemented precision, import, coverage, heuristic, and M2.1 unrealized-performance rules for deterministic finance modules.
14. [M3 market and news provider candidate research](research/M3_provider_candidates.md) evaluates Tavily, Alpha Vantage, and yfinance against the provider seam; it is decision input, not an approved provider selection.
15. [M3 provider policy](M3_provider_policy.md) records the implemented adapters, endpoint policies, rights gate, quota budget, and safe fallback behavior.
16. [M3 Massive market-data adapter research](research/M3_massive_provider.md) evaluates Massive's technical fit, current Basic-plan limits, and owner-only individual-plan rights using official sources.
17. [M4.1 OpenAI model selection](research/M4_1_openai_model_selection.md) records the approved private-demo model, data controls, limits, cost posture, and revisit triggers.
18. [M6.1 response-cache dependency selection](research/M6_1_response_cache_dependencies.md) records the pinned Redis/RedisVL/encoder set, local security posture, licensing, and integration evidence.
19. [Managed-state deployment recommendations](research/managed_state_deployment_recommendations.md)
    records the primary-source service research behind the owner-approved deployment contract; the
    machine-readable contract, not the research alternatives, is the selected design authority.

Milestone completion evidence is recorded separately from the design authority. See
[M0 delivery report](M0_delivery_report.md) for the foundation milestone and
[M1 delivery report](M1_delivery_report.md) for persistent knowledge ingestion, retrieval evaluation, activation, and rollback, and
[M2 delivery report](M2_delivery_report.md) for deterministic Portfolio import/analysis, goal projection, and the reserved cash-flow interface, and
[M2.1 delivery report](M2_1_delivery_report.md) for cost-basis unrealized gain/return and top-five concentration, and
[M3 delivery report](M3_delivery_report.md) for market/news ports, deterministic adapters, and conditional live-provider adapters, and
[M4 delivery report](M4_delivery_report.md) for the six-agent graph, measured RunEvents, checkpoint behavior, and observability evidence, and
[M4.1 delivery report](M4_1_delivery_report.md) for the live model adapter and completed six-agent qualification evidence, and
[M5 delivery report](M5_delivery_report.md) for versioned REST/SSE, durable local persistence, the historical provider cache, and operational telemetry transport, and
[M6 delivery report](M6_delivery_report.md) for the responsive React product experiences, accessible chart/table evidence, portfolio import review, and privacy-safe browser telemetry, and
[M7 delivery report](M7_delivery_report.md) for the measured RunEvent Inspector, accessible timeline, graph reconciliation, reconnect behavior, and redaction evidence, and
[M6.1 delivery report](M6_1_delivery_report.md) records the evidence-bound public Finance/Tax response-cache seam, Redis qualification, calibration gate, and measured call avoidance, and
[M8 delivery report](M8_delivery_report.md) records the passing private-demo release qualification, owner-approved selected-model review, threat/observability/reliability evidence, and clean dependency scans, and
[M9 delivery report](M9_delivery_report.md) records the product/coursework release package,
read-only MCP client evidence, clean-start record, documentation, and demonstration bundle.
[M9.1 delivery report](M9_1_delivery_report.md) records the product-oriented repository-layout
migration, integrity reconciliation, and passing release qualification. [M11 application-access
delivery report](M11_application_access_delivery_report.md) records the implemented identity,
base-path, and per-Principal isolation slice without claiming cloud deployment qualification.
[M11 managed-state adapter report](M11_managed_state_adapter_report.md) records the selected
managed-state contract, PostgreSQL/checkpoint adapter, operator migration/retention seams, and the
deferred real-service recovery qualification. [M11 delivery pipeline report](M11_delivery_pipeline_report.md)
records digest-pinned non-root images, deterministic/security workflows, provenance and keyless
identity seams. [M11 staging infrastructure report](M11_staging_infrastructure_report.md) records the
provisioned Terraform state, registry, keyless identities, protected GitHub environments, budget,
private Cloud SQL foundation, drift evidence, deferred recovery work, and remaining MVP
workload/edge/knowledge gates. [M11 application workload report](M11_application_workload_report.md)
records the locally qualified separate-state Cloud Run definitions, migration-first lifecycle,
approved secret pattern, and the subsequently exercised create/destroy lifecycle. [M11 shared-
knowledge release report](M11_knowledge_release_report.md) records the snapshot-transfer,
qualification, alias rollback, least-privilege key, provider-boundary implementation, and qualified
live staging evidence. [M11 Qdrant runtime-key rotation report](M11_runtime_key_rotation_report.md)
records the focused replacement-key qualification, backend-only cutover/rollback, old-key
retirement, and qualified secret-free live staging evidence. [M11 private-edge implementation
report](M11_private_edge_report.md) records the repository-controlled HTTPS/IAP edge, generated
audience handoff, owner-only policy, reviewed DNS/OAuth procedure, and qualified live boundary.
[M11 private-demo qualification report](M11_private_demo_qualification_report.md) records the exact
assembled `credential_free` journeys, read-only operator preflight, synthetic cleanup, evidence
contract, and qualified live run for merged revision
`e66751dc36ed1cd342b0480248ce772c64896834`.
[M11 live-provider activation report](M11_live_provider_activation_report.md) records the approved
OpenAI/Massive/Tavily account-rights boundary, provider-side spend control, Secret Manager and
Terraform cutover/rollback seams, and the qualified merged-main owner-only live run for revision
`9f9c9c88b15139ebb19ed93dd76f8510ea5f9b20`.

The runnable release documentation is indexed by the [private-demo release
bundle](release/README.md); M9 evidence is indexed separately under
[docs/evidence/m9](evidence/m9/README.md).

If documents conflict, use this precedence: product requirements, accepted ADRs, system design, implementation plan, evaluation strategy, then the M0 prompt. Coursework criteria remain mandatory for the coursework release even when they do not constrain later product architecture. Resolve source-rubric ambiguities in the coursework criteria rather than weakening product requirements.

## Scope labels

- **Initial release:** required for the first product and coursework release unless a requirement explicitly says otherwise.
- **Private demonstration release:** production-oriented initial release operated only for the owner and approved viewers in a controlled local or private environment; it is not a public launch.
- **Coursework release:** submission-specific deliverables and grading evidence. These are mandatory for submission even if they are not enduring product constraints.
- **Planned enhancement:** architecturally acknowledged work that is not part of the initial release.
- **Private multi-user deployment:** an internet-routable deployment protected by strong identity,
  an explicit allow-list, and per-Principal authorization; it is not anonymous public access. M11
  now implements the application-access boundary. Its first cloud objective is a revocable,
  owner-operated private-demo MVP at the documented URL, not a production-ready service. The MVP is
  first qualified for the owner-only `credential_free` posture; the workload, shared knowledge,
  runtime-key rotation, private edge, direct-origin controls, and final integrated product journeys
  have revision-scoped evidence. The separately approved owner-only OpenAI/Massive/Tavily posture
  is also qualified by a merged-main operator run and provider-owned revision-scoped evidence. It
  does not enable viewers, broaden provider rights, or establish production readiness.
- **Production hardening:** controls beyond the private-demo MVP that are required before claiming
  production readiness or broader availability, including tested backup/recovery, availability,
  capacity/SLO, alerting, and incident-response objectives. Proposed or documented controls are not
  represented as implemented.
- **Out of scope:** excluded unless separately approved.

All controls and capabilities in these documents are requirements or designs until supported by completion evidence from the implementation plan. Documentation must not describe an unimplemented control as operational.

## Traceability convention

Product requirements use PR and QR identifiers. Coursework criteria use CA identifiers. Decisions use ADR identifiers. Milestones use M0 through M11, with M4.1 and M6.1 as explicitly sequenced intermediate gates. M10 and M11 are independent post-release tracks. Evaluation cases use EV identifiers. The requirements specification contains the cross-document traceability matrix; the coursework document contains the source-to-product mapping.

