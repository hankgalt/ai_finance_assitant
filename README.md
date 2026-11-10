# AI Finance Assistant

AI Finance Assistant is a U.S.-focused financial education and analysis product. It has:
- Versioned Finance and Tax knowledge collections, 
- Safe Portfolio import/calculation modules, 
- Deterministic Goal projections, 
- Provider ports/adapters, 
- A bounded six-agent LangGraph workflow, 
- A qualified OpenAI model path, 
- Authoritative measured RunEvents,
- Versioned REST/replayable SSE,
- Durable private-demo storage,
- Historical and public-RAG caches,
- Vendor-neutral operational telemetry,
- Responsive product/Inspector experiences, and
- A four-tool read-only MCP stdio adapter. 

It does not yet provide approved public-provider rights, private multi-user deployment controls,
professional financial or tax advice, or M10 cash-flow import. M11 documents but has not implemented
the IAP-protected GCP deployment.

The planned initial release is a production-oriented private demonstration release for the owner and approved viewers, not a public launch. Live provider demonstrations must remain within approved API terms and configured quotas; a separately selected credential-free mode remains reproducible and clearly labeled synthetic.

Read [docs/release/developer-guide.md](docs/release/developer-guide.md), [docs/release/user-guide.md](docs/release/user-guide.md) & [docs/release/README.md](docs/release/README.md). See [docs/release/demo-script.md](docs/release/demo-script.md) to go over functionality demo.

## Grading rubric map

Where to find each graded criterion. The [demo script](docs/release/demo-script.md) walks through
them in order, and the [coursework evidence matrix](docs/evidence/m9/coursework-evidence-matrix.md)
has the full mapping.

| Rubric criterion | What is implemented | Where to see it |
|---|---|---|
| Multi-agent architecture | Six specialist agents: Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, Tax Education. They share one typed result contract and collaborate only through the graph. | [specialists.py](backend/src/ai_finance_assistant/agents/specialists.py), [test_agents.py](backend/tests/test_agents.py) |
| LangGraph workflow | LangGraph `StateGraph` with model-based routing, a context gate, conditional fan-out, multi-agent synthesis, durable SQLite checkpoints and follow-up turns | [graph.py](backend/src/ai_finance_assistant/workflow/graph.py), [test_workflow.py](backend/tests/test_workflow.py) |
| RAG implementation | Persistent Qdrant Finance and Tax collections combining keyword and semantic search (BM25 + BGE, merged with RRF), filtered by tax year and jurisdiction, with citations. Retrieval is scored against fixed test questions before activation (hybrid recall@5 = 1.0 for both). | [knowledge/](backend/src/ai_finance_assistant/knowledge), [evaluation reports](backend/artifacts/knowledge) |
| Real-time data integration | Alpha Vantage or Massive market data and Tavily news behind provider adapters, with retries, circuit breaker, request budget, durable history cache, and explicit stale/unavailable states. Live mode is selected by environment; a labelled synthetic mode works without credentials. | [providers/](backend/src/ai_finance_assistant/providers), [M3 provider policy](docs/M3_provider_policy.md) |
| MCP server | Read-only stdio MCP server with four tools: `search_education`, `get_market_quote`, `analyze_portfolio`, `project_goal` | `make mcp-stdio`, [MCP client record](docs/evidence/m9/mcp-client-record.md) |
| Web interface | React + TypeScript app (used instead of Streamlit; see [ADR-007](docs/02_architecture_decision_records.md)) with Assistant, Portfolio, Market, Goals, History and Inspector views. Responsive, with accessible states. | [screenshots](docs/evidence/m6), [user guide](docs/release/user-guide.md) |
| Conversational flow | Session-scoped conversation with durable checkpoints, follow-ups that reuse the selected portfolio, clarification prompts, replayable SSE streaming, archived session history | Assistant view, [test_workflow_application.py](backend/tests/test_workflow_application.py) |
| Data visualization | Allocation donut, unrealized gain/loss bars, market price line, and goal scenario bars (Recharts), each with an accessible table. The Agent Execution Inspector graph (React Flow) is built from measured run events. | Portfolio, Market, Goals and Inspector views, [Inspector screenshots](docs/evidence/m7) |
| Educational content | 49 approved, rights-reviewed sources split into 6,401 cited chunks: 18 Investor.gov/SEC finance articles and 31 IRS publications and form instructions. 18 more sources are pending review. | [source registry](backend/data/knowledge/source-registry.v1.json), [source license register](docs/release/source-license-register.md) |
| Portfolio analysis | Deterministic Decimal calculations: valuation, allocation, asset-class and sector concentration, weighted expense ratio, HHI and effective-holdings diversification, top-5 concentration, cost-basis unrealized gain/loss, return on cost, holding period and annualized return. All with coverage reporting. | [calculation policy](docs/M2_calculation_policy.md), [portfolio_analysis.py](backend/src/ai_finance_assistant/finance/portfolio_analysis.py), [sample portfolios](examples/portfolios) |
| Market intelligence | Quotes and daily history with provenance and freshness; deterministic period change, percent change, high and low for the Market Analysis agent to interpret; dated, attributed news synthesis | Market view, Assistant market/news questions |
| Code organization | Modules organized by capability with ports and adapters; strict mypy, ruff, ESLint and Prettier | [repository layout](docs/repository_layout.md) |
| Documentation | Requirements, 30 architecture decision records, system design with Mermaid diagrams, implementation plan, user/developer/operator guides, per-milestone delivery reports | [docs/README.md](docs/README.md) |
| Testing | Backend: 338 tests, 91.55% coverage. Frontend: 71 Vitest tests, 93.85% lines / 92.98% statements (branches 78.53%), plus 10 Playwright journeys. Release qualification covers 18 dimensions. | `make verify`, [coverage report](docs/evidence/m8/coverage.md) |
| Innovation (bonus) | Agent Execution Inspector from measured run events, an evidence-bound semantic response cache (Redis), OpenTelemetry tracing across browser and backend, a threat model with prompt-injection controls, and planned M10 cash-flow import and M11 IAP-protected GCP deployment | [M7](docs/M7_delivery_report.md), [M6.1](docs/M6_1_delivery_report.md), [M8](docs/M8_delivery_report.md) reports, [implementation plan](docs/04_implementation_plan.md) |

