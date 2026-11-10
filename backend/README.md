# Backend package

FastAPI versioned resources, durable local or managed persistence, the offline knowledge pipeline, deterministic finance modules, provider ports/adapters, the six-agent LangGraph workflow, conditional OpenAI adapter, historical and response caches, operational telemetry, and the read-only MCP adapter for AI Finance Assistant.

Runtime code performs read-only Qdrant compatibility checks and retrieval. Collection creation, source fetching, embedding, evaluation, activation, and rollback are available only through `python -m ai_finance_assistant.knowledge.cli` and the repository Make targets.

`ai_finance_assistant.finance` exposes the M2 PortfolioImport, PortfolioAnalysis, and GoalProjection interfaces plus the reserved CashFlowAnalysisService contract. M5 exposes Portfolio import/validation, saved Portfolio/Snapshot, and goal-projection routes while preserving deterministic numerical authority. The future cash-flow module remains M10 work.

`ai_finance_assistant.providers` exposes MarketDataProvider and NewsProvider ports, deterministic credential-free adapters, conditional Alpha Vantage/Massive market adapters, a Tavily news adapter, and explicit bundle factories. Credential-free mode is the default. `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive` selects one live market adapter before a workflow; there is no automatic mid-workflow fallback. M5 adds an application-owned two-tier cache for normalized historical daily bars with range coverage, gap fetches, recent-tail refresh, restart reuse, purge, provenance, and rights gating.

`ai_finance_assistant.workflow.WorkflowApplication` assembles exactly six specialist agents plus a new selected provider bundle and model adapter for each Run. The compiled graph asks that fixed adapter for a schema-constrained routing decision, executes one or more selected domains, enforces deadline/hop bounds, preserves independent partial results, synthesizes typed output, and checkpoints follow-up routing by Session/Workflow thread. Credential-free mode uses scripted deterministic outputs. Conditional live mode uses OpenAI `gpt-6.1-sol` through Responses structured output with `store=False`, no tools, bounded retries, and a seven-attempt Run budget covering one route plus at most six specialist responses. M5 supplies versioned REST, replayable SSE, durable RunEvents/results, and the official SQLite checkpoint adapter.

`ai_finance_assistant.observability` provides disabled, in-memory, and OpenTelemetry modes behind a small interface. RunEvents remain the authoritative product record. OpenTelemetry attributes are allow-listed and exporter failure is isolated. Optional LangSmith tracing is disabled by default and creates a client with inputs and outputs hidden when explicitly enabled. `AIFA_WORKFLOW_ID` owns the Run and checkpoint namespace, `AIFA_LANGSMITH_PROJECT` selects the LangSmith destination, and `AIFA_OTEL_SERVICE_NAME` identifies the OpenTelemetry service; these identities are intentionally configured separately. The root trace name is the Run's stable workflow identifier rather than the project name. M5 instruments FastAPI, HTTPX, modules, cache, and persistence and supplies an optional loopback OTLP Collector debug sink; browser telemetry belongs to M6.

`ai_finance_assistant.mcp_adapter` exposes exactly four read-only stdio tools: education search, market quote, in-memory Portfolio analysis, and Goal projection. It reuses application validation and deterministic/provider/retrieval modules, stores no Portfolio input, and exposes no Session, mutation, administration, credential, deletion, or trade interface. Run it with `make mcp-stdio`; verify it with `backend/tests/test_mcp_adapter.py`.

`ai_finance_assistant.persistence` keeps SQLite as the loopback-development adapter and provides the
managed PostgreSQL application repository plus the official LangGraph PostgreSQL checkpointer. A
production web process uses `AIFA_STORAGE_MIGRATION_MODE=verify_only`; schema DDL is an explicit
operator action through `make managed-state-migrate`. Retention is an independent scheduled command
through `make managed-state-retention`, and `make managed-state-status` reports only non-secret
schema compatibility. The opt-in PostgreSQL integration test uses
`AIFA_TEST_POSTGRES_DSN`; `make managed-state-postgres-up` starts the disposable loopback fixture and
`make managed-state-postgres-check` runs that test. The fixture uses trust authentication only on
its loopback-bound qualification port, its data directory is a temporary filesystem, and the
profile is not a deployment topology or credential pattern. Ordinary CI
remains credential-free. Database DSNs and Qdrant keys are
never committed. A DSN that contains a password is a secret; the selected Cloud SQL operator jobs
instead construct a passwordless loopback DSN and use the Cloud SQL Auth Proxy's automatic IAM
authentication. Qdrant and provider keys remain secret values. Cloud Run does not natively inject
the approved regional Secret Manager versions, so the later browser-workload slice must qualify an
explicit regional-secret access path before using those keys.

The ordinary test suite loads the tracked, credential-free `backend/.test.env` and excludes tests marked `live_provider` and `live_model`; changes to `backend/.env` cannot alter those runs. With approved selected-market and Tavily credentials and terms flags in `backend/.env`, `make provider-live-check` explicitly opts into that file and enables two bounded smoke tests: at most three selected-market requests and one Tavily request. With an approved OpenAI key and terms flag, `make model-live-check` explicitly opts into `backend/.env`; an aggregate six-agent Run uses seven calls (one routing decision plus one response per specialist). Restart a running backend after changing an environment-selected adapter. For Massive, individual-plan data must remain owner-only unless Business/commercial display rights cover the demo audience.

See the repository [README](../README.md), [documentation index](../docs/README.md), [private-demo release bundle](../docs/release/README.md), and [M9 delivery report](../docs/M9_delivery_report.md).
