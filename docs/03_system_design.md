# AI Finance Assistant — System design

Version 1.8 | Status: Product architecture baseline through M6 plus M6.1 response-cache design | 2026-10-30

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
  ROUTER -. qualified exact-route reuse .-> RC[ModelResponseCache]
  QA -. evidence-bound generation reuse .-> RC
  RC --> REDIS[(Loopback Redis)]

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

One Run follows: normalize and validate request → apply access and safety policy → classify intent → reject unrelated general knowledge or select one or more agents → check required authorized context → execute independent agents concurrently where safe → synthesize structured results → validate citations, provenance, and safety → persist terminal state. Dependent work remains ordered; for example, a portfolio must be validated before enrichment and valued before a news question can be contextualized to its holdings.

Intent classification uses the Run's fixed ModelAdapter and a closed `RoutingModelOutput` schema containing only allowed Agent identifiers and a bounded reason category. The classifier is the normal graph entry path: it routes only explicit financial education, U.S. investment-tax education, financial news, saved-Portfolio, market-data, and financial-goal requests. Unrelated weather, politics, sports, entertainment, geography, and general-knowledge questions return `out_of_scope` with no specialist execution; an explicit financial connection is required before such a subject can route. The router supplies the untrusted user message and prior selected agents as data, enables no tools, records model identity/usage separately from the route outcome, and fails closed when the provider or schema is unavailable. Credential-free tests use scripted routing outputs at the same seam; they do not claim to measure live-model semantic accuracy.

Under ADR-028, M6.1 may reuse an exact route only for a previously qualified standalone Finance Q&A request in the same opaque authorized Session scope and with no authorized context references. For a semantically similar question, normal routing still runs. Finance Q&A always performs current retrieval before a generation-cache lookup; a generation hit is valid only when its Session scope, exact version filters, and active-evidence fingerprint match, and citations are rebuilt from the current Evidence. Thus a cache can avoid model work without becoming routing authority, knowledge authority, conversation memory, or the source of a Run's citations.

Execution has maximum graph hops, per-tool timeouts, an overall deadline, and model/token budgets. An independent agent failure can yield a partial result with structured warnings. Missing required user input yields a clarification result, not guessed data.

## 3. Six-agent interfaces and interaction limits

All agents accept an AgentRequest containing Run, Session, Workflow, user-message, authorized context references, locale/jurisdiction, and deadline. All return AgentResult with agent identifier, status, summary, structured facts, evidence, visualization data where applicable, as-of fields, warnings, and typed errors.

| Agent | Domain input | Output | Allowed tools/modules | Dependencies | Failure behavior | Interaction boundary |
|---|---|---|---|---|---|---|
| Finance Q&A | Educational question, declared experience level, conversation context | Grounded explanation, definitions, examples, risks, citations, uncertainty | Finance Education retrieval and grounded-response adapter | Active Finance KB, LLM adapter | No relevant evidence → say evidence is insufficient; incompatible collection → unavailable | Does not value portfolios, project goals, interpret personal taxes, or issue buy/sell instructions |
| Portfolio Analysis | Authorized Portfolio identifier or validated import; analysis options; valuation time | Portfolio Snapshot, allocation/concentration/expense results, coverage, provenance, warnings, explanation | Portfolio import/validation, security enrichment, MarketDataProvider, deterministic portfolio analysis | Portfolio data, provider adapter/cache, calculation policy | Invalid rows → validation report; missing prices or classifications → partial coverage; provider outage → stale-labeled or unavailable values | Does not invent data, predict returns, make suitability decisions, or overwrite imports |
| Market Analysis | Security identifiers, date range, requested statistics | Current/historical observations, descriptive statistics, provenance, freshness, limitations | MarketDataProvider and deterministic time-series statistics | Provider adapter/cache | Rate limit/timeout → bounded retry then stale cache or unavailable; invalid symbol → typed error | Describes history and context; does not turn performance into a guaranteed forecast or own goal assumptions |
| Goal Planning | Goal amount/date, starting resources, contribution schedule, inflation/return scenarios, declared risk tolerance; optional authorized summaries | Deterministic scenarios, contributions/growth decomposition, shortfall/surplus, assumptions, warnings | Goal projection module; read-only Portfolio Snapshot and future CashFlowSummary access | Calculation policy and authorized summaries | Missing fields → clarification; invalid horizon/rate → validation error; incomplete summary → labeled partial scenario | Remains separate from Market Analysis; market history may inform education but does not silently set future-return assumptions |
| News Synthesizer | Topic, security identifiers, time window, optional authorized portfolio summary | Dated attributed story summaries, fact/interpretation labels, relevance, limitations | NewsProvider; optional Market Analysis result supplied through graph | News provider and LLM adapter | Authorized context → use its query/window; uppercase ticker without context → construct a minimized ticker query; explicit broad financial-news intent → use the fixed `latest financial news` query; both defaults use a labeled seven-day window; no safe public topic → clarify; no recent stories → explicit empty state; provider failure → unavailable | Does not treat news as price prediction, retrieve unapproved sources, or expose portfolio records or raw user prompts to the provider |
| Tax Education | U.S. federal tax-education question, requested tax year, account/investment concept, jurisdiction | Educational explanation, applicable year/jurisdiction, authoritative citations, caveats | Tax Education retrieval and grounded-response adapter | Active Tax KB and LLM adapter | Explicit year → exact-year evidence only; omitted year → use and label the latest matching authoritative year; no authoritative evidence → abstain; unsupported jurisdiction → out-of-scope | Does not calculate an individual return, make elections, provide legal advice, or silently apply current law to historical years |

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
| ModelResponseCache | Reuse eligible schema-validated route/generation outputs under exact policy and evidence filters; never cache a complete Run | Disabled and deterministic in-memory adapters; loopback Redis 8/RedisVL private-demo adapter |

