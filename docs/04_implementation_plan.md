# AI Finance Assistant — Incremental implementation plan

Version 3.1 | Status: M0–M9.1 complete; M10 planned; M11 slices 2 and 4 implemented, slice 3 live-recovery gate pending, and slice 5 foundation provisioned with remaining qualification gates | 2026-11-10

## 1. Delivery rules

Each milestone is a bounded, reviewable increment. Before implementation, read [the documentation index](README.md), follow accepted ADRs, and check whether any open decision blocks the milestone. Use fake external adapters in continuous integration and record actual commands and results. A file, class, dependency, or framework import is not completion evidence; acceptance tests must exercise observable behavior through the documented interface.

Every milestone delivery report must include:

1. files and interfaces changed;
2. requirement and ADR mapping;
3. migrations or collection/configuration versions;
4. exact commands and actual results;
5. failing, skipped, quarantined, and manually verified cases;
6. evidence artifact paths;
7. security/privacy impact and known limitations;
8. unresolved decisions and the next permitted milestone.

Milestones sequence delivery; they no longer define repository ownership. New implementation,
Terraform, workflow, contract, fixture, test, and evidence paths use the product capability or
release/quality owner defined by [the repository layout](repository_layout.md). Milestone identifiers
belong only in this plan, delivery reports, and historical evidence. Do not create `m10`, `m11`, or
equivalent milestone-owned implementation directories.

Cash flow remains a planned enhancement: M2 reserves and tests its interface shape, and post-release M10 implements provider-independent CSV/JSON bank and credit-card imports. The initial release prioritizes investment portfolios and complete behavior for all six agents.

The initial and coursework releases are production-oriented private demonstration releases, not public launches. A documented live-demo mode may use approved provider calls within a predeclared entitlement-aware request budget. A separate credential-free mode uses deterministic adapters and remains fully demonstrable when credentials, quota, or provider availability are absent. Modes are selected explicitly; a run never silently changes from live to synthetic data.

Observability has three distinct records that must not be collapsed into one vendor:

1. privacy-filtered RunEvents are the authoritative product execution record used by history, replay, and the Inspector;
2. OpenTelemetry carries operational traces and metrics across the browser, FastAPI, application modules, and external adapters, with structured logs correlated by trace/span and request/execution identifiers;
3. LangSmith is an optional agent/LLM trace and evaluation adapter, not a replacement for RunEvent persistence, operational metrics, or logs.

Telemetry configuration is environment-driven and disabled safely when no exporter credentials or endpoint are configured. Export failure must not fail a product request. Every exporter receives only allow-listed, redacted fields; raw prompts, financial records, transactions, credentials, hidden reasoning, and unrestricted tool payloads are excluded.

## 2. Revised milestones

### M0 — Repository, development environment, and contracts

**Deliverables**

- Reproducible backend/frontend project foundations and documented local commands.
- FastAPI liveness/readiness interface and React application shell for Chat, Portfolio, Market, Goals, and Inspector.
- Shared versioned schemas for AgentResult, provider provenance, Portfolio identifiers, typed errors, and RunEvent v1.
- Configuration and secret-loading seam, structured correlation logging, redaction policy, and local-demo mode labeling.
- Qdrant collection expectation/readiness configuration only; no corpus ingestion or startup embedding.
- Versioned synthetic RunEvent fixtures clearly marked as synthetic.

**Dependencies:** Accepted documentation only.

**Acceptance:** Both foundations start in mock/local mode; frontend reads health; schema validation rejects invalid identifiers/timestamps/status; no real agent, fake live data, SSE server, corpus, or finance calculation is represented as complete.

**Tests:** Backend schema/health tests; frontend navigation, contract, and accessibility smoke tests; lint/typecheck; secret/redaction fixtures.

**Evidence:** [M0 delivery report](M0_delivery_report.md), command log, generated schema snapshot, screenshots of labeled empty/synthetic states. The bounded implementation prompt is [06_codex_starting_prompt.md](06_codex_starting_prompt.md).

### M1 — Persistent Qdrant and offline knowledge ingestion

**Deliverables**

- SourceRegistry and use-rights fields for Finance Education and Tax Education sources.
- Separate offline ingestion application implementing discovery through activation.
- Qdrant payload schema, dense/sparse representation version metadata, logical active aliases, readiness checks, and rollback record.
- Initial permitted Finance and Tax candidate collections, historical tax-year metadata, and fixed retrieval qrels.
- Incremental/idempotent updates using source and content hashes.

**Dependencies:** M0 contracts and a resolved Qdrant hosting mode/model experiment plan.

**Acceptance:** Startup validates active collections without fetching or embedding; unchanged rerun creates no duplicate points; a changed document creates a new version; an incompatible collection is not ready; a candidate cannot activate until schema and retrieval gates pass; rollback restores the previous active alias.

**Tests:** Extraction/chunking fixtures, duplicate/change detection, payload/metadata validation, tax-year filters, dense baseline, sparse/hybrid/RRF comparisons, citation-source integrity, activation/rollback, missing-Qdrant behavior.

**Evidence:** [M1 delivery report](M1_delivery_report.md), SourceRegistry and permitted-use review, collection manifests/checksums, fixed qrels, comparative evaluation reports, activation records, restart evidence, and rollback transcripts. Coursework corpus counts are reported separately without padding.

### M2 — Deterministic financial calculation modules

**Deliverables**

- Common manual/JSON/CSV/XLSX PortfolioImport interface and safe parsers.
- Imported Portfolio/Account/Holding records, provider-enrichment records, and Portfolio Snapshot model kept separate.
- Deterministic valuation, allocation, expense coverage, classification concentration, and versioned diversification heuristic.
- Deterministic GoalProjection with recurring contributions, inflation, fees when modeled, and multiple user-controlled scenarios.
- Conceptual CashFlowAnalysisService and CashFlowSummary interfaces only, sufficient to prevent later Goal Planning rework.
- Versioned valid and adversarial sample datasets.

**Dependencies:** M0 contracts. Market enrichment remains fake at this milestone.

**Acceptance:** Golden outputs reproduce exactly under the documented precision policy; imports aggregate safe errors; duplicates are reported rather than silently merged; missing prices/classifications reduce coverage; mixed currency is either explicitly converted with a fixture or kept separate; no LLM is involved.

**Tests:** Unit, property, and metamorphic arithmetic tests; all four import modes; malicious formula/macro-like content; size/row limits; duplicate and missing-field fixtures; serialization and deletion lifecycle.

