# Backend package

FastAPI foundation, versioned contracts, the M1 offline knowledge pipeline, and M2 deterministic finance modules for AI Finance Assistant.

Runtime code performs read-only Qdrant compatibility checks and retrieval. Collection creation, source fetching, embedding, evaluation, activation, and rollback are available only through `python -m ai_finance_assistant.knowledge.cli` and the repository Make targets.

`ai_finance_assistant.finance` exposes the M2 PortfolioImport, PortfolioAnalysis, and GoalProjection interfaces plus the reserved CashFlowAnalysisService contract. These modules have no FastAPI route or persistence adapter yet; M5 owns those interfaces and lifecycle implementations.

See the repository [README](../README.md), [documentation index](../docs/README.md), [M1 delivery report](../docs/M1_delivery_report.md), and [M2 calculation policy](../docs/M2_calculation_policy.md).
