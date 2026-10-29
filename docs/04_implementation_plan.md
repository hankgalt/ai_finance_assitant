# AI Finance Assistant — Incremental implementation plan

Version 2.3 | Status: Approved sequence; M0–M6 complete; M7 and later milestones planned | 2026-10-29

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

- Versioned REST resources for Sessions, chat Runs, Portfolios/import validation, Portfolio Snapshots, market queries, goal projections, and authorized trace history.
- SSE for conversational chunks and RunEvents with documented replay or REST recovery.
- Durable local adapters for checkpoints, saved portfolios, run summaries/events, and deletion; idempotency for artifact-creating requests.
- An application-owned durable provider-cache port and relational adapter for normalized historical daily bars, with a bounded memory front cache, range-coverage and gap detection, recent-tail revalidation, provider/schema/policy isolation, concurrent-request deduplication, and administrative purge. Current quotes and news retain short endpoint-specific lifecycles unless separately approved.
- OpenAPI-driven or contract-verified frontend types and readiness for storage/Qdrant/providers.
- FastAPI and outbound-client OpenTelemetry instrumentation with W3C trace-context propagation; JSON logs enriched with trace, span, request, execution, and Run identifiers when available.
- OTLP/Collector configuration for enabled signals, with backend request/error/latency, provider/retrieval timing, retry/rate-limit, cache, and persistence metrics using bounded low-cardinality attributes.

**Dependencies:** M1–M4.1. ADR-026 validation must select the concrete local relational store and record provider-specific refresh, retention, migration, and risk-acceptance behavior before implementation.

**Acceptance:** REST is authoritative; reconnect deduplicates events; cross-session reads/streams fail; restart behavior matches configured retention; deletion removes defined user artifacts; partial and not-ready states use stable errors; inbound and outbound trace context correlates with logs and RunEvents; telemetry remains non-blocking and no metric label or exported attribute exposes protected or unbounded identifiers. A complete, fresh historical range survives restart without a provider call; an overlapping or partially stale request fetches only missing/provider-approved refresh coverage; stored observations never cross provider, adjustment, currency, or schema/policy boundaries; and every response truthfully distinguishes memory hit, durable hit, partial hit, stale, and unavailable states. Owner-only unverified-rights retention requires explicit local risk acceptance and cannot pass shared-demo or public-deployment readiness.

**Tests:** OpenAPI snapshots/contracts, REST/SSE framing, last-event/recovery behavior, concurrent Runs, authorization scope, restart, idempotency, deletion, migration, CORS/local bind, resource limits, W3C context propagation, log/trace correlation, metric cardinality, health-endpoint exclusion, and unavailable Collector/exporter behavior. Provider-cache tests cover exact and overlapping ranges, gap-only fetches, recent-tail refresh, stale fallback, no-call restart reuse, concurrent request coalescing, provider/currency/adjustment/schema isolation, malformed or migrated rows, purge, retention expiry, and owner-only versus shared/public rights gates.

**Evidence:** [M5 delivery report](M5_delivery_report.md), interface specification, migration records, contract test report, SSE transcript, lifecycle/isolation evidence, provider call-count and restart-reuse transcripts, cache schema and purge record, retention/rights configuration, correlated FastAPI/module trace sample, metric inventory, Collector/exporter configuration, and documented local security posture.

### M6 — React product experiences

**Deliverables**

- Conversational Assistant, Portfolio Dashboard, Market Overview, and Goal Planning views.
- Manual/JSON/CSV/XLSX portfolio flows with validation review and no silent corrections.
- TanStack Query integration, Recharts visuals and accessible tables, citations/provenance, freshness, coverage, and assumption displays.
- Responsive, keyboard-accessible loading, empty, partial, success, stale, and failure states.
- Privacy-safe frontend telemetry module for error-boundary events, Web Vitals, navigation, and API timing/failure categories, with W3C trace context and request correlation propagated to FastAPI.
- First-party telemetry transport or protected Collector adapter; no LangSmith, provider, or telemetry credential is shipped to the browser, and telemetry contains no prompt or financial payload content.

**Dependencies:** M5 interfaces and deterministic backend fixtures.

**Acceptance:** Users complete core workflows without developer tools; UI never performs authoritative calculations or leaks credentials; chart/tabular values match backend resources; refresh/reconnect preserves intended state; frontend failures correlate to backend traces when sampled; disabled or failed telemetry has no user-visible functional effect.

**Tests:** Component tests, API mock contracts, Playwright user journeys, keyboard/focus/semantic/contrast checks, responsive layouts, network failure and stale data, import error correction, error-boundary and Web-Vitals emission, trace/request-header propagation, payload redaction, CSP/CORS behavior, and unavailable telemetry transport.

**Evidence:** [M6 delivery report](M6_delivery_report.md), browser-test report, accessibility review, screenshots for representative states, contract-version record, privacy-safe frontend telemetry sample, and browser-to-FastAPI correlation record under `docs/evidence/m6/`.