**Evidence:** [M2 delivery report](M2_delivery_report.md), [calculation policy/version](M2_calculation_policy.md), hand-worked golden cases, sample-data manifest, test and coverage reports, and documented heuristic limitations.

### M2.1 — Cost-basis unrealized performance

**Deliverables**

- `finance-calculation-v2` with `unrealized-performance-v1`: per-Holding cost basis total, unrealized gain/loss, return on cost, holding period, and Actual/365 annualized return for holdings held at least one year; per-currency summary with cost-basis value coverage; and top-five Holding concentration.
- Additive Snapshot contract fields so persisted `finance-calculation-v1` Snapshots remain readable.
- Portfolio Analysis facts, read-only MCP output, and a Portfolio Dashboard section with summary metrics, a single-currency bar chart, and an accessible table.
- Hand-worked golden dataset and artifact registered in the calculation fixture manifest.

**Dependencies:** M2 import of cost basis and acquisition date; M5 Snapshot API; M6 Portfolio Dashboard. No provider, history, or ADR change. History-based volatility, drawdown, and risk-adjusted metrics are out of scope because they need per-holding history beyond the private-demo market request budget and a new decision.

**Acceptance:** Goldens reproduce exactly; missing cost basis reduces coverage instead of inventing zero; unpriced, zero-basis, future-acquisition, sub-one-year, total-loss, quote-currency-mismatch, and mixed-currency cases behave as documented; v1 Snapshots deserialize; agents explain but do not recalculate the figures.

**Tests:** Golden, edge-case, currency-partition, and backward-compatibility unit tests; agent fact and MCP regression; frontend component tests for signed values, coverage, missing basis, mixed-currency chart suppression, and v1 Snapshots.

**Evidence:** [M2.1 delivery report](M2_1_delivery_report.md), [calculation policy §6a](M2_calculation_policy.md), golden artifact, and test/coverage results.

### M3 — External market and news integrations

**Deliverables**

- MarketDataProvider and NewsProvider ports with selected production and fake adapters.
- Standard provenance/freshness envelopes, provider-specific rate limits, bounded cache, timeouts, retry/jitter, and circuit behavior.
- Current/historical quote and dated-news retrieval suitable for the Market and News agents.
- Provider license, entitlement, and fallback decision record updates.
- Explicit live-demo and credential-free provider modes, including startup/readiness checks, per-workflow request budgets, cache reuse, and labels that prevent synthetic, delayed, cached, or unavailable data from appearing live.

**Dependencies:** M0 contracts; selected providers and accepted data terms. Portfolio enrichment consumes M2 interfaces.

**Acceptance:** Success, delay, cache, stale, rate-limit, invalid-symbol/query, malformed-payload, and unavailable behavior are observable and correctly labeled; the documented private live-demo journey stays within the configured provider entitlement and request budget; the same feature journey remains reproducible in credential-free mode; synthetic results cannot appear live and one Run never mixes live and fake provider data.

**Tests:** Adapter contracts using recorded permitted fixtures or fakes; 401/403, 429, timeout, malformed data, cache expiry, provider fallback, provenance timestamp, concurrency/quota cases, preflight budget exhaustion before a provider call, repeated-view cache behavior, missing credentials, explicit mode/market-adapter selection, and no live/synthetic or cross-provider mixing. Opt-in tests marked `live_provider` may validate an approved Alpha Vantage or Massive market account plus Tavily; ordinary suites exclude that marker and require no credentials.

**Evidence:** [M3 delivery report](M3_delivery_report.md), [provider policy and activation gate](M3_provider_policy.md), ADR-024/025, synthetic contract fixtures, failure matrix, cache/rate configuration, actual test report, cost/limit notes, and a private-demo call-budget transcript for credential-free mode and the deliberately blocked live preflight.

### M4 — LangGraph orchestration and all six agents

**Deliverables**

- Versioned FinanceState, schema-constrained ModelAdapter router, bounded conditional graph, synthesis/validation, and checkpoint interfaces.
- Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, and Tax Education agents with the exact §3 responsibilities.
- Finance and Tax retrieval; M2 calculations; M3 providers; multi-agent composition without recursive agent calls.
- Actual RunEvent instrumentation for routes, nodes, retrieval, tools/providers, models, and terminal state.
- A small vendor-neutral observability interface for spans, metrics, and context propagation, with OpenTelemetry runtime and in-memory test adapters.
- Optional LangSmith tracing for LangGraph, agent, model, retrieval, and tool spans; RunEvent identifiers correlate with exported traces while RunEvent persistence remains authoritative.
- Redaction and allow-list filtering before RunEvent persistence or external trace export; LangSmith inputs/outputs and unsafe metadata are hidden by default.

**Dependencies:** M1–M3.

**Acceptance:** Each agent passes distinct domain cases; labeled requests route correctly; Finance/Tax cite Run evidence; Portfolio/Goal use deterministic outputs; multi-agent results preserve domain boundaries; restart/follow-up and partial failures behave as designed; event sequences match graph execution; every instrumented operation carries stable correlation; disabling or losing an observability exporter does not change product behavior.

**Tests:** Labeled single/multi-intent routing, agent contract suites, collaboration, hop/deadline bounds, citation and tax-year correctness, prompt injection, malformed model output, checkpoint restart/isolation, event ordering and redaction, in-memory span/metric assertions, disabled/exporter-failure behavior, and RunEvent-to-trace correlation.

**Evidence:** Six-agent behavior report, route confusion matrix, captured privacy-filtered RunEvents and OpenTelemetry traces, optional LangSmith trace samples when configured, actual graph diagrams, exporter-failure evidence, and failure examples.

### M4.1 — Production LLM adapter and live-model qualification

**Deliverables**

