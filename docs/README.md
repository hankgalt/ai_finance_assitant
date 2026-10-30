# AI Finance Assistant documentation

Version 2.2 | Status: Product architecture baseline; M0–M6 evidence recorded and M6.1 response-cache preparation planned | 2026-10-29

This directory is the design authority for AI Finance Assistant. The product mission is to provide an intelligent, trustworthy, and accessible financial education and analysis platform for U.S. users and U.S. markets. The coursework capstone is an important release and evidence obligation, but it does not define the product's long-term identity.

## Reading order and authority

1. [Requirements specification](01_requirements_specification.md) defines product capabilities, quality attributes, release scope, and planned enhancements.
2. [Architecture decision records](02_architecture_decision_records.md) records consequential choices and their tradeoffs.
3. [System design](03_system_design.md) defines module interfaces, runtime flows, data contracts, six-agent responsibilities, and failure behavior.
4. [Implementation plan](04_implementation_plan.md) sequences delivery and maps the previous milestones to the revised plan.
5. [Evaluation strategy](05_evaluation_strategy.md) defines product release gates and coursework evidence.
6. [Coursework acceptance criteria](coursework_acceptance_criteria.md) preserves capstone and grading obligations separately from product requirements.
7. [Codex M0 starting prompt](06_codex_starting_prompt.md) is the bounded implementation prompt for the foundation milestone. It is an instruction artifact, not a record that M0 has been executed.
8. [Domain glossary](../GLOSSARY.md) provides canonical product terminology.
9. [M1 Qdrant, model, and source-use research](research/M1_qdrant_models_sources.md) records the primary-source evidence used for M1 decisions; it is not itself an ADR.
10. [M2 calculation policy](M2_calculation_policy.md) records the implemented precision, import, coverage, and heuristic rules for deterministic finance modules.
11. [M3 market and news provider candidate research](research/M3_provider_candidates.md) evaluates Tavily, Alpha Vantage, and yfinance against the provider seam; it is decision input, not an approved provider selection.
12. [M3 provider policy](M3_provider_policy.md) records the implemented adapters, endpoint policies, rights gate, quota budget, and safe fallback behavior.
13. [M3 Massive market-data adapter research](research/M3_massive_provider.md) evaluates Massive's technical fit, current Basic-plan limits, and owner-only individual-plan rights using official sources.
14. [M4.1 OpenAI model selection](research/M4_1_openai_model_selection.md) records the approved private-demo model, data controls, limits, cost posture, and revisit triggers.

Milestone completion evidence is recorded separately from the design authority. See
[M0 delivery report](M0_delivery_report.md) for the foundation milestone and
[M1 delivery report](M1_delivery_report.md) for persistent knowledge ingestion, retrieval evaluation, activation, and rollback, and
[M2 delivery report](M2_delivery_report.md) for deterministic Portfolio import/analysis, goal projection, and the reserved cash-flow interface, and
[M3 delivery report](M3_delivery_report.md) for market/news ports, deterministic adapters, and conditional live-provider adapters, and
[M4 delivery report](M4_delivery_report.md) for the six-agent graph, measured RunEvents, checkpoint behavior, and observability evidence, and
[M4.1 delivery report](M4_1_delivery_report.md) for the live model adapter and completed six-agent qualification evidence, and
[M5 delivery report](M5_delivery_report.md) for versioned REST/SSE, durable local persistence, the historical provider cache, and operational telemetry transport, and
[M6 delivery report](M6_delivery_report.md) for the responsive React product experiences, accessible chart/table evidence, portfolio import review, and privacy-safe browser telemetry.

If documents conflict, use this precedence: product requirements, accepted ADRs, system design, implementation plan, evaluation strategy, then the M0 prompt. Coursework criteria remain mandatory for the coursework release even when they do not constrain later product architecture. Resolve source-rubric ambiguities in the coursework criteria rather than weakening product requirements.

## Scope labels

- **Initial release:** required for the first product and coursework release unless a requirement explicitly says otherwise.
- **Private demonstration release:** production-oriented initial release operated only for the owner and approved viewers in a controlled local or private environment; it is not a public launch.
- **Coursework release:** submission-specific deliverables and grading evidence. These are mandatory for submission even if they are not enduring product constraints.
- **Planned enhancement:** architecturally acknowledged work that is not part of the initial release.
- **Production hardening:** required before exposing the product as a public multi-user service, but not represented as implemented in the initial local release.
- **Out of scope:** excluded unless separately approved.

All controls and capabilities in these documents are requirements or designs until supported by completion evidence from the implementation plan. Documentation must not describe an unimplemented control as operational.

## Traceability convention

Product requirements use PR and QR identifiers. Coursework criteria use CA identifiers. Decisions use ADR identifiers. Milestones use M0 through M10, with M4.1 and M6.1 as explicitly sequenced intermediate gates. Evaluation cases use EV identifiers. The requirements specification contains the cross-document traceability matrix; the coursework document contains the source-to-product mapping.

