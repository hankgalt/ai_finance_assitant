# AI Finance Assistant documentation

Version 1.4 | Status: Product architecture baseline; M0–M2 evidence recorded | 2026-10-27

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

Milestone completion evidence is recorded separately from the design authority. See
[M0 delivery report](M0_delivery_report.md) for the foundation milestone and
[M1 delivery report](M1_delivery_report.md) for persistent knowledge ingestion, retrieval evaluation, activation, and rollback, and
[M2 delivery report](M2_delivery_report.md) for deterministic Portfolio import/analysis, goal projection, and the reserved cash-flow interface.

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

Product requirements use PR and QR identifiers. Coursework criteria use CA identifiers. Decisions use ADR identifiers. Milestones use M0 through M10. Evaluation cases use EV identifiers. The requirements specification contains the cross-document traceability matrix; the coursework document contains the source-to-product mapping.

