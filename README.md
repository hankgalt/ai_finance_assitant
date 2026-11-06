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

Open http://127.0.0.1:5173. Vite proxies `/api` to the backend at http://127.0.0.1:8000.

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
