# AI Finance Assistant — System design

Version 1.0 | Status: Product architecture baseline | 2026-10-26

## 1. Architecture principles

- Keep the web client behind a versioned FastAPI interface; business rules do not run in the browser.
- Use LangGraph to route and coordinate exactly six specialist agents.
- Put financial calculations, import validation, retrieval, and provider behavior in deep modules with small typed interfaces. Agents interpret results; they do not own arithmetic or persistence.
- Treat external content and uploaded files as untrusted data.
- Keep imported user data, provider enrichment, and calculated outputs separate and traceable.
- Build and evaluate knowledge collections offline; runtime connects to an activated persistent Qdrant collection.
- Emit measured execution events as work happens; never reconstruct a trace from the final answer.
- Make local-demo and production security postures explicit.

## 2. Runtime topology and orchestration

~~~mermaid
flowchart TD
  UI[React application] -->|versioned REST and SSE| API[FastAPI]
  API --> AUTH[Session and access checks]
  AUTH --> GRAPH[LangGraph workflow]
  GRAPH --> ROUTER[Router and safety policy]
  ROUTER --> QA[Finance Q&A]
  ROUTER --> PORT[Portfolio Analysis]
  ROUTER --> MARKET[Market Analysis]
  ROUTER --> GOAL[Goal Planning]
  ROUTER --> NEWS[News Synthesizer]
  ROUTER --> TAX[Tax Education]

  QA --> RET[Retrieval module]
  TAX --> RET
  RET --> QD[(Persistent Qdrant)]

  PORT --> PM[Portfolio analysis module]
  PORT --> MDP[Market-data adapter]
  MARKET --> MDP
  GOAL --> GP[Goal projection module]
  NEWS --> NP[News-provider adapter]

  GRAPH --> CP[(Checkpoint store)]
  GRAPH --> EVENTS[Run-event recorder]
  EVENTS --> RS[(Run-event store)]
  RS -->|REST history and SSE| API

  INGEST[Offline ingestion and evaluation] --> CANDIDATE[(Candidate Qdrant collection)]
  CANDIDATE -->|validate and activate alias| QD

  MCP[Read-only MCP adapter] --> AUTH
  MCP --> RET
  MCP --> PM
  MCP --> GP
  MCP --> MDP
~~~

One Run follows: normalize and validate request → apply access and safety policy → classify intent → select one or more agents → execute independent agents concurrently where safe → synthesize structured results → validate citations, provenance, and safety → persist terminal state. Dependent work remains ordered; for example, a portfolio must be validated before enrichment and valued before a news question can be contextualized to its holdings.

Execution has maximum graph hops, per-tool timeouts, an overall deadline, and model/token budgets. An independent agent failure can yield a partial result with structured warnings. Missing required user input yields a clarification result, not guessed data.

## 3. Six-agent interfaces and interaction limits

All agents accept an AgentRequest containing Run, Session, Workflow, user-message, authorized context references, locale/jurisdiction, and deadline. All return AgentResult with agent identifier, status, summary, structured facts, evidence, visualization data where applicable, as-of fields, warnings, and typed errors.