- Evaluation-based selection of the initial production model/provider under ADR-008, including capability, structured-output, privacy, retention/training, regional, latency, context-limit, availability, and cost considerations.
- A production ModelAdapter implementing the same versioned structured request/result contract as the deterministic adapter; all six agents continue to use the shared seam and never call a vendor SDK directly.
- Environment-owned credentials and explicit credential-free versus live-model modes. One Run fixes its model/provider/model-version selection before execution and uses it for routing plus selected-agent responses; it never silently substitutes fake output.
- Versioned system instructions and response schemas, bounded evidence/context assembly, model and prompt identifiers on measured events, and schema-validation/repair behavior that does not accept arbitrary malformed output.
- Deadline-aware timeout, bounded retry/backoff, concurrency and per-Run token/request budgets, typed provider failures, measured provider token usage where supplied, and clearly unavailable cost when no approved calculation method exists.
- Privacy-safe OpenTelemetry and optional LangSmith instrumentation. Prompts, retrieved excerpts, financial records, credentials, provider payloads, and model responses remain excluded from RunEvents and operational telemetry; LangSmith inputs and outputs stay hidden unless a later approved privacy decision changes that policy.
- Opt-in live-model qualification tests and a credential-free deterministic suite. Ordinary CI loads the tracked `backend/.test.env`, requires no model credential, performs no external model call, and never reads the developer's `backend/.env`; live targets opt into that file explicitly.

**Dependencies:** Completed M4 seam; an approved model/provider decision satisfying ADR-008; account credentials and terms suitable for the private demonstration; documented data-use, retention, and training controls. Missing approval or credentials blocks live-model activation rather than triggering an automatic provider or fake fallback.

**Acceptance:** Each of the six agents completes at least one distinct, schema-valid live-model case through the shared adapter; Finance and Tax remain grounded in supplied Run evidence; Portfolio and Goal explain deterministic outputs without changing arithmetic; Market and News preserve provider provenance and attribution; model/prompt/version and measured usage correlate with RunEvents and OpenTelemetry; timeout, quota, malformed output, refusal, and provider outage return typed safe states; credential-free behavior remains reproducible; no raw prompt, evidence excerpt, financial payload, credential, unrestricted response, or hidden reasoning appears in persisted events, logs, or exported operational attributes.

**Tests:** Production-adapter contract tests with permitted recorded or hand-authored fixtures; deterministic tests for structured success, refusal, malformed/extra/truncated output, timeout, authentication, quota/rate limit, transient retry exhaustion, context/token/request budget, deadline, cancellation propagation where supported, usage availability, redaction, prompt-injection boundaries, and fake/live separation. Explicitly marked live tests exercise one bounded request per representative agent behavior or an approved lower-call matrix that still covers all six output contracts; ordinary suites exclude the marker.

**Evidence:** Model/provider selection record, account terms/privacy review, model and prompt/version inventory, structured-output and failure matrix, token/request budget, privacy data-flow review, captured redacted RunEvent/OpenTelemetry correlation, optional hidden-input/output LangSmith sample, opt-in live qualification report with actual request count and cost/usage availability, credential-free regression report, limitations, and a delivery report.

### M5 — FastAPI integration and persistence

**Deliverables**

- Versioned REST resources for Active and Archived Sessions, archive/history/permanent deletion, chat Runs, Portfolios/import validation, Portfolio Snapshots, market queries, goal projections, and authorized trace history.
- SSE for conversational chunks and RunEvents with documented replay or REST recovery.
- Durable local adapters for checkpoints, saved portfolios, run summaries/events, Session archive/history/permanent deletion, and retention; idempotency for artifact-creating requests.
- An application-owned durable provider-cache port and relational adapter for normalized historical daily bars, with a bounded memory front cache, range-coverage and gap detection, recent-tail revalidation, provider/schema/policy isolation, concurrent-request deduplication, and administrative purge. Current quotes and news retain short endpoint-specific lifecycles unless separately approved.
- OpenAPI-driven or contract-verified frontend types and readiness for storage/Qdrant/providers.
- FastAPI and outbound-client OpenTelemetry instrumentation with W3C trace-context propagation; JSON logs enriched with trace, span, request, execution, and Run identifiers when available.
- OTLP/Collector configuration for enabled signals, with backend request/error/latency, provider/retrieval timing, retry/rate-limit, cache, and persistence metrics using bounded low-cardinality attributes.

**Dependencies:** M1–M4.1. ADR-026 validation must select the concrete local relational store and record provider-specific refresh, retention, migration, and risk-acceptance behavior before implementation.

**Acceptance:** REST is authoritative; reconnect deduplicates events; cross-session reads/streams fail; restart behavior matches configured retention; clearing archives the Active Session without removing history; Archived Sessions are read-only and explicit permanent deletion removes defined user artifacts; partial and not-ready states use stable errors; inbound and outbound trace context correlates with logs and RunEvents; telemetry remains non-blocking and no metric label or exported attribute exposes protected or unbounded identifiers. A complete, fresh historical range survives restart without a provider call; an overlapping or partially stale request fetches only missing/provider-approved refresh coverage; stored observations never cross provider, adjustment, currency, or schema/policy boundaries; and every response truthfully distinguishes memory hit, durable hit, partial hit, stale, and unavailable states. Owner-only unverified-rights retention requires explicit local risk acceptance and cannot pass shared-demo or public-deployment readiness.

**Tests:** OpenAPI snapshots/contracts, REST/SSE framing, last-event/recovery behavior, concurrent Runs, authorization scope, restart, idempotency, Active-to-Archived transitions, read-only history, permanent deletion, schema migration, CORS/local bind, resource limits, W3C context propagation, log/trace correlation, metric cardinality, health-endpoint exclusion, and unavailable Collector/exporter behavior. Provider-cache tests cover exact and overlapping ranges, gap-only fetches, recent-tail refresh, stale fallback, no-call restart reuse, concurrent request coalescing, provider/currency/adjustment/schema isolation, malformed or migrated rows, purge, retention expiry, and owner-only versus shared/public rights gates.

**Evidence:** [M5 delivery report](M5_delivery_report.md), interface specification, migration records, contract test report, SSE transcript, lifecycle/isolation evidence, provider call-count and restart-reuse transcripts, cache schema and purge record, retention/rights configuration, correlated FastAPI/module trace sample, metric inventory, Collector/exporter configuration, and documented local security posture.

### M6 — React product experiences

**Deliverables**

- Conversational Assistant, Portfolio Dashboard, Market Overview, and Goal Planning views.
- Manual/JSON/CSV/XLSX portfolio flows with validation review and no silent corrections.
- TanStack Query integration, Recharts visuals and accessible tables, citations/provenance, freshness, coverage, and assumption displays.
- Responsive, keyboard-accessible loading, empty, partial, success, stale, and failure states.
- Confirmed Active Session archive, fresh-Session creation, read-only archived conversation history, and separately confirmed permanent deletion from History.
- Privacy-safe frontend telemetry module for error-boundary events, Web Vitals, navigation, and API timing/failure categories, with W3C trace context and request correlation propagated to FastAPI.
- First-party telemetry transport or protected Collector adapter; no LangSmith, provider, or telemetry credential is shipped to the browser, and telemetry contains no prompt or financial payload content.