## Current capabilities

- FastAPI liveness/readiness and React application shell.
- Reviewed SourceRegistry with permitted-use, status, provenance, and tax-year fields.
- Explicit offline HTML/PDF ingestion with integrity-checked source caching, deterministic normalization/chunking, source/content hashing, and resumable batched writes.
- Persistent Qdrant 1.20.0 collections with named dense and sparse vectors, filter indexes, immutable manifests, atomic active aliases, and rollback.
- Locally generated BGE-small dense and Qdrant BM25 sparse representations with exact model revisions and artifact hashes.
- Dense, sparse, and hybrid/RRF evaluation against fixed Finance and Tax qrels.
- Runtime readiness that validates active aliases, schema, vector configuration, model artifacts, payload indexes, ready state, and nonempty collections without fetching or embedding.
- One safe PortfolioImport interface for manual, JSON, CSV, and XLSX input, with aggregate diagnostics, duplicate rejection, source hashing, bounded parsing, and formula/macro defenses.
- Immutable imported Portfolio/Account/Holding records kept separate from fake/provider enrichment records and calculated Portfolio Snapshots.
- Decimal-based valuation, per-currency allocation, expense/classification coverage, concentration, and a versioned HHI/effective-holdings heuristic.
- Multi-scenario goal projections with explicit contribution timing/frequency, inflation, modeled fees, risk-tolerance context, and nominal/real decomposition.
- A types-only CashFlowAnalysisService seam and minimized CashFlowSummary; provider-independent JSON/CSV cash-flow import and analysis are planned for post-release M10.
- MarketDataProvider and NewsProvider ports with normalized provenance, freshness, cache, entitlement, warning, and typed-error states.
- Deterministic credential-free market/news adapters and hand-authored synthetic fixtures for CI and private demonstrations.
- Conditional Alpha Vantage or Massive end-of-day/daily-market adapters plus Tavily attributed-news behind explicit selection, readiness, quota, retry, circuit, and bounded-cache controls.
- Exactly six specialist agents behind a typed, bounded LangGraph router/synthesis workflow, with no recursive agent calls and separate Market Analysis and Goal Planning authorities.
- Finance and Tax citation grounding, deterministic Portfolio/Goal delegation, attributed News, and provider-backed Market behavior through stable application ports.
- Privacy-filtered RunEvents plus in-memory and OpenTelemetry span/metric adapters with stable trace correlation and optional input/output-hidden LangSmith tracing.
- Versioned `/api/v1` Session, Run, Portfolio, Snapshot, market, goal, and authorized trace resources with typed safe failures and artifact idempotency.
- Replayable SSE for persisted RunEvents and terminal response chunks with `Last-Event-ID` recovery.
- SQLite application schema v3, official durable LangGraph checkpoints, Active-to-Archived Session history, archive-before-permanent-deletion behavior, and a two-tier historical daily-bar cache with truthful memory/durable/provider/stale states.
- FastAPI and outbound HTTPX W3C instrumentation, bounded backend/provider/retrieval/cache/persistence metrics, structured correlation logs, and optional loopback OTLP Collector transport.
- Responsive React Assistant, Portfolio, Market, Goal, and Session History experiences with accessible states, backend-authoritative calculations, archive/history/permanent deletion, and privacy-safe browser telemetry.
- Measured React Flow Inspector, qualified Finance/Tax Redis semantic cache, and read-only MCP stdio tools for education retrieval, quote lookup, in-memory Portfolio analysis, and Goal projection.
- Full release qualification plus user/developer/operator, coursework, clean-start, coverage, and eight-minute credential-free demonstration evidence.