| Agent | Domain input | Output | Allowed tools/modules | Dependencies | Failure behavior | Interaction boundary |
|---|---|---|---|---|---|---|
| Finance Q&A | Educational question, declared experience level, conversation context | Grounded explanation, definitions, examples, risks, citations, uncertainty | Finance Education retrieval and grounded-response adapter | Active Finance KB, LLM adapter | No relevant evidence → say evidence is insufficient; incompatible collection → unavailable | Does not value portfolios, project goals, interpret personal taxes, or issue buy/sell instructions |
| Portfolio Analysis | Authorized Portfolio identifier or validated import; analysis options; valuation time | Portfolio Snapshot, allocation/concentration/expense results, coverage, provenance, warnings, explanation | Portfolio import/validation, security enrichment, MarketDataProvider, deterministic portfolio analysis | Portfolio data, provider adapter/cache, calculation policy | Invalid rows → validation report; missing prices or classifications → partial coverage; provider outage → stale-labeled or unavailable values | Does not invent data, predict returns, make suitability decisions, or overwrite imports |
| Market Analysis | Security identifiers, date range, requested statistics | Current/historical observations, descriptive statistics, provenance, freshness, limitations | MarketDataProvider and deterministic time-series statistics | Provider adapter/cache | Rate limit/timeout → bounded retry then stale cache or unavailable; invalid symbol → typed error | Describes history and context; does not turn performance into a guaranteed forecast or own goal assumptions |
| Goal Planning | Goal amount/date, starting resources, contribution schedule, inflation/return scenarios, declared risk tolerance; optional authorized summaries | Deterministic scenarios, contributions/growth decomposition, shortfall/surplus, assumptions, warnings | Goal projection module; read-only Portfolio Snapshot and future CashFlowSummary access | Calculation policy and authorized summaries | Missing fields → clarification; invalid horizon/rate → validation error; incomplete summary → labeled partial scenario | Remains separate from Market Analysis; market history may inform education but does not silently set future-return assumptions |
| News Synthesizer | Topic, security identifiers, time window, optional authorized portfolio summary | Dated attributed story summaries, fact/interpretation labels, relevance, limitations | NewsProvider; optional Market Analysis result supplied through graph | News provider and LLM adapter | No recent stories → explicit empty state; provider failure → unavailable; conflicting reports → preserve attribution | Does not treat news as price prediction, retrieve unapproved sources, or expose portfolio records to the provider |
| Tax Education | U.S. federal tax-education question, requested tax year, account/investment concept, jurisdiction | Educational explanation, applicable year/jurisdiction, authoritative citations, caveats | Tax Education retrieval and grounded-response adapter | Active Tax KB and LLM adapter | Ambiguous year → clarify or label assumed current year; no authoritative evidence → abstain; unsupported jurisdiction → out-of-scope | Does not calculate an individual return, make elections, provide legal advice, or silently apply current law to historical years |

Multi-domain requests are decomposed by the router. Agents never call one another recursively; the graph supplies another agent’s structured result when composition is required. Goal Planning and Market Analysis always remain separate nodes and authorities.

## 4. Core modules and seams

| Module | Interface responsibility | Adapters or implementation notes |
|---|---|---|
| PortfolioImport | Parse manual/JSON/CSV/XLSX input and return imported records plus all safe validation findings | Format parsers remain internal; tests exercise the common interface |
| SecurityEnrichment | Resolve allowed identifiers and return provenance-bearing reference fields without mutating input | External reference providers and deterministic fakes |
| PortfolioAnalysis | Convert imported records, enrichment, and a consistent quote set into a Portfolio Snapshot | Pure deterministic implementation |
| GoalProjection | Produce inflation-aware, recurring-contribution scenarios and decompositions | Pure deterministic implementation |
| KnowledgeRetrieval | Search one logical KB with filters and an explicit retrieval strategy; return ranked Evidence or no-evidence | Qdrant adapter and in-test adapter |
| MarketDataProvider | Return standardized Quote and historical series results with freshness/error state | One or more external adapters plus fakes |
| NewsProvider | Return attributed NewsItems for a query/time range | External adapter plus fake |
| CheckpointRepository | Load and save workflow state by authorized Session and Workflow version | In-memory test adapter and durable runtime adapter |
| RunEventRepository | Append ordered events and read authorized run history/replay | In-memory fixture adapter and durable adapter where restart replay is required |
| LLM | Return schema-validated model output and measured usage metadata when provided | Configured provider adapter plus deterministic fake |

Ports exist only at seams that genuinely vary, normally production and test adapters. Internal helpers are not exposed just to make tests easier; observable behavior is tested through each module’s interface.

## 5. Portfolio model and data flow

### 5.1 Imported records

Portfolio:

- portfolio_id, label, base_currency, imported_at, source_kind, source_file_hash;
- Accounts.

Account:

- account_id, portfolio_id, account_type, optional institution_label;
- Holdings.

Holding:

- holding_id, account_id, source_row, identifier_type/value;
- quantity, currency;
- optional asset_class, cost_basis_amount, cost_basis_basis, acquisition_date/lots;
- optional user_price, user_price_as_of, user_price_provenance;
- optional expense_ratio and sector;
- explicit missing fields and accepted warnings.

Imported records preserve raw field values needed for diagnostics, but unsafe formulas or executable content are neutralized. A source-file hash supports duplicate detection without becoming a permanent copy of the upload.

### 5.2 Provider-enriched records

SecurityReference contains holding_id, canonical identifiers, display name, verified asset class/sector, trading currency, expense ratio, field-level provider provenance, retrieved_at, and conflict flags. Quote contains identifier, price, currency, market_as_of, retrieved_at, provider, delay status, stale status, and cache status.

Enrichment is additive. Conflicts with imported fields become warnings with both sources retained.

### 5.3 Calculated records

PortfolioSnapshot contains snapshot_id, portfolio_id, calculated_at, calculation_policy_version, quote-set identifier, per-holding values, total by currency/base currency when supported, allocations, classification concentrations, expense metrics and covered allocation, diversification heuristic/version, valuation coverage, and warnings.

The flow is:

~~~text
uploaded bytes → safe parser → imported records + validation report
imported records → enrichment adapters → security references + quotes
imported records + enrichment + one quote set → deterministic analysis → Portfolio Snapshot
Portfolio Snapshot → agent explanation and UI charts
~~~

Original uploaded files are deleted after parsing under the configured local retention mode unless the user explicitly chooses a supported retained-artifact mode. Deleting a Portfolio also deletes its imported records, enrichment, and snapshots according to the retention policy.

## 6. Deterministic financial calculations

Portfolio value for holding i is quantity_i × price_i using a single identified quote set. Total and allocation exclude holdings without usable prices and report both priced and unpriced coverage. Mixed currencies require explicit conversion provenance; otherwise totals remain partitioned by currency. Weighted expense ratios always report the percentage of portfolio value with a known ratio. Asset and sector concentration are calculated only over classified coverage. A diversification value is a transparent versioned heuristic, never an objective or personalized risk rating.

GoalProjection accepts starting amount, contribution amount/frequency/timing, horizon, nominal return assumption, inflation assumption, fees when modeled, and scenario labels. It special-cases zero return, documents compounding and rounding, and returns nominal value, inflation-adjusted value, total contributions, modeled growth, and shortfall/surplus. Scenarios are user-controlled illustrations, not predictions. Declared risk tolerance is explanatory context and cannot authorize a suitability recommendation.

Use Decimal or another approved explicit precision policy for monetary operations. Golden examples, properties, and metamorphic relations validate the interface; an LLM output is never an arithmetic oracle.

## 7. Offline knowledge ingestion and activation

The ingestion application is a separate administrative workflow:

1. **Discover and register sources.** Add a SourceRegistry entry with authority, URL, use/redistribution notes, logical KB, review cadence, jurisdiction, and effective/tax years.
2. **Fetch documents.** Retrieve only approved content and record response metadata, source version, and raw content hash.
3. **Extract and normalize.** Convert permitted content to normalized text while preserving headings, tables where meaningful, document identifiers, and source anchors.
4. **Validate.** Check required provenance, readable content, supported jurisdiction/year, use policy, extraction quality, and quarantine/error state.
5. **Detect duplicates and changes.** Compare canonical source identifiers and hashes; skip unchanged content idempotently, relate duplicates, and create a new document version for changes.
6. **Chunk by document structure.** Preserve section paths, page/anchor references, effective dates, tax years, and sufficient standalone context.
7. **Generate representations.** Create version-identified dense vectors and sparse representations where the collection policy requires them.
8. **Persist to Qdrant.** Write candidate collection points with stable chunk IDs and payload schema; never write directly over the active version.
9. **Evaluate retrieval.** Run schema checks and the fixed logical-KB test set, compare against the active baseline, inspect failures, and record metrics/configuration.
10. **Activate a validated version.** Atomically move the logical active alias after approval. Keep the prior collection for a bounded rollback period.