**Dependencies:** M5 interfaces and deterministic backend fixtures.

**Acceptance:** Users complete core workflows without developer tools; clearing an Active Session preserves it in History and opens a fresh Session; only an Archived Session exposes permanent deletion; UI never performs authoritative calculations or leaks credentials; chart/tabular values match backend resources; refresh/reconnect preserves intended state; frontend failures correlate to backend traces when sampled; disabled or failed telemetry has no user-visible functional effect.

**Tests:** Component tests, API mock contracts, Playwright user journeys including archive/history/permanent deletion, keyboard/focus/semantic/contrast checks, responsive layouts, network failure and stale data, import error correction, error-boundary and Web-Vitals emission, trace/request-header propagation, payload redaction, CSP/CORS behavior, and unavailable telemetry transport.

**Evidence:** [M6 delivery report](M6_delivery_report.md), browser-test report, accessibility review, screenshots for representative states, contract-version record, privacy-safe frontend telemetry sample, and browser-to-FastAPI correlation record under `docs/evidence/m6/`.

### M6.1 — Evidence-bound response cache and M8 preparation

This milestone implements ADR-028 for QR-001, QR-004, QR-006, QR-007, QR-010, QR-012, QR-014, and QR-015. It prepares the latency, cost, privacy, and trace-fidelity evidence that M8 will qualify; it does not claim that a cache hit is automatically safe or that the M8 release gate has passed.

**Deliverables**

- An application-owned `ModelResponseCache` port and versioned eligibility/key/fingerprint policy, with disabled and deterministic in-memory adapters plus a Redis 8/RedisVL private-demo adapter. Do not route the custom `ModelAdapter` through a framework-global cache.
- Explicitly selected local infrastructure: loopback-only Redis, pinned container/dependency versions, persistence disabled, a maximum 24-hour TTL, bounded lookup timeout, administrative purge, and readiness that distinguishes an optional unavailable accelerator from a required product dependency.
- Exact route reuse only for previously qualified standalone public Finance Q&A or U.S. Tax Education requests, and semantic reuse only for successful schema-validated generation from the same RAG domain after corresponding current Qdrant retrieval. Tax reuse additionally requires an exact U.S. federal jurisdiction and resolved tax-year match. Semantic matching uses a pinned local embedding adapter, initially the existing `BAAI/bge-small-en-v1.5` FastEmbed model if calibration accepts it, without an external embedding request.
- Exact invalidation filters for an opaque server-derived Session scope, agent, model/provider, prompt, workflow, response schema, cache-policy version, locale/jurisdiction, and the active evidence fingerprint of collection version, retrieved chunk identifiers, and content hashes. A hit creates a new Run and rebuilds citations from the current Evidence; it never replays a cached Run or cached citations, and another Session cannot reuse it.
- A deny-by-default eligibility policy allowing only standalone public Finance Q&A and U.S. Tax Education while excluding context references, checkpoint-dependent follow-ups, multi-agent requests, Portfolio, Market, Goal, News, personalized inputs, errors, partial/no-evidence results, and unqualified messages. Stored values contain only an opaque Session scope, the normalized policy-qualified public education query, and the validated structured response, never system prompts, raw Session/Run identifiers, or financial/provider payloads. Session archival/permanent deletion and administrative purge remove the applicable namespace.
- Keyed request coalescing for identical in-flight eligible misses within the same Session scope and documented process boundary, plus fail-open bypass for Redis timeout, outage, corruption, or schema incompatibility.
- Privacy-filtered RunEvents, OpenTelemetry spans/metrics, and optional LangSmith correlation for lookup outcome, bypass reason, entry age, policy version, bounded similarity-distance bucket, avoided model request/token availability, and actual model calls. Cache hits must not emit model-started/model-completed events for work that did not occur.
- A frozen exact/paraphrase/near-miss/adversarial evaluation set and shadow-mode report used to calibrate the semantic threshold before serving semantic hits. The threshold, encoder identity, TTL, and eligibility rules are versioned configuration.

**Dependencies:** Completed M1 collection/version contracts, M4/M4.1 structured routing and generation seams, M5 API/RunEvent/telemetry foundations, M6 product journeys, and the M7 Inspector's generic persisted-event rendering seam. M6.1 adds response-cache events through the existing tool-event contract after M7; it does not require an Inspector-specific cache representation. Redis and RedisVL compatibility, image digest, package pin, local resource use, and license/security review must be recorded before implementation.

**Acceptance:** Within one Active Session, a second identical eligible Finance or Tax question creates a distinct Run, executes current domain retrieval, rebuilds current citations, and avoids both routing and generation model calls; a calibrated paraphrase executes routing and current retrieval but may avoid generation only when all exact filters and the evidence fingerprint match. Tax-year or jurisdiction changes cannot reuse an entry. The same input in another Session, a frozen near-miss, or a changed collection/chunk/model/prompt/workflow/policy/schema value cannot reuse the entry. Archival and permanent deletion remove the Session namespace. Excluded or ambiguous requests always execute the normal path. A Redis outage or malformed entry is visible as a bounded bypass and produces the same functional result as cache-disabled mode. Cache events, model-call counts, usage availability, and latency are truthful and reconcilable across RunEvents and operational traces. On the same recorded fixture and hardware, exact and qualified semantic hits demonstrate lower end-to-end latency than cache-disabled runs. Semantic serving remains disabled unless the frozen Finance-and-Tax near-miss/adversarial set has zero critical false hits and every proposed semantic hit in the calibration set has recorded human review; the selected threshold favors precision over hit rate.

**Tests:** Port/adapter contracts; deterministic exact and semantic hit/miss behavior; route-only versus generation reuse; schema validation; evidence-fingerprint and every version-filter invalidation; cross-Session non-reuse; archive/delete/administrative purge; TTL/expiry; deny-by-default eligibility; privacy/redaction canaries; paraphrase/near-miss/adversarial fixtures; disabled/shadow/serving modes; Redis absence, timeout, corruption, and incompatible-index handling; same-Session concurrent identical-miss coalescing; Run/SSE/RunEvent identity and ordering; model-call/event truth; deterministic clean-environment behavior without Redis or credentials; and an opt-in real-Redis integration suite excluded from ordinary unit runs.