Ports exist only at seams that genuinely vary, normally production and test adapters. Internal helpers are not exposed just to make tests easier; observable behavior is tested through each module’s interface.

M4.1 selects OpenAI `gpt-6.1-sol` as the conditional live adapter and keeps the deterministic
adapter as the credential-free default. `WorkflowApplication` creates one fixed model adapter per
Run and shares its seven-attempt budget across one routing decision and up to six specialist
responses. The live adapter uses Responses structured output with `store=False`, no tools, bounded
untrusted input assembly, deadline-aware timeout, and typed failures. Routing and the four
non-grounded specialists use low reasoning effort; Finance and Tax use medium. Generated output is
limited to explanation and warnings: agents return deterministic module facts and provider
provenance from their original code-owned values, never model-restated arithmetic. Model and
prompt identifiers plus provider-reported token usage are allow-listed on measured events; model
cost remains unavailable until an approved versioned calculator exists. See the
[M4.1 selection record](research/M4_1_openai_model_selection.md).

M6.1 places `ModelResponseCache` at the structured model boundary rather than wrapping the whole
workflow or configuring a framework-global cache. Exact-route keys use the normalized qualified
request, opaque server-derived Session scope, and routing contract versions. Finance Q&A semantic
lookup happens only after retrieval and uses a pinned local encoder plus exact filters for agent, model/provider, prompt, Workflow, response
schema, cache policy, locale/jurisdiction, and an evidence fingerprint over the active collection
version and ordered chunk identifiers/content hashes. The initial Redis policy is loopback-only,
non-persistent, administratively purgeable, and bounded to a 24-hour maximum TTL. It stores only a
normalized policy-qualified public education query and validated structured response; raw Session
identifiers are not stored and cross-Session reuse is prohibited. All other
agents, multi-agent requests, context-dependent follow-ups, personalized inputs, and unsuccessful
results bypass reuse. Redis failure is a bounded cache bypass, not a workflow failure.

User-facing model summaries use a separate 4,000-character narrative contract across structured
model output, Agent results, Workflow results, durable Run records, REST, and SSE. The 512-character
`ShortText` contract remains for labels, warnings, errors, and bounded execution-event metadata;
it must not be reused to clip an otherwise successful answer. Model warnings contain only
user-relevant domain limitations or missing evidence. Provider incompleteness and generation
failures remain typed application failures rather than model-authored warnings.

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

M3 implements the application ports with deterministic credential-free adapters, conditional Alpha Vantage and Massive market adapters, and a conditional Tavily news adapter under ADR-024/025. `AIFA_PROVIDER_MODE` selects one bundle and `AIFA_MARKET_DATA_PROVIDER` selects one live market adapter before workflow execution. Each bundle uses one mode and one market adapter; missing credentials, insufficient budget, quota failure, or failed readiness returns an explicit unavailable state and never switches a running workflow to fake data or another live provider. The initial bounded in-memory cache is scoped to the provider process/workflow and is not a durable user record.

M5 implements ADR-026 as a two-tier durable provider cache. The memory tier serves hot exact requests; the database tier stores normalized daily bars independently by provider, canonical instrument, interval, trading date, currency, adjustment basis, and schema/policy version. A range read reports complete, partial, stale, or missing coverage, fetches only provider-specific gaps plus a configurable recent refresh window, and upserts without combining providers. Every returned series retains the source provider, original market and retrieval timestamps, freshness, cache state, and applicable entitlement/retention label. Raw provider payloads, credentials, user portfolio context, and news article bodies are not stored in this cache. Current quotes and news keep short endpoint-specific retention unless a later decision approves a different lifecycle.

