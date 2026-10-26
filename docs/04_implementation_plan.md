# AI Finance Assistant — Incremental implementation plan

Version 1.0 | Status: Approved sequence, implementation not started by this document | 2026-10-26

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

Cash flow remains a planned enhancement: M2 reserves and tests its interface shape only. The initial release prioritizes investment portfolios and complete behavior for all six agents.

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

**Evidence:** M0 delivery report, command log, generated schema snapshot, screenshots of labeled empty/synthetic states. The bounded implementation prompt is [06_codex_starting_prompt.md](06_codex_starting_prompt.md).

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

**Evidence:** Source manifest, permitted-use review notes, collection manifest/checksums, evaluation report, activation record, and rollback transcript. Coursework corpus counts are reported separately without padding.

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

**Evidence:** Calculation policy/version, hand-worked golden cases, sample-data manifest, test and coverage reports, documented heuristic limitations.

### M3 — External market and news integrations

**Deliverables**

- MarketDataProvider and NewsProvider ports with selected production and fake adapters.
- Standard provenance/freshness envelopes, provider-specific rate limits, bounded cache, timeouts, retry/jitter, and circuit behavior.
- Current/historical quote and dated-news retrieval suitable for the Market and News agents.
- Provider license, entitlement, and fallback decision record updates.

**Dependencies:** M0 contracts; selected providers and accepted data terms. Portfolio enrichment consumes M2 interfaces.

**Acceptance:** Success, delay, cache, stale, rate-limit, invalid-symbol/query, malformed-payload, and unavailable behavior are observable and correctly labeled; mock/demo results cannot appear as live.

**Tests:** Adapter contracts using recorded permitted fixtures or fakes; 401/403, 429, timeout, malformed data, cache expiry, provider fallback, provenance timestamp, and concurrency/quota cases.

**Evidence:** Provider decision update, contract fixtures, failure matrix, cache/rate configuration, actual test report, and cost/limit notes.

### M4 — LangGraph orchestration and all six agents

**Deliverables**

- Versioned FinanceState, router, bounded conditional graph, synthesis/validation, and checkpoint interfaces.
- Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, and Tax Education agents with the exact §3 responsibilities.
- Finance and Tax retrieval; M2 calculations; M3 providers; multi-agent composition without recursive agent calls.
- Actual RunEvent instrumentation for routes, nodes, retrieval, tools/providers, models, and terminal state.

**Dependencies:** M1–M3.

**Acceptance:** Each agent passes distinct domain cases; labeled requests route correctly; Finance/Tax cite Run evidence; Portfolio/Goal use deterministic outputs; multi-agent results preserve domain boundaries; restart/follow-up and partial failures behave as designed; event sequences match graph execution.

**Tests:** Labeled single/multi-intent routing, agent contract suites, collaboration, hop/deadline bounds, citation and tax-year correctness, prompt injection, malformed model output, checkpoint restart/isolation, event ordering and redaction.

**Evidence:** Six-agent behavior report, route confusion matrix, captured privacy-filtered traces, actual graph diagrams, and failure examples.

### M5 — FastAPI integration and persistence

**Deliverables**

- Versioned REST resources for Sessions, chat Runs, Portfolios/import validation, Portfolio Snapshots, market queries, goal projections, and authorized trace history.
- SSE for conversational chunks and RunEvents with documented replay or REST recovery.
- Durable local adapters for checkpoints, saved portfolios, run summaries/events, and deletion; idempotency for artifact-creating requests.
- OpenAPI-driven or contract-verified frontend types and readiness for storage/Qdrant/providers.

**Dependencies:** M1–M4.

**Acceptance:** REST is authoritative; reconnect deduplicates events; cross-session reads/streams fail; restart behavior matches configured retention; deletion removes defined user artifacts; partial and not-ready states use stable errors.

**Tests:** OpenAPI snapshots/contracts, REST/SSE framing, last-event/recovery behavior, concurrent Runs, authorization scope, restart, idempotency, deletion, migration, CORS/local bind, and resource limits.

**Evidence:** Interface specification, migration records, contract test report, SSE transcript, lifecycle/isolation evidence, and documented local security posture.

### M6 — React product experiences

**Deliverables**

- Conversational Assistant, Portfolio Dashboard, Market Overview, and Goal Planning views.
- Manual/JSON/CSV/XLSX portfolio flows with validation review and no silent corrections.
- TanStack Query integration, Recharts visuals and accessible tables, citations/provenance, freshness, coverage, and assumption displays.
- Responsive, keyboard-accessible loading, empty, partial, success, stale, and failure states.

**Dependencies:** M5 interfaces and deterministic backend fixtures.

**Acceptance:** Users complete core workflows without developer tools; UI never performs authoritative calculations or leaks credentials; chart/tabular values match backend resources; refresh/reconnect preserves intended state.

**Tests:** Component tests, API mock contracts, Playwright user journeys, keyboard/focus/semantic/contrast checks, responsive layouts, network failure and stale data, import error correction.