**Evidence:** ADR-028 implementation record; response-cache schema and policy versions; pinned Redis/RedisVL/encoder manifest; threat/privacy data-flow review; purge and outage transcripts; fixed-set threshold calibration with false-hit review; cache-disabled/exact-hit/semantic-hit/near-miss benchmark including p50/p95 latency, model-call/token availability, and answer/citation comparison; correlated RunEvent/OpenTelemetry/LangSmith samples; actual commands/results/skips; known limitations; and an M6.1 delivery report. M8 consumes these artifacts and independently reruns the release qualification.

### M7 — Agent Execution Inspector

**Deliverables**

- Authorized Run selector, execution timeline, details panel, and React Flow path visualization backed by M4/M5 events.
- Display of routing, status, measured timing, safe tool/result metadata, retrieval sources, and tokens/cost where available.
- Explicit “not available” states and clearly distinct static workflow-design overlays if used.
- Event deduplication, out-of-order handling, reconnect behavior, and accessible list alternative.
- Authorized correlation identifiers sufficient to locate the corresponding operational or LangSmith trace when configured; the Inspector continues to render only persisted RunEvents and never queries an external trace backend as its source of truth.

**Dependencies:** M4 instrumentation, M5 history/SSE, and the M6 shared UI. M6.1 is not a prerequisite: later response-cache activity must use the generic persisted tool-event contract and remains absent or unavailable until that milestone is implemented.

**Acceptance:** Every dynamic node and edge resolves to recorded events; failures/partial paths are truthful; synthetic fixtures are labeled; raw financial records, credentials, hidden reasoning, prompts, and unsafe payloads never render.

**Tests:** Synthetic and actual runs, event-to-graph reconciliation, duplicate/out-of-order streams, missing measurements, failed/skipped nodes, multi-run/session isolation, redaction, keyboard and screen-reader flows.

**Evidence:** Fixture versions, backend/Inspector comparison report, screenshots of success/partial/failure, and redaction assertions.

### M8 — Evaluation, security, observability, and reliability

**Completed (2026-10-31):** the versioned full qualification reports all EVAL-01 through EVAL-18
dimensions passed, zero critical failures, zero incomplete gates, and a passing private-demo
release gate. The owner approved the selected-model review and the two frozen semantic candidates;
semantic serving is qualified under the recorded policy. See
[the M8 delivery report](M8_delivery_report.md).

**Deliverables**

- Versioned evaluation datasets and runner covering every dimension in [evaluation strategy](05_evaluation_strategy.md).
- Privacy/security threat review, prompt-injection suite, safe-file suite, and session/access audit.
- Reliability tests for providers, Qdrant, persistence, retries, load bounds, and restart.
- Measured routing/retrieval/grounding/arithmetic/portfolio/import/citation/tax-year/UI/Inspector/latency/cost reports.
- Response-cache qualification using M6.1's frozen exact/paraphrase/near-miss/adversarial set, including false-hit review, invalidation, cache-disabled equivalence, privacy/redaction, outage behavior, and measured avoided calls/tokens.
- End-to-end observability qualification across browser, FastAPI, deterministic modules, providers/retrieval, LangGraph, and RunEvent persistence, including sampling, correlation, redaction, retention, metric cardinality, and exporter backpressure/outage behavior.
- Operational runbooks for local failures and explicit production-hardening gap register.

**Dependencies:** M1–M7 feature-complete candidate, including M4.1 and M6.1.

**Acceptance:** All critical release gates pass; no critical financial arithmetic, access, leakage, citation, response-cache false-hit, or trace-fidelity defect remains open; metrics include configuration and unavailable values; response-cache serving remains disabled unless cache-disabled equivalence, the zero-critical-false-hit gate, evidence/version invalidation, and measured latency benefit pass; a sampled request can be reconciled across frontend telemetry, backend spans/logs, LangSmith when enabled, and the authoritative RunEvent record; collector/exporter loss cannot corrupt or block product state; any noncritical exception has owner, rationale, and expiry.

**Tests:** Full regression, adversarial, integration, browser, accessibility, benchmark, response-cache false-hit/invalidation/outage/privacy suites, soak/concurrency within initial scale, clean-environment suite, sensitive-field canaries, sampling/retention, missing-parent/partial-trace handling, high-cardinality rejection, and Collector/LangSmith outage tests.

**Evidence:** Immutable evaluation bundle, coverage report, threat model, dependency scan, benchmark/cost report, observability data-flow diagram, signal/attribute inventory, correlated cross-tier trace, redaction and exporter-failure reports, known-risk register, and release recommendation.

### M9 — Product documentation, coursework packaging, demonstration, and release

**Completed (2026-10-31):** the release bundle, evidence-path audit, frontend coverage report,
credential-free demo, and four-tool read-only MCP stdio/client validation satisfy PR-014, PR-015,
and CA-01 through CA-13 without changing the owner-only release boundary. See
[M9 delivery report](M9_delivery_report.md).

**Deliverables**

- User/developer/operator documentation, diagrams, source/license register, sample-data guide, and clean-start instructions.
- Read-only MCP adapter and client setup/evidence if CA-13 remains required.
- Coursework evidence matrix, 5–10 minute demonstration script/recording plan, and React/Qdrant substitution rationale.
- Private-demo runbook with explicit provider mode, readiness preflight, per-journey request budget, cache assumptions, and a separately selected credential-free alternative that remains labeled synthetic.
- Product release notes, limitation/disclaimer review, collection and schema versions, rollback instructions, and signed completion checklist.
- Operator guidance for observability configuration, disabled mode, sampling, privacy filters, retention, Collector/exporter routing, LangSmith setup, dashboards/alerts where deployed, and correlation-based troubleshooting.

**Dependencies:** M8 release recommendation and authoritative coursework confirmation where obtainable.

**Acceptance:** Product gate: a clean environment reproduces the private demonstration release, every initial product requirement has evidence or an explicitly approved exception, and no public-deployment or unimplemented production control is claimed complete. Coursework gate: CA-01 through CA-13 have evidence or an approved instructor clarification; every demo path works with stable fixtures; optional live calls pass preflight, remain within the recorded provider budget, and are separately labeled.

**Tests:** Clean install/start, documentation link/command validation, packaged sample walkthrough, MCP protocol/client test, evidence-path audit, and final regression.

