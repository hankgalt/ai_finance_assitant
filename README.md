# AI Finance Assistant

AI Finance Assistant is a U.S.-focused financial education and analysis product. The repository has completed **M6: React product experiences**. It has versioned Finance and Tax knowledge collections, safe portfolio import/calculation modules, deterministic goal projections, provider ports/adapters, a bounded six-agent LangGraph workflow, a qualified OpenAI model path, authoritative measured RunEvents, versioned REST/replayable SSE, durable private-demo storage, a historical provider cache, vendor-neutral operational telemetry, and responsive Assistant, Portfolio, Market, Goal, and Session History experiences. It does not yet provide the M7 execution Inspector, approved public-provider rights, public multi-user controls, or professional financial or tax advice.

The planned initial release is a production-oriented private demonstration release for the owner and approved viewers, not a public launch. Live provider demonstrations must remain within approved API terms and configured quotas; a separately selected credential-free mode remains reproducible and clearly labeled synthetic.

Read [docs/README.md](docs/README.md) before implementation work. Repository-wide engineering instructions are in [AGENTS.md](AGENTS.md). Milestone reports are indexed in the documentation directory; M5 backend behavior is recorded in [docs/M5_delivery_report.md](docs/M5_delivery_report.md), and the M6 product experiences and browser evidence are recorded in [docs/M6_delivery_report.md](docs/M6_delivery_report.md).

## Current capabilities

- FastAPI liveness/readiness and React application shell from M0.
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
- SQLite application schema v2, official durable LangGraph checkpoints, Active-to-Archived Session history, archive-before-permanent-deletion behavior, and a two-tier historical daily-bar cache with truthful memory/durable/provider/stale states.
- FastAPI and outbound HTTPX W3C instrumentation, bounded backend/provider/retrieval/cache/persistence metrics, structured correlation logs, and optional loopback OTLP Collector transport.
- Responsive React Assistant, Portfolio, Market, Goal, and Session History experiences with accessible states, backend-authoritative calculations, archive/history/permanent deletion, and privacy-safe browser telemetry.

MCP and the Inspector UI belong to later milestones. Live providers are not enabled until the account-specific rights gate passes.

M4.1 adds a conditional OpenAI `gpt-6.1-sol` ModelAdapter while retaining the deterministic credential-free default. M5 integrates it through the durable application boundary without changing deterministic authority or credential-free CI. M6 consumes that boundary in the React application. M7 is the next permitted milestone.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose v2
- Node.js 22 or newer
- pnpm 11

Dependencies are local to `backend/.venv` and `frontend/node_modules`. Qdrant data is held in the Compose-managed `qdrant-storage` volume.

## Install and configure

~~~bash
make backend-sync
make frontend-install
cp .env.example backend/.env
~~~

The generated lockfiles are the reproducibility authority. The example configuration enables only the loopback Qdrant service and requires no credentials.

## Run locally

~~~bash
make qdrant-up
make backend-dev
~~~

In another terminal:

~~~bash
make frontend-dev
~~~

Open http://127.0.0.1:5173. Vite proxies `/api` to the backend at http://127.0.0.1:8000.

Health interfaces:

- `GET /api/health` — aggregate service status.
- `GET /api/health/live` — process liveness.
- `GET /api/health/ready` — HTTP 200 only when both active Qdrant collections match the expected M1 contract; otherwise HTTP 503.

Application startup and health checks never fetch sources, download models, create collections, or generate embeddings.

## Offline knowledge maintenance

These commands intentionally run outside application startup. They fetch only enabled, approved registry entries, build an immutable candidate, evaluate it, and activate it only after the gate passes:

~~~bash
make knowledge-finance
make knowledge-tax
make knowledge-validate
~~~

Raw source responses are cached under ignored `backend/.cache/knowledge-sources/`. Use the CLI `--refresh-sources` option only for a deliberate source refresh. Manifests and evaluation evidence are written under `backend/artifacts/m1/`.

Stop Qdrant without deleting its volume:

~~~bash
make qdrant-stop
~~~

## Verify

~~~bash
make verify
make qdrant-check
make knowledge-validate
~~~

`make verify` loads the tracked `backend/.test.env`, is credential-free, ignores the developer's `backend/.env`, and skips the live-Qdrant integration test. `make qdrant-check` explicitly exercises candidate creation, compatibility validation, atomic activation, rollback, and cleanup against the loopback service.

M2 calculation and import contracts are exercised by the ordinary backend test suite. The versioned numerical policy is [docs/M2_calculation_policy.md](docs/M2_calculation_policy.md), and valid/adversarial samples are indexed by `backend/data/finance/sample_manifest.v1.json`.

M3 provider contracts and failure behavior are exercised by `make m3-check`. Credential-free mode is the default. Live mode requires both keys, documented entitlements, and a predeclared request budget; missing readiness never silently falls back within a Run.

M4 schema-constrained model routing, all six agent contracts, checkpoint behavior, failure bounds, RunEvents, redaction, OpenTelemetry correlation, optional LangSmith privacy defaults, and exporter-failure isolation are exercised by `make m4-check`. OpenTelemetry is enabled locally without a network exporter by default; `AIFA_OBSERVABILITY_MODE=disabled|in_memory|opentelemetry` controls the runtime adapter. LangSmith remains off unless explicitly configured.

M4.1 structured-output, routing, failure, retry, request-budget, concurrency, privacy, and configuration contracts are exercised credential-free by `make m4-1-check`. Live mode requires `OPENAI_API_KEY` (or `AIFA_OPENAI_API_KEY`) and `AIFA_OPENAI_TERMS_APPROVED=true`; `make model-live-check` makes one routing request plus one request for each selected agent, with a seven-call ceiling for the aggregate six-agent case. Current LangSmith variables (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`) and their legacy `LANGCHAIN_*` aliases are accepted, but inputs and outputs remain hidden and RunEvents stay authoritative.

M5 REST/SSE contracts, isolation, idempotency, restart/deletion/retention, migrations, cache reuse and rights gates, W3C propagation, metric cardinality, and readiness behavior are exercised by `make m5-check`. `make observability-up` starts the optional loopback OTLP Collector debug sink; network export remains disabled until `AIFA_OTEL_EXPORT_ENABLED=true` is deliberately configured.

M6 product workflows, Active Session archiving, archived history and permanent deletion, browser contract mocks, accessibility states, responsive layouts, and browser telemetry are exercised by `make m6-check`.

Synthetic JSON, CSV, and XLSX files for exercising portfolio validation and dashboard analysis are available in [examples/portfolios](examples/portfolios/README.md). Each file includes explicit synthetic user prices, so the dashboard can be verified without live market-provider calls.

Set `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive` before a live workflow. After the selected market provider and Tavily credentials, terms flags, and entitlement descriptions are configured in `backend/.env`, run `make provider-live-check` for the explicitly marked, quota-bounded live smoke tests. Selection is explicit per workflow; quota failure never silently switches providers. Massive individual-plan data is owner-only, so a demo shown to viewers or testers requires separately approved Business/commercial rights. Ordinary `pytest`, `make backend-check`, `make verify`, and `make m3-check` runs exclude the `live_provider` marker and make no live-provider calls.

## Local security posture

The development services bind to `127.0.0.1`. Local Qdrant has no authentication and is not a production deployment. Do not expose it publicly. Only reviewed public educational sources are enabled, raw source caches are ignored, and M2/M3 use versioned synthetic financial/provider fixtures rather than real user data. Logs continue to exclude request bodies, query values, credentials, raw prompts, holdings, and transaction payloads.