Owner-only local mode may explicitly opt into long-term historical-bar retention under the ADR-026 risk exception when cache permission has not been confirmed. The setting and resulting records must state that permission is unverified, support administrative purge, and cannot satisfy readiness for a shared demonstration or public deployment. This local product-owner risk acceptance does not amend provider terms or establish redistribution rights.

Alpha Vantage quote currency is caller-supplied because the selected quote/daily endpoints do not return a currency. Massive uses the previous-day and raw daily-aggregate endpoints; its quote currency is likewise caller-supplied, and Basic data remains end-of-day with a rolling history window. Neither adapter presents these responses as realtime. Massive individual-plan data is owner-only and cannot be shown to testers or viewers without approved Business/commercial rights. Tavily is a discovery provider, not a publisher: the adapter disables generated answers and raw content, preserves the source URL/host, and labels `published_date` as provider-estimated or unavailable. Only a bounded public query may leave the backend; holdings, transactions, credentials, and user-specific financial context are prohibited.

## 10. FastAPI and React interfaces

The React application contains:

- **Conversational Assistant:** streamed response, citations, uncertainty, follow-up continuity, and partial/failure states. A completed Run renders each agent narrative once; the Workflow summary is a fallback only when no agent result exists. Chunk-level evidence is grouped by canonical source URL for display, and supplemental agent/Workflow messages are shown once by first occurrence without changing stored provenance.
- **Portfolio Dashboard:** manual/file import, validation review, snapshot selector, provenance, allocations/concentrations/expenses, warnings, and accessible tables.
- **Market Overview:** security search, timestamped current/historical data, descriptive statistics, and stale/unavailable states.
- **Goal Planning:** inputs, assumptions, deterministic scenario curves, contribution/growth decomposition, and accessible table.
- **Agent Execution Inspector:** authorized Run selector, event timeline, React Flow graph, details, sources, and measurement availability.

TanStack Query owns remote server state; frontend state is limited to interaction and view preferences. Recharts visualizations always have text/table equivalents. The browser never receives provider credentials or performs authoritative calculations.

Versioned interface groups:

- health/readiness and configuration capabilities;
- Active and Archived Sessions, history, archive, and permanent deletion;
- chat Runs, final results, event history, and SSE;
- portfolio import/validation, Portfolios, and Snapshots;
- market query;
- goal projection;
- authorized trace retrieval.

REST returns authoritative resources and terminal Run status. SSE carries typed conversation chunks and RunEvents. A client reconnects with the last event identifier when replay is supported; otherwise it reloads authorized event history and final state over REST. OpenAPI is the contract source and generated or contract-tested TypeScript types prevent drift.

M5 implements these interfaces under `/api/v1`. Artifact-creating requests accept bounded idempotency keys; reused keys return the original resource only when the request hash matches. RunEvents are persisted before replay, use stable sequence-derived event identifiers, and can be resumed with `Last-Event-ID`; the terminal conversational chunk has its own stable identifier. Every history, stream, Portfolio, Snapshot, and context lookup checks the requested Session scope. Clearing the Active Session archives it as read-only and opens a new Active Session. Archived Sessions can be listed and read; writes fail with a stable conflict. Permanent deletion requires an Archived Session and removes its owned records plus checkpoint thread. The local demo remains unauthenticated and loopback-only, so Session identifiers are isolation keys rather than proof of identity.

Assistant portfolio questions use a graph context gate after model routing. When Portfolio Analysis
is selected without an authorized Portfolio context, the graph does not start any specialist; it
returns a typed `portfolio_selection` requirement. Only then does React load the Session-scoped
saved-Portfolio list and render an explicit single-Portfolio or “all saved Portfolios — compare
separately” choice inside that Run. Submitting the choice creates a linked continuation Run through
the context gate, preserving the classifier's selected agents without paying for or risking a
second classification. FastAPI re-authorizes every opaque context identifier against the source
Run's Session. Portfolio Analysis calculates a separate deterministic Snapshot for every supplied
Portfolio and gives the model bounded Snapshot facts for explanation; it never silently chooses the
first reference or combines totals across Portfolios or currencies. The original clarification and
linked result remain separately visible in history.