**Evidence:** Release bundle, exact environment/command log, requirement-to-evidence matrix, demonstration artifact, MCP record, known limitations, and approval.

### M9.1 — Product-oriented repository layout maintenance

**Completed:** 2026-11-02. See [M9.1 delivery report](M9_1_delivery_report.md).

**Deliverables**

- Capability-owned paths for committed backend data and generated artifacts, with cross-product
  reports under quality, qualification, or release ownership.
- Interface-named machine contracts and behavior-named backend tests without milestone identifiers.
- One current repository-layout reference plus durable agent guidance; milestone delivery reports
  remain historical evidence rather than the navigation model for current assets.
- Atomically reconciled CLI defaults, Make targets, JSON path references, hashes, documentation
  links, and release audits.
- Environment-owned workflow, LangSmith-project, and OpenTelemetry-service identities, including
  credential-free backend and frontend test configuration without product-identity literals in
  implementation or test fixtures.

**Dependencies:** Completed M9 release bundle and accepted ADR-029. This maintenance does not change
runtime state locations, product contracts, collection versions, financial calculations, or release
scope.

**Acceptance:** No tracked backend data, artifact, contract, or test path is owned by a milestone
directory or filename; every moved path has one capability/release owner; all machine references and
documentation links resolve; active RAG collection identities and artifact contents remain
unchanged except for path metadata; credential-free backend, frontend, contract, evidence, and
release gates pass.

**Tests:** Formatting, linting, strict typing, full backend and frontend suites, path/reference and
checksum audits, contract reconciliation, release qualification, and documentation-link checks.

**Evidence:** ADR-029, [repository layout](repository_layout.md), rename map in version control, exact
verification commands/results, security/privacy statement, and unresolved limitations.

### M10 — Provider-independent bank and credit-card cash-flow import

**Deliverables**

- Versioned `CashFlowImport` interface with safe UTF-8 JSON and CSV parsers for user-exported bank and credit-card transactions; no financial-data provider or live account connection is required.
- Canonical JSON schema plus versioned Cash-flow import profiles that map supported CSV headers, date/amount conventions, debit/credit signs, and source categories into the M2 transaction contracts.
- Deterministic CashFlowAnalysisService implementation for normalization, versioned categorization with user overrides, recurring-expense candidates, monthly/category income and spending, surplus, trends, coverage, and warnings.
- Authorized cross-import reconciliation for duplicates, transfers, and credit-card payments so internal money movement is excluded from spending exactly once, with ambiguous matches left unresolved.
- Versioned REST resources, durable authorized storage, idempotent imports, retention/deletion behavior, and a React import/review/correction experience with accessible summaries.
- Minimized CashFlowSummary access for Goal Planning by identifier; raw rows and descriptions remain outside general LangGraph state, prompts, RunEvents, logs, metrics, and external traces.
- Deterministic fake data and versioned valid/adversarial JSON and CSV fixtures. A future provider adapter may target the same canonical interface but is not an M10 dependency or acceptance requirement.

**Dependencies:** M2 cash-flow contracts plus M5 authorization/persistence/API patterns and the M6 UI foundation. M10 is scheduled after the M9 initial/coursework release and has no dependency on M3 market/news providers or a banking-data provider.

**Acceptance:** Equivalent CSV and JSON inputs produce the same canonical transactions and summaries without network access or paid credentials; unsupported or ambiguous mappings require user review rather than guessed fields; transfers and card payments are not double-counted; category overrides and unresolved matches remain reproducible; mixed currencies are not silently combined; import bytes follow the documented cleanup policy; authorized restart and cascade deletion behavior passes; Goal Planning receives only an authorized minimized summary; no seventh agent is introduced.

**Tests:** Parser schema and mapping-profile contracts; CSV/JSON equivalence; malformed encoding/shape, formula-like cells, size/row/column limits, date/amount/sign conventions, duplicate/idempotent imports, deterministic categorization and overrides, recurring detection, transfer/card-payment reconciliation and ambiguity, multi-account/currency coverage, restart/isolation/deletion, REST/OpenAPI contracts, browser import-correction/accessibility journeys, and log/trace/prompt redaction canaries.

**Evidence:** Cash-flow import and calculation policy versions, profile registry, canonical schema, valid/adversarial fixture manifest, hand-worked reconciliation goldens, API and lifecycle reports, test/coverage results, UI evidence, privacy data-flow review, redaction report, limitations, and a delivery report.

### M11 — IAP-protected GCP private multi-user deployment

M11 is an independent post-release production-hardening track. It may proceed before, after, or in
parallel with M10 and must not imply that cash-flow import is implemented. Its first slice is
documentation-only: proposed ADR-030, the requirements/design/evaluation updates, deployment threat
boundaries, open owner decisions, and rollback gates. Later slices may begin only after their
dependencies and ADR-030 validation questions are resolved.

**Deliverables**

- A versioned `/finance_assistant` base-path contract covering React routes and assets, REST,
  replayable SSE, redirects, health/readiness, generated URLs, and reverse-proxy behavior while
  preserving an explicit loopback local-development mode.
- IAP-only browser authentication for the deployed Finance Assistant. FastAPI validates the signed
  IAP assertion and maps its issuer/subject to an immutable Application Principal with owner or
  approved-viewer role; email is not a resource-ownership key.
- Per-Principal authorization and durable ownership for Assistant Sessions/checkpoints, Portfolios,
  enrichments/Snapshots, Market context, Goals, History, Runs/RunEvents, streams, idempotency, cache
  namespaces, deletion, and Inspector access. Shared knowledge remains read-only, and any shared
  provider observation or cache entry requires an approved non-user-specific policy.
- Stateless deployable frontend/backend images plus selected managed application/checkpoint storage,
  production Qdrant, Redis topology, secret management, encryption, migrations, retention jobs,
  backup/restore, readiness, observability, quotas, and cost controls. Exact GCP services, region,
  sizing, and retention periods require the owner decisions and validation named by ADR-030.
- Capability-owned Terraform for the GCP foundation, workload identity, Artifact Registry,
  workloads, networking, load balancer, IAP, managed data services, Secret Manager, monitoring,
  budgets, HTTPS, and no-direct-workload-bypass controls. Registrar/DNS actions that cannot be owned
  by Terraform remain explicit, reviewable operator steps.