Each point payload includes logical_kb, collection_version, document_id, document_version, chunk_id, title, publisher, canonical_url, source_type, section_path, effective dates, tax_year, jurisdiction, content_hash, fetched_at, reviewed_at, permitted_use, and status. Model identifiers and payload schema version belong to collection metadata and the ingestion manifest.

Application readiness checks both Finance and Tax active aliases, required named vectors/sparse fields, payload schema, model versions, and a collection-ready marker. Failure produces a specific not-ready health result. Runtime never fetches the corpus or embeds content during startup.

## 8. Retrieval and knowledge lifecycle

KnowledgeRetrieval accepts logical KB, query, filters, top_k, relevance policy, and strategy:

- dense semantic search for conceptual queries;
- sparse lexical search for exact terms, form numbers, or identifiers;
- dense/sparse search fused with Reciprocal Rank Fusion for query classes shown to benefit;
- metadata filters for source, category, date, document version, status, and, for Tax, tax year and jurisdiction.

The module returns ranked Evidence with score type, rank, stable source identifiers, source anchor, collection/model versions, and attribution fields. Results below the calibrated relevance policy are discarded. Agents receive bounded excerpts and metadata; a citation validator confirms that cited evidence came from the Run.

Maintenance separates checks from indexing:

| Content | Source-change check | Human review | Re-index trigger |
|---|---|---|---|
| Financial fundamentals | Quarterly | Quarterly or on material change | Validated content hash changed |
| Investment products/regulatory guidance | Monthly | On material change | Validated content hash changed |
| Tax publications/guidance | Monthly and event-driven | On new/revised guidance | New document/tax year or changed hash |
| Representation models | On planned model change | Comparative retrieval review | Always build a new collection version |

Historical Tax collection content remains queryable by year. Superseded guidance is marked, not destroyed, unless use rights require removal.

## 9. External providers and failure behavior

Provider results use a common envelope: status, provider, requested identifier/query, data, market/published timestamp, retrieved_at, delay, cache age/hit, license/entitlement label when needed, warnings, and typed error.

The provider policy defines rate limits, concurrency, timeout, retry eligibility, exponential backoff with jitter, circuit state, and cache TTL by endpoint. Authentication and invalid requests are not retried as transient failures. On timeout, quota, or outage, the module may return a valid cached result only with its original timestamp and stale state; otherwise it returns unavailable. Demo fixtures and fallback providers are always labeled.

News preserves publisher and publication time and distinguishes source text from generated interpretation. Market statistics are computed from returned structured series rather than model guesses.

M3 implements the application ports with deterministic credential-free adapters, conditional Alpha Vantage and Massive market adapters, and a conditional Tavily news adapter under ADR-024/025. `AIFA_PROVIDER_MODE` selects one bundle and `AIFA_MARKET_DATA_PROVIDER` selects one live market adapter before workflow execution. Each bundle uses one mode and one market adapter; missing credentials, insufficient budget, quota failure, or failed readiness returns an explicit unavailable state and never switches a running workflow to fake data or another live provider. The initial bounded in-memory cache is scoped to the provider process/workflow and is not a durable user record. M5 may add an approved durable cache adapter only under the same provenance and provider-rights rules.

Alpha Vantage quote currency is caller-supplied because the selected quote/daily endpoints do not return a currency. Massive uses the previous-day and raw daily-aggregate endpoints; its quote currency is likewise caller-supplied, and Basic data remains end-of-day with a rolling history window. Neither adapter presents these responses as realtime. Massive individual-plan data is owner-only and cannot be shown to testers or viewers without approved Business/commercial rights. Tavily is a discovery provider, not a publisher: the adapter disables generated answers and raw content, preserves the source URL/host, and labels `published_date` as provider-estimated or unavailable. Only a bounded public query may leave the backend; holdings, transactions, credentials, and user-specific financial context are prohibited.

## 10. FastAPI and React interfaces

The React application contains:

- **Conversational Assistant:** streamed response, citations, uncertainty, follow-up continuity, and partial/failure states.
- **Portfolio Dashboard:** manual/file import, validation review, snapshot selector, provenance, allocations/concentrations/expenses, warnings, and accessible tables.
- **Market Overview:** security search, timestamped current/historical data, descriptive statistics, and stale/unavailable states.
- **Goal Planning:** inputs, assumptions, deterministic scenario curves, contribution/growth decomposition, and accessible table.
- **Agent Execution Inspector:** authorized Run selector, event timeline, React Flow graph, details, sources, and measurement availability.

TanStack Query owns remote server state; frontend state is limited to interaction and view preferences. Recharts visualizations always have text/table equivalents. The browser never receives provider credentials or performs authoritative calculations.

Versioned interface groups:

- health/readiness and configuration capabilities;
- Sessions and deletion;
- chat Runs, final results, event history, and SSE;
- portfolio import/validation, Portfolios, and Snapshots;
- market query;
- goal projection;
- authorized trace retrieval.

REST returns authoritative resources and terminal Run status. SSE carries typed conversation chunks and RunEvents. A client reconnects with the last event identifier when replay is supported; otherwise it reloads authorized event history and final state over REST. OpenAPI is the contract source and generated or contract-tested TypeScript types prevent drift.

## 11. Agent Execution Inspector contract

RunEvent schema version 1 contains:

| Field group | Required content |
|---|---|
| Identity | schema_version, event_id, execution_id, trace_id, session_id, workflow_id, workflow_version, sequence |
| Subject | node_id; optional agent_id, tool_call_id, tool_name, parent_event_id |
| Lifecycle | event_type, status, started_at, completed_at when observed, duration_ms when measured |
| Routing | selected agent/node identifiers, decision outcome, sanitized reason category; never hidden chain-of-thought |
| Tool result | safe result status, provider, record counts, cache/freshness metadata, sanitized error reference |
| Error | stable error_code, safe message, retryable flag, attempt count; no credential or sensitive payload |
| Usage | input/output/total tokens and monetary cost only when supplied or calculated by an identified method; availability and method fields |
| Retrieval | logical KB, collection/version, query strategy, source/chunk identifiers, ranks and score types; excerpts omitted by default |
| Presentation | short sanitized summary and safe_metadata constrained by an allow-list |

Event types include run started/completed/partial/failed, route selected, node started/completed/failed/skipped, tool started/completed/failed, retrieval started/completed/failed, model started/completed/failed, and response chunk. Status values are pending, running, completed, partial, failed, and skipped.

Sequence is monotonically increasing within execution_id; event_id is stable for deduplication. started_at and completed_at are timezone-aware. duration_ms is derived only when both observations use a suitable clock. Missing token, cost, duration, or trace data is represented as unavailable with a reason, not zero.

Instrumentation records events at LangGraph and module execution points. The event recorder redacts before persistence. The Inspector builds dynamic nodes and edges only from recorded identifiers and relationships. A static workflow-design overlay, if shown, is visually labeled as design rather than execution.

Staged delivery remains:

- M0: schema, redaction policy, and versioned synthetic fixtures;
- M4: actual LangGraph and module instrumentation;
- M7: timeline, details, and React Flow views;
- M8: fidelity, streaming, isolation, accessibility, and redaction evaluation.

## 12. Persistence, privacy, and security

Data classes and initial local policy:

| Data | Purpose | Initial persistence/retention requirement | Access and deletion |
|---|---|---|---|
| Uploaded file bytes | Parse portfolio | Ephemeral; delete after safe parse or failure | Parser only; cleanup tested |
| Imported Portfolio records | User analysis | Durable local store only when user saves; policy/version recorded | Owning Session/user context; delete cascades to derived user artifacts |
| Enrichment and Snapshots | Reproducible analysis | Bounded by Portfolio retention and provider terms | Same owner; deletable |
| Conversation checkpoints | Follow-up context | Durable local mode with documented retention | Owning Session; delete with Session |
| Run events/traces | Inspector and audit | Privacy-filtered and time-bounded | Owning Session; deletion supported |
| Knowledge sources/collections | Shared education evidence | Versioned according to source rights and rollback policy | Administrative ingestion role; user deletion does not remove shared sources |
| Provider cache | Reliability and rate control | Endpoint-specific bounded TTL and provider terms | Server only; never presented without provenance |