**Evidence:** Browser-test report, accessibility review, screenshots/video for each state, and contract-version record.

### M7 — Agent Execution Inspector

**Deliverables**

- Authorized Run selector, execution timeline, details panel, and React Flow path visualization backed by M4/M5 events.
- Display of routing, status, measured timing, safe tool/result metadata, retrieval sources, and tokens/cost where available.
- Explicit “not available” states and clearly distinct static workflow-design overlays if used.
- Event deduplication, out-of-order handling, reconnect behavior, and accessible list alternative.

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
- Operational runbooks for local failures and explicit production-hardening gap register.

**Dependencies:** M1–M7 feature-complete candidate.

**Acceptance:** All critical release gates pass; no critical financial arithmetic, access, leakage, citation, or trace-fidelity defect remains open; metrics include configuration and unavailable values; any noncritical exception has owner, rationale, and expiry.

**Tests:** Full regression, adversarial, integration, browser, accessibility, benchmark, soak/concurrency within initial scale, and clean-environment suite.

**Evidence:** Immutable evaluation bundle, coverage report, threat model, dependency scan, benchmark/cost report, known-risk register, and release recommendation.

### M9 — Product documentation, coursework packaging, demonstration, and release

**Deliverables**

- User/developer/operator documentation, diagrams, source/license register, sample-data guide, and clean-start instructions.
- Read-only MCP adapter and client setup/evidence if CA-13 remains required.
- Coursework evidence matrix, 5–10 minute demonstration script/recording plan, and React/Qdrant substitution rationale.
- Product release notes, limitation/disclaimer review, collection and schema versions, rollback instructions, and signed completion checklist.

**Dependencies:** M8 release recommendation and authoritative coursework confirmation where obtainable.

**Acceptance:** Product gate: a clean environment reproduces the documented release, every initial product requirement has evidence or an explicitly approved exception, and no planned enhancement or production control is claimed complete. Coursework gate: CA-01 through CA-13 have evidence or an approved instructor clarification, demo paths work with stable fixtures, and optional live calls are separately labeled.

**Tests:** Clean install/start, documentation link/command validation, packaged sample walkthrough, MCP protocol/client test, evidence-path audit, and final regression.

**Evidence:** Release bundle, exact environment/command log, requirement-to-evidence matrix, demonstration artifact, MCP record, known limitations, and approval.

## 3. Dependency sequence

~~~text
M0 → M1
M0 → M2
M0 → M3
M1 + M2 + M3 → M4
M4 → M5 → M6 → M7
M1 through M7 → M8 → M9
~~~

M1, M2, and provider-contract portions of M3 can proceed in parallel after M0 when staffing allows. Evaluation fixtures begin with their owning milestone and are consolidated in M8. No milestone waits until M8 to add its critical tests.

## 4. Mapping from the previous milestone plan

| Previous milestone | Revised milestone(s) | Mapping rationale |
|---|---|---|
| Old M0: scaffold, environment, schemas, logger, tests, CI | New M0 | Preserved; adds explicit Qdrant readiness contract, product/coursework separation, and privacy-safe event schema |
| Old M1: corpus and FAISS ingestion | New M1 | Replaced FAISS with persistent Qdrant; splits Finance/Tax KBs; adds offline versioning, evaluation, activation, rollback, and maintenance |
| Old M2: deterministic finance core | New M2 | Expanded portfolio import/domain separation and reserves the future cash-flow interface |
| Old M3: market abstraction | New M3 | Preserved and expanded to news, licensing, quota, and provenance behavior |
| Old M4: orchestrator plus four agents | New M4 | All six agents now complete together so partial staging is not mistaken for the target architecture |
| Old M5: News and Tax agents | New M1, M3, M4 | Tax knowledge belongs to M1, news provider to M3, and both agents to M4 |
| Old M6: React views plus Inspector | New M6 and M7 | Separates core product journeys from trace fidelity while retaining their shared UI foundation |
| Old M7: observability/safety/evaluation | New M0/M4 and M8 | Contracts/instrumentation move earlier; integrated qualification remains M8 |
| Old M8: MCP tools | New M9 | Kept as a coursework release obligation after validated core modules |
| Old M9: documentation and demo | New M9 | Preserved and broadened into product release packaging |
| Old M10: optional hybrid retrieval or voice | New M1 evaluation and future backlog | Hybrid retrieval is evaluated as a retrieval strategy, not bonus theater; voice remains out of initial scope |

## 5. Release sequencing and stop conditions

The **initial product release** requires M0 through M8 plus the product documentation and packaging portions of M9. The **coursework release** additionally requires the submission-specific portions of M9, including MCP unless authoritative clarification removes it. Cash-flow end-user implementation and all production-hardening controls remain later work.

Stop a milestone when a critical dependency, source-use right, data-integrity policy, security decision, or external authority is missing. Record the blocker rather than substituting invented data, bypassing a gate, or weakening the requirement. Near-complete work is not milestone completion.