### M7 — Agent Execution Inspector

**Deliverables**

- Authorized Run selector, execution timeline, details panel, and React Flow path visualization backed by M4/M5 events.
- Display of routing, status, measured timing, safe tool/result metadata, retrieval sources, and tokens/cost where available.
- Explicit “not available” states and clearly distinct static workflow-design overlays if used.
- Event deduplication, out-of-order handling, reconnect behavior, and accessible list alternative.
- Authorized correlation identifiers sufficient to locate the corresponding operational or LangSmith trace when configured; the Inspector continues to render only persisted RunEvents and never queries an external trace backend as its source of truth.

**Dependencies:** M4 instrumentation, M5 history/SSE, M6 shared UI.

**Acceptance:** Every dynamic node and edge resolves to recorded events; failures/partial paths are truthful; synthetic fixtures are labeled; raw financial records, credentials, hidden reasoning, prompts, and unsafe payloads never render.

**Tests:** Synthetic and actual runs, event-to-graph reconciliation, duplicate/out-of-order streams, missing measurements, failed/skipped nodes, multi-run/session isolation, redaction, keyboard and screen-reader flows.

**Evidence:** Fixture versions, backend/Inspector comparison report, screenshots of success/partial/failure, and redaction assertions.

### M8 — Evaluation, security, observability, and reliability

**Deliverables**

- Versioned evaluation datasets and runner covering every dimension in [evaluation strategy](05_evaluation_strategy.md).
- Privacy/security threat review, prompt-injection suite, safe-file suite, and session/access audit.
- Reliability tests for providers, Qdrant, persistence, retries, load bounds, and restart.
- Measured routing/retrieval/grounding/arithmetic/portfolio/import/citation/tax-year/UI/Inspector/latency/cost reports.
- End-to-end observability qualification across browser, FastAPI, deterministic modules, providers/retrieval, LangGraph, and RunEvent persistence, including sampling, correlation, redaction, retention, metric cardinality, and exporter backpressure/outage behavior.
- Operational runbooks for local failures and explicit production-hardening gap register.

**Dependencies:** M1–M7 feature-complete candidate.

**Acceptance:** All critical release gates pass; no critical financial arithmetic, access, leakage, citation, or trace-fidelity defect remains open; metrics include configuration and unavailable values; a sampled request can be reconciled across frontend telemetry, backend spans/logs, LangSmith when enabled, and the authoritative RunEvent record; collector/exporter loss cannot corrupt or block product state; any noncritical exception has owner, rationale, and expiry.

**Tests:** Full regression, adversarial, integration, browser, accessibility, benchmark, soak/concurrency within initial scale, clean-environment suite, sensitive-field canaries, sampling/retention, missing-parent/partial-trace handling, high-cardinality rejection, and Collector/LangSmith outage tests.

**Evidence:** Immutable evaluation bundle, coverage report, threat model, dependency scan, benchmark/cost report, observability data-flow diagram, signal/attribute inventory, correlated cross-tier trace, redaction and exporter-failure reports, known-risk register, and release recommendation.

### M9 — Product documentation, coursework packaging, demonstration, and release

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

## 3. Dependency sequence

~~~text
M0 → M1
M0 → M2
M0 → M3
M1 + M2 + M3 → M4
M4 → M4.1 → M5 → M6 → M7
M1 through M7 → M8 → M9
M2 + M5 + M6 → M10 after M9 release approval
~~~

M1, M2, and provider-contract portions of M3 can proceed in parallel after M0 when staffing allows. Evaluation fixtures begin with their owning milestone and are consolidated in M8. No milestone waits until M8 to add its critical tests. M10 is a post-release planned enhancement; its provider-independent import path remains useful even if no live banking provider is ever approved.

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
| Old M8: MCP tools | New M9 | Kept as a coursework release obligation after validated core modules |
| Old M9: documentation and demo | New M9 | Preserved and broadened into product release packaging |
| Previously unsequenced PR-016 cash-flow implementation | New M10 | Adds a provider-independent JSON/CSV path after the initial/coursework release while preserving the M2 domain seam |
| Old M10: optional hybrid retrieval or voice | New M1 evaluation and future backlog | Hybrid retrieval is evaluated as a retrieval strategy, not bonus theater; voice remains out of initial scope |

## 5. Release sequencing and stop conditions

The **initial product release** requires M0 through M8, including M4.1, plus the product documentation and packaging portions of M9. It is released only as a private demonstration release. The **coursework release** additionally requires the submission-specific portions of M9, including MCP unless authoritative clarification removes it. M10 is the planned post-release cash-flow implementation; it does not delay either release and does not require a banking-data provider. Public availability and remaining production-hardening controls stay out of scope until separately approved.

Stop a milestone when a critical dependency, source-use right, data-integrity policy, security decision, or external authority is missing. Record the blocker rather than substituting invented data, bypassing a gate, or weakening the requirement. Near-complete work is not milestone completion.