- Capability- and release-owned GitHub Actions for deterministic CI, dependency/secret/container/IaC
  scanning, image publication, Terraform validation/plan, approval-gated apply/deploy, migration,
  smoke verification, and rollback. GCP authentication uses Workload Identity Federation and stores
  no long-lived service-account key in GitHub.
- A production knowledge-release workflow that transfers immutable collection artifacts to the
  selected Qdrant service, verifies manifests/schema/models/qrels, activates aliases only after the
  fixed gates pass, and proves rollback. Application startup continues to perform readiness checks
  only and never fetches sources or generates embeddings.
- An HTTPS deployment at `https://apps.comfforts.com/finance_assistant` behind a Google Cloud load
  balancer and IAP custom External OAuth client, with the owner and explicitly approved Workspace or
  Gmail viewers allow-listed. Plain HTTP redirects to HTTPS; anonymous access and direct workload
  URLs are denied.
- A deployment threat review and release-qualification package covering identity, cross-Principal
  isolation, provider entitlements, file handling, privacy/redaction, retention/deletion,
  backup/restore, availability, capacity, alerting, incident response, DNS/certificate and IAM
  rollback, application/data migration rollback, and collection rollback.

**Dependencies:** Completed M9.1 capability-layout maintenance plus accepted ADR-019 and ADR-029.
The documentation slice creates proposed ADR-030. Application access/isolation requires approval of
the IAP Principal and tenancy model. Managed-state, infrastructure, data-migration, and deployment
slices require the corresponding owner decisions and successful prototypes named in ADR-030. M11
has no dependency on M10, and M10 has no dependency on M11 unless a later decision explicitly adopts
M11 managed persistence for the cash-flow capability.

**Ordered slices and stop gates**

1. Record proposed ADR-030, requirements, design, evaluation, capability ownership, open decisions,
   and promotion/rollback gates. No runtime or cloud control is claimed by this slice.
2. Implement `/finance_assistant`, verified IAP identity, Application Principal mapping, and complete
   per-Principal application authorization. Stop until the two-Principal negative matrix passes.
3. Replace local-only runtime assumptions with selected managed-state, secret, migration, retention,
   readiness, backup/restore, telemetry, and stateless-workload behavior. Stop until recovery and
   privacy tests pass against the real adapter seams.
4. Establish deterministic GitHub CI, artifact provenance, security scanning, Workload Identity
   Federation, and approval boundaries before permitting automated cloud deployment.
5. Provision and validate staging GCP infrastructure through Terraform, including the no-direct-
   workload-bypass boundary, before any production/demo cutover.
6. Transfer, validate, activate, and roll back the versioned Finance and Tax collections in the
   selected production Qdrant topology.
7. Deploy to staging, then configure HTTPS, external DNS, IAP OAuth branding/allow-list, and
   `apps.comfforts.com/finance_assistant`; promote only the pinned qualified revision.
8. Run the integrated security, privacy, recovery, capacity, cost, accessibility, observability, and
   release qualification. Security controls and tests are implemented in every earlier slice; this
   final slice verifies the assembled system rather than adding security after deployment.

Implementation status on 2026-11-10: slices 2 and 4 are implemented. Slice 3's PostgreSQL adapter,
operator configuration, role policy, synthetic migration/recovery/retention harness, recovery
contract, and repeatable operator procedure are implemented and locally qualified, but its real-
service Cloud SQL recovery gate remains pending. The slice 5 Terraform state, registry, WIF,
protected GitHub environments, budget, private network, Cloud SQL, service identities, and empty
regional secret containers are provisioned; the last applied foundation plans were drift-free. The
three digest-pinned private Cloud Run operator jobs are provisioned but not yet executed. Their first
apply failed closed before creating a job because Cloud Run rejected mixed GHCR/GCR container
registries; the obsolete PostgreSQL secret-access bindings were removed as planned. Both image
manifests are now mirrored with unchanged digests into the approved `us-west1` Artifact Registry,
and the corrected Terraform input rejects mixed registries before apply. The corrected plan added
all three jobs without changing or destroying another resource. The recovery wizard then stopped
before any job execution because its post-apply digest inspection used the Terraform API JSON path
instead of the `gcloud` Knative JSON path; the selector is corrected and regression-tested. The
next run installed the reviewed least-privilege grants, then stopped before job execution because
the owner-user delete command supplied a create-only `--type` flag. The exit trap disabled Data API
access, the exact temporary owner user was removed, and both delete paths are corrected and tested.
The initial staging WIF smoke failed closed on a legacy name-only subject condition; the immutable-ID
subject remediation changed only the two providers in place, destroyed nothing, and is drift-free. The staging retry and
production smoke both passed after required review. Real-service recovery, the staging workload,
and no-direct-workload-bypass qualification remain stop gates, so slice 5 is not complete and no
internet-facing workload is claimed operational.

**Owner decisions required before implementation slices**

- Application access/isolation decisions resolved for slice 2: initial owner
  `vtalwar.w@comfforts.com`; owner/viewer/disabled matrix; request-boundary revocation; fixed
  loopback-development owner fixture; empty deployed application store; separate RAG transfer; and
  `/finance_assistant` for local as well as deployed navigation. Viewer live-provider access remains
  denied until ADR-024–026 rights permit it.
- Before managed-state and infrastructure work: identify the GCP organization/project and billing
  owner, preferred region and cost ceiling, selected workload/database/Qdrant/Redis services,
  retention and backup objectives, GitHub environment approvers, and staging/production separation.
  Resolved for implementation: same-project staging in `comfforts-369117`; single-zone Cloud SQL
  PostgreSQL 17 Enterprise `db-f1-micro` with 10 GiB SSD, seven daily backups, and three-day PITR;
  deployed response cache disabled; the documented `us-central1` Qdrant Free exception; regional
  Secret Manager with Google-managed encryption; credential-free deployed providers; USD 100 soft
  monthly budget; and sole public-repository approver `hankgalt` without independent review.
- Before cutover: provide registrar/DNS authority, the final approved-viewer list, OAuth branding and
  public privacy/support URLs, provider modes/entitlements per role, and the maintenance/incident
  contact. Credentials and secret values are supplied only through their approved secret systems,
  never through planning documents or repository files.