FastAPI and outbound HTTPX calls are OpenTelemetry-instrumented with W3C propagation. JSON logs add request, trace, span, Session, and Run identifiers when available without bodies or headers. The optional loopback OTLP HTTP Collector receives traces and metrics and currently exports only to its debug sink. Bounded operational measurements cover HTTP status class/route, workflow status, retrieval strategy, provider operation/status/retry/rate-limit, cache outcome, and persistence operation/status. Health endpoints are excluded and protected or unbounded identifiers are not metric attributes. Export failure is isolated from product behavior; RunEvents remain the authoritative execution record.

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

Instrumentation records events at LangGraph and module execution points. The event recorder redacts before persistence. M6.1 records response-cache access using the existing tool lifecycle events with the allow-listed `model_response_cache` tool name and hit, miss, bypass, or error outcome metadata; it emits model lifecycle events only for an actual provider/model invocation. The Inspector builds dynamic nodes and edges only from recorded identifiers and relationships. A static workflow-design overlay, if shown, is visually labeled as design rather than execution.

Staged delivery remains:

- M0: schema, redaction policy, and versioned synthetic fixtures;
- M4: actual LangGraph and module instrumentation;
- M6.1: response-cache tool events, actual-model-call truth, and calibration fixtures;
- M7: timeline, details, and React Flow views;
- M8: fidelity, streaming, isolation, accessibility, and redaction evaluation.

## 12. Persistence, privacy, and security

Data classes and initial local policy:

| Data | Purpose | Initial persistence/retention requirement | Access and deletion |
|---|---|---|---|
| Uploaded file bytes | Parse portfolio | Ephemeral; delete after safe parse or failure | Parser only; cleanup tested |
| Imported Portfolio records | User analysis | Durable local store only when user saves; policy/version recorded | Owning Session/user context; delete cascades to derived user artifacts |
| Enrichment and Snapshots | Reproducible analysis | Bounded by Portfolio retention and provider terms | Same owner; deletable |
| Conversation checkpoints | Follow-up context | Durable local mode with documented retention | Owning Session; preserve on archive and delete with permanent Session deletion |
| Run records/events/traces | Conversation history, Inspector, and audit | New Run records retain the submitted request message and terminal result; legacy records may have no message; events/traces remain privacy-filtered and time-bounded | Owning Session; read-only after archive and deletion supported |
| Knowledge sources/collections | Shared education evidence | Versioned according to source rights and rollback policy | Administrative ingestion role; user deletion does not remove shared sources |
| Durable provider cache | Reliability, quota control, and reusable historical ranges | Normalized historical bars survive restart; recent bars are revalidated; quote/news retention stays endpoint-specific; local owner-only long retention requires explicit unverified-rights risk acceptance | Server only; provider/schema/policy scoped, administratively purgeable, and never presented without provenance |
| Model response cache | Reduce repeated model latency/cost for qualified public Finance Q&A | Optional non-persistent loopback Redis; maximum 24-hour TTL; current evidence is rechecked before generation reuse | Server only; opaque Session/version/evidence scoped; purged on archive/deletion or administratively; no raw Session/Run identifiers, context references, or financial/provider payloads |

The local demo is unauthenticated only when explicitly configured and bound for local use. Opaque identifiers are not authentication. Every resource lookup and stream still checks Session scope to prevent accidental cross-session leakage. A public deployment requires the ADR-019 production controls before release.

M5 local persistence uses application schema version 3 in SQLite with foreign keys, WAL for file-backed databases, a five-second busy timeout, and transactional migrations. Version 2 adds nullable `archived_at` state to Sessions; version 3 adds nullable `request_message` to Runs so new conversation history can display the submitted question while legacy Runs remain readable. Application tables store Sessions, Runs, privacy-filtered RunEvents, saved Portfolios, Snapshots, authorized agent contexts, idempotency records, normalized market bars, and range coverage. The official LangGraph SQLite saver uses a dedicated connection to the same local file and strict allow-listed checkpoint deserialization. Startup rejects a newer schema, purges expired application/cache records, and removes expired Session checkpoint threads. Archiving preserves Session-owned records and checkpoints; permanent Archived Session deletion cascades user artifacts, including submitted Run messages, and explicitly deletes its checkpoint thread. Provider cache purge is a separately token-protected local administrative operation.

Default local retention is 30 days for Sessions and RunEvents and 365 days for saved Portfolios. Historical cache retention is at most 3,650 days, with a seven-day recent tail revalidated after six hours and a 128-entry/five-minute memory tier. These are private-demo defaults, not public legal-policy approval. A later public or multi-user store requires a new ADR, authentication/authorization, protected storage, enforced retention jobs, backup/recovery, and migration qualification.

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
  response_cache/      eligibility, fingerprints, and optional Redis/in-memory adapters
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