Live providers are not enabled until the account-specific rights gate passes. The independently
planned post-release tracks are M10 provider-independent bank/card cash-flow import and M11
IAP-protected GCP private multi-user deployment; either may proceed first.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose v2
- Node.js 22 or newer
- pnpm 11

Dependencies are local to `backend/.venv` and `frontend/node_modules`. Qdrant data is held in the Compose-managed `qdrant-storage` volume.

## Install and configure

### 1. Install dependencies
~~~bash
make backend-sync
make frontend-install
~~~

### 2. Create local configuration
~~~bash
cp .env.example backend/.env
docker compose config --quiet
~~~

The generated lockfiles are the reproducibility authority. The example configuration enables only the loopback Qdrant service and requires no credentials.

## Run locally

### 3. Start local infrastructure
~~~bash
make qdrant-up
make response-cache-up
~~~

### 4. Build, evaluate, and activate both RAG collections
~~~bash
make knowledge-finance
make knowledge-tax
~~~

### 5. Validate the active aliases
~~~bash
make knowledge-validate
~~~

The ingestion commands:
- Fetch only enabled and approved sources from the source registry.
- Download the pinned BGE-small and BM25 model artifacts if absent.
- Normalize and chunk Finance and Tax content.
- Generate dense and sparse representations.
- Write immutable Qdrant collections.
- Evaluate retrieval against the tracked cases.
- Activate each collection only if its evaluation passes.

On the existing release state, the expected collections are:
- Finance: 18 documents, 106 chunks
- Tax: 31 documents, 6,295 chunks

Raw source responses are cached under ignored `backend/.cache/knowledge-sources/`. Use the CLI `--refresh-sources` option only for a deliberate source refresh. Manifests and evaluation evidence are written under `backend/artifacts/knowledge/`.

### 6. Start the application in separate terminals:
~~~bash
make backend-dev
make frontend-dev
~~~

### 7. Verify readiness:
~~~bash
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
~~~

Open http://127.0.0.1:5174/finance_assistant/. Vite proxies `/api` to the backend at http://127.0.0.1:8000.

Health interfaces:

- `GET /api/health` — aggregate service status.
- `GET /api/health/live` — process liveness.
- `GET /api/health/ready` — HTTP 200 only when both active Qdrant collections match the expected knowledge contract; otherwise HTTP 503.

Application startup and health checks never fetch sources, download models, create collections, or generate embeddings.

Stop Qdrant without deleting its volume:

~~~bash
make qdrant-stop
~~~

## Verify

~~~bash
make verify
make qdrant-check
make knowledge-validate
make release-check
~~~

`make verify` loads the tracked `backend/.test.env`, is credential-free, ignores the developer's `backend/.env`, and skips the live-Qdrant integration test. `make qdrant-check` explicitly exercises candidate creation, compatibility validation, atomic activation, rollback, and cleanup against the loopback service.

Calculation and import contracts are exercised by `make calculations-check`. The versioned numerical policy is [docs/M2_calculation_policy.md](docs/M2_calculation_policy.md), and valid/adversarial samples are indexed by `backend/data/calculations/fixture-manifest.v1.json`.

Provider contracts and failure behavior are exercised by `make providers-check`. Credential-free mode is the default. Live mode requires both keys, documented entitlements, and a predeclared request budget; missing readiness never silently falls back within a Run.

Schema-constrained model routing, all six agent contracts, checkpoint behavior, failure bounds, RunEvents, redaction, OpenTelemetry correlation, optional LangSmith privacy defaults, and exporter-failure isolation are exercised by `make assistant-check`. OpenTelemetry is enabled locally without a network exporter by default; `AIFA_OBSERVABILITY_MODE=disabled|in_memory|opentelemetry` controls the runtime adapter. LangSmith remains off unless explicitly configured.

Structured-output, routing, failure, retry, request-budget, concurrency, privacy, and configuration contracts are exercised credential-free by `make model-check`. Live mode requires `OPENAI_API_KEY` (or `AIFA_OPENAI_API_KEY`) and `AIFA_OPENAI_TERMS_APPROVED=true`; `make model-live-check` makes one routing request plus one request for each selected agent, with a seven-call ceiling for the aggregate six-agent case. Current LangSmith variables (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`) and their legacy `LANGCHAIN_*` aliases are accepted, but inputs and outputs remain hidden and RunEvents stay authoritative.

REST/SSE contracts, isolation, idempotency, restart/deletion/retention, migrations, cache reuse and rights gates, W3C propagation, metric cardinality, and readiness behavior are exercised by `make api-check`. `make observability-up` starts the optional loopback OTLP Collector debug sink; network export remains disabled until `AIFA_OTEL_EXPORT_ENABLED=true` is deliberately configured.

Product workflows, Active Session archiving, archived history and permanent deletion, browser contract mocks, accessibility states, responsive layouts, and browser telemetry are exercised by `make product-ui-check`.

Inspector fidelity is exercised by `make inspector-check`. Response-cache behavior is exercised by `make response-cache-check` and the calibration/benchmark targets. Full EVAL-01–EVAL-18 qualification is exercised by `make qualification-check`. `make release-check` adds measured frontend coverage, regenerates the full qualification, invokes the MCP protocol/client and release-path audits, and validates Compose configuration. The release guide records exact scope, modes, budgets, rollback, observability, and limitations. Historical milestone target names remain compatibility aliases.

Synthetic JSON, CSV, and XLSX files for exercising portfolio validation and dashboard analysis are available in [examples/portfolios](examples/portfolios/README.md). Each file includes explicit synthetic user prices, so the dashboard can be verified without live market-provider calls.

Set `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive` before a live workflow. After the selected market provider and Tavily credentials, terms flags, and entitlement descriptions are configured in `backend/.env`, run `make provider-live-check` for the explicitly marked, quota-bounded live smoke tests. Selection is explicit per workflow; quota failure never silently switches providers. Massive individual-plan data is owner-only, so a demo shown to viewers or testers requires separately approved Business/commercial rights. Ordinary `pytest`, `make backend-check`, `make verify`, and `make m3-check` runs exclude the `live_provider` marker and make no live-provider calls.

## Local security posture

The development services bind to `127.0.0.1`. Local Qdrant has no authentication and is not a production deployment. Do not expose it publicly. Only reviewed public educational sources are enabled, raw source caches are ignored, and M2/M3 use versioned synthetic financial/provider fixtures rather than real user data. Logs continue to exclude request bodies, query values, credentials, raw prompts, holdings, and transaction payloads.