**Acceptance:** The internet-facing edge admits only allow-listed Google identities, FastAPI rejects invalid
or bypassed IAP assertions, and two approved viewers cannot read, mutate, stream, resume, inspect,
archive, delete, or infer each other's resources across any product experience. The deployed path
and all generated assets/interfaces work under `/finance_assistant`; direct workload access is
denied. Authoritative state survives restart and controlled rollout, retention/deletion and
backup/restore are enforced, active RAG collections pass the fixed qualification and rollback gates,
provider data is selected and displayed only within recorded rights, and measured capacity/cost/SLO
targets pass. CI/CD deploys a pinned reviewed revision through short-lived identity and supports a
tested application, infrastructure, schema, and collection rollback. No control is called
operational until the deployed evidence passes, and accepting ADR-030 requires the final threat and
release review.

**Tests:** Base-path/static-asset/API/SSE/browser navigation; signed-IAP assertion signature,
issuer/audience/expiry and unsigned-header rejection; owner/viewer/disabled/unknown identities;
cross-Principal matrix tests for every resource and lifecycle operation; guessed identifiers,
idempotency, concurrent Sessions, stream reconnect, Inspector, cache and administrative boundaries;
migration/restart/retention/deletion; backup/restore and disaster rehearsal; Qdrant transfer,
readiness, activation and rollback; Redis/provider/telemetry outage and privacy behavior; Terraform
format/validate/plan/policy and URL-map tests; direct-origin bypass, TLS, headers, CSRF/XSS/SSRF,
malicious imports and prompt injection; container/dependency/secret/IaC scans; staging smoke,
supported-browser accessibility, load/soak, cost/quota/alert, deploy and rollback tests.

**Evidence:** Proposed/accepted ADR-030 history; identity and authorization matrix; data inventory and
threat model; migration and rollback transcripts; Terraform plans and drift checks; CI/CD
attestations and image digests; collection manifests/evaluations/activation records; provider-rights
matrix; backup/restore, load/cost/SLO and incident-response reports; correlated privacy-filtered
telemetry; DNS/TLS/IAP and no-bypass verification; clean staging/production deployment record; known
limitations; and an explicit private multi-user release recommendation. Current artifacts live under
their capability, `backend/artifacts/quality/`, or `backend/artifacts/release/`; milestone delivery
reports link to those single sources of truth.

## 3. Dependency sequence

~~~text
M0 → M1
M0 → M2
M0 → M3
M1 + M2 + M3 → M4
M4 → M4.1 → M5 → M6 → M7 → M6.1
M1–M7 + M4.1 + M6.1 → M8 → M9 → M9.1
M2 + M5 + M6 → M2.1 after M9, independent of M10 and M11
M2 + M5 + M6 → M10 after M9 release approval
M9.1 → M11, independent of M10
~~~

M1, M2, and provider-contract portions of M3 can proceed in parallel after M0 when staffing allows. M7 renders generic persisted RunEvents first. M6.1 later emits response-cache activity through that existing tool-event contract, and M8 independently qualifies both features for release. Evaluation fixtures begin with their owning milestone and are consolidated in M8. No milestone waits until M8 to add its critical tests. M9.1 changes repository ownership after the release without changing product behavior. M10 is a post-release planned enhancement; its provider-independent import path remains useful even if no live banking provider is ever approved.
M11 is a separate production-hardening and deployment track rooted in the M9.1 product-oriented
layout. It may be delivered before or in parallel with M10. Security, isolation, and rollback tests
arrive with their owning M11 slice rather than being deferred to final qualification.

## 4. Mapping from the previous milestone plan

| Previous milestone | Revised milestone(s) | Mapping rationale |
|---|---|---|
| Old M0: scaffold, environment, schemas, logger, tests, CI | New M0 | Preserved; adds explicit Qdrant readiness contract, product/coursework separation, and privacy-safe event schema |
| Old M1: corpus and FAISS ingestion | New M1 | Replaced FAISS with persistent Qdrant; splits Finance/Tax KBs; adds offline versioning, evaluation, activation, rollback, and maintenance |
| Old M2: deterministic finance core | New M2 | Expanded portfolio import/domain separation and reserves the future cash-flow interface |
| Old M3: market abstraction | New M3 | Preserved and expanded to news, licensing, quota, and provenance behavior |
| Old M4: orchestrator plus four agents | New M4 and M4.1 | M4 implements all six bounded agent modules and deterministic contracts; M4.1 qualifies the production LLM adapter so a fake-only graph is not mistaken for the release model path |
| Old M5: News and Tax agents | New M1, M3, M4 | Tax knowledge belongs to M1, news provider to M3, and both agents to M4 |
| Old M6: React views plus Inspector | New M6 and M7 | Separates core product journeys from trace fidelity while retaining their shared UI foundation |
| Old M7: observability/safety/evaluation | New M0/M4 and M8 | Contracts/instrumentation move earlier; integrated qualification remains M8 |
| Previously unsequenced response reuse | New M6.1 and M8 | Adds a bounded evidence-bound cache through the Inspector's generic event seam, then independently qualifies latency, privacy, event truth, and false-hit safety in M8 |
| Old M8: MCP tools | New M9 | Kept as a coursework release obligation after validated core modules |
| Old M9: documentation and demo | New M9 | Preserved and broadened into product release packaging |
| Previously unsequenced PR-016 cash-flow implementation | New M10 | Adds a provider-independent JSON/CSV path after the initial/coursework release while preserving the M2 domain seam |
| Previously unsequenced private multi-user GCP deployment | New M11 | Adds IAP identity, per-Principal authorization, managed infrastructure, production knowledge deployment, CI/CD, and release qualification without depending on or reorganizing around M10 |
| Old M10: optional hybrid retrieval or voice | New M1 evaluation and future backlog | Hybrid retrieval is evaluated as a retrieval strategy, not bonus theater; voice remains out of initial scope |

## 5. Release sequencing and stop conditions

The **initial product release** requires M0 through M8, including M4.1 and M6.1, plus the product documentation and packaging portions of M9. It is released only as a private demonstration release. The **coursework release** additionally requires the submission-specific portions of M9, including MCP unless authoritative clarification removes it. M10 is the independent post-release cash-flow implementation and does not require a banking-data provider. M11 is the independent post-release private multi-user deployment and production-hardening track. Neither M10 nor M11 delays the other; anonymous public availability remains out of scope unless separately approved.

Stop a milestone when a critical dependency, source-use right, data-integrity policy, security decision, or external authority is missing. Record the blocker rather than substituting invented data, bypassing a gate, or weakening the requirement. Near-complete work is not milestone completion.