The local demo is unauthenticated only when explicitly configured and bound for local use. Opaque identifiers are not authentication. Every resource lookup and stream still checks Session scope to prevent accidental cross-session leakage. A public deployment requires the ADR-019 production controls before release.

Logs and traces use allow-listed fields, pseudonymous correlation identifiers, and field-level redaction. Raw prompts, raw portfolio rows, transactions, credentials, hidden reasoning, and unrestricted tool payloads are excluded. Secrets remain server-side. File parsing enforces content and resource limits and cannot execute formulas, macros, or embedded objects.

Health distinguishes liveness from readiness for Qdrant collections, storage migrations, and required provider configuration without exposing secrets. Writes use idempotency identifiers where duplicate requests could create artifacts. Failure taxonomy covers validation, authorization, not-ready, no-evidence, upstream unavailable/rate-limited, conflict, timeout, internal, and partial.

## 13. Planned CashFlowAnalysisService

CashFlowAnalysisService remains outside the initial end-user release but gets a stable conceptual interface:

Input:

- versioned provider-independent JSON or CSV import plus a Cash-flow import profile that maps source columns and date/amount/sign conventions to canonical rows;
- authorized import_id, account_id, source type (bank or credit card), schema/version, currency;
- transaction rows with date, posted date, description, amount/direction, optional merchant/category, and source-row identifier;
- optional user category overrides and reconciliation hints.

Output:

- normalized transactions with original-row references;
- categories with rule/model version, confidence, and override state;
- income/spending summaries by month/category;
- recurring-expense candidates and evidence;
- reconciled transfers and credit-card payments with matched identifiers;
- monthly surplus and trend series;
- coverage, unresolved duplicates/transfers, and warnings;
- CashFlowSummary safe for authorized Goal Planning consumption.

Normalization, categorization rules, recurrence detection, and reconciliation are deterministic or explicitly versioned analytical implementations. Transfer/card-payment pairs are excluded from spending totals exactly once. Raw transactions never enter general graph state; the graph receives a reference or minimized summary.

M10 implements the JSON/CSV path without requiring a financial-data provider. A future provider adapter may emit the same canonical rows, but live bank connections, automatic transactions, PDF statements, and a seventh LLM agent remain excluded. Adding any of them requires a new decision and security review.

## 14. Logical repository layout and deployment posture

~~~text
backend/
  api/                 FastAPI routes, access checks, REST/SSE adapters
  workflow/            LangGraph state, routing, graph, synthesis, instrumentation
  agents/              six agent modules
  portfolio/           import, validation, enrichment models, deterministic analysis
  planning/            deterministic goal projection; future cash-flow interface
  knowledge/           retrieval interface, Qdrant adapter, readiness
  providers/           market/news/LLM ports and adapters, cache policy
  persistence/         checkpoints, portfolios, run events
  safety/              validation, redaction, policy, errors
  evaluation/          fixtures, runners, reports
frontend/
  features/            chat, portfolio, market, goals, inspector
  shared/              generated contracts, accessible UI, query client
ingestion/
  registry/            governed source manifest
  pipeline/            fetch, extraction, validation, chunking, representations
  evaluation/          retrieval test set, activation and rollback records
knowledge/
  manifests/           versioned non-secret ingestion metadata
  fixtures/            permitted small test content
docs/
~~~

The layout is conceptual and can be refined without changing the interfaces. The initial development topology uses separate Vite, FastAPI, Qdrant, and ingestion commands/processes. The release target is a production-oriented private demonstration release, not a public deployment or claim of regulatory approval. Credential-free demo mode uses labeled deterministic adapters. Live-demo mode is separately selected, performs provider readiness and configured-budget checks, uses only approved credentials and entitlements, and never silently substitutes synthetic results. Public hosting, identity, stores, encryption, availability objectives, and compliance posture remain unresolved.
