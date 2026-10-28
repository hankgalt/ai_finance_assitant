# Backend package

FastAPI foundation, versioned contracts, the M1 offline knowledge pipeline, M2 deterministic finance modules, and M3 provider ports/adapters for AI Finance Assistant.

Runtime code performs read-only Qdrant compatibility checks and retrieval. Collection creation, source fetching, embedding, evaluation, activation, and rollback are available only through `python -m ai_finance_assistant.knowledge.cli` and the repository Make targets.

`ai_finance_assistant.finance` exposes the M2 PortfolioImport, PortfolioAnalysis, and GoalProjection interfaces plus the reserved CashFlowAnalysisService contract. These modules have no FastAPI route or persistence adapter yet; M5 owns those interfaces and lifecycle implementations.

`ai_finance_assistant.providers` exposes MarketDataProvider and NewsProvider ports, deterministic credential-free adapters, conditional Alpha Vantage/Massive market adapters, a Tavily news adapter, and explicit bundle factories. Credential-free mode is the default. `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive` selects one live market adapter before a workflow; there is no automatic mid-workflow fallback. Live adapters do not call the network until invoked and must pass account-rights, credential, readiness, and budget gates. M4 owns agent consumption and measured provider RunEvents; M5 owns API lifecycle integration.

The ordinary test suite excludes tests marked `live_provider`. With approved selected-market and Tavily credentials and terms flags in `backend/.env`, `make provider-live-check` explicitly enables two bounded smoke tests: at most three selected-market requests and one Tavily request. The market test validates each operation before starting the next one, so a failure does not consume quota on later operations. Restart a running backend after changing the environment-selected adapter. For Massive, individual-plan data must remain owner-only unless Business/commercial display rights cover the demo audience.

See the repository [README](../README.md), [documentation index](../docs/README.md), [M1 delivery report](../docs/M1_delivery_report.md), [M2 calculation policy](../docs/M2_calculation_policy.md), and [M3 provider policy](../docs/M3_provider_policy.md).
