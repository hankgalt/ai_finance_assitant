# AI Finance Assistant — Product requirements specification

Version 1.0 | Status: Product architecture baseline | 2026-10-26

## 1. Mission and product posture

AI Finance Assistant provides an intelligent, trustworthy, and accessible financial education and analysis platform that helps individuals understand financial concepts, analyze investments, evaluate financial goals, and make more informed financial decisions.

The initial release serves U.S. users and U.S. financial markets. It provides education, analytical tools, and hypothetical planning scenarios. It does not represent itself as a licensed financial, investment, legal, or tax adviser; execute transactions; file taxes; or guarantee outcomes.

Product requirements are defined here. Submission-specific obligations are defined separately in [Coursework acceptance criteria](coursework_acceptance_criteria.md) and remain mandatory for the coursework release.

## 2. Users, scope, and release labels

Primary users are individuals learning financial concepts, beginner-to-intermediate investors reviewing self-entered portfolios, and people exploring savings or investment goal scenarios. The product should explain terminology and uncertainty without assuming professional expertise.

The **initial release** includes all six agents, persistent knowledge retrieval, portfolio analysis, goal projections, market and news integrations, the React application, FastAPI integration, and the Agent Execution Inspector. **Production hardening** requirements apply before public multi-user deployment. Personal cash flow is a **planned enhancement** with a stable interface designed during the initial release but no required end-user implementation.

## 3. Product functional requirements

| ID | Release | Requirement | Acceptance summary |
|---|---|---|---|
| PR-001 | Initial | Provide exactly six specialist agents with the responsibilities and interaction limits in system design §3 | Each agent has typed inputs/outputs, allowed tools, failure modes, and distinct behavior tests |
| PR-002 | Initial | Orchestrate requests with LangGraph, support correct single- and multi-agent routing, bounded execution, synthesis, and follow-up context | Labeled routing, collaboration, bounded-hop, checkpoint, and partial-result tests pass |
| PR-003 | Initial | Accept structured portfolios by manual entry and JSON, CSV, or XLSX import; preserve imported fields separately from provider enrichment and calculations | Validation reports row/field errors, duplicates, and missing values without inventing data; supplied samples import reproducibly |
| PR-004 | Initial | Retrieve current and historical U.S. market information through provider adapters and expose provenance and freshness | Results include provider and timestamps; stale, delayed, cached, limited, and unavailable states are explicit |
| PR-005 | Initial | Calculate hypothetical goals using starting value, recurring contributions, horizon, inflation, declared resources/risk tolerance, and user-controlled return scenarios | A deterministic module produces reproducible nominal and inflation-aware results; all assumptions are visible |
| PR-006 | Initial | Retrieve and summarize financial news with publisher, publication timestamp, link, fact/interpretation distinction, and relevant market context | News remains attributed and is never presented as a reliable price predictor |
| PR-007 | Initial | Provide U.S. federal tax education grounded in year-specific authoritative content | Responses include tax year, jurisdiction, citations, limitations, and professional-advice framing where appropriate |
| PR-008 | Initial | Maintain separate Finance Education and Tax Education knowledge bases in persistent Qdrant collections through an offline, versioned ingestion workflow | Startup connects to and validates an active collection; it never regenerates embeddings |
| PR-009 | Initial | Perform portfolio valuations, allocations, expense analysis, concentration and diversification heuristics, and goal arithmetic in deterministic Python modules | Golden, property, and missing-data tests pass; agents only interpret returned results |
| PR-010 | Initial | Provide a React/TypeScript application with Conversational Assistant, Portfolio Dashboard, Market Overview, Goal Planning, and Agent Execution Inspector experiences | Each experience has accessible loading, empty, success, partial, and failure states and communicates through FastAPI |
| PR-011 | Initial | Stream conversational and measured execution events where appropriate while keeping ordinary operations on versioned REST interfaces | OpenAPI and event contract tests pass; reconnection never mixes sessions or duplicates rendered events |
| PR-012 | Initial | Visualize actual LangGraph execution through an accessible timeline, details view, and React Flow graph | Every dynamic node maps to a recorded event; unavailable measurements are labeled; sensitive material is redacted |
| PR-013 | Initial | Persist conversation checkpoints, run summaries, active knowledge collection metadata, and necessary user artifacts according to documented retention modes | Restart and session-isolation behavior is tested; local-demo limitations are visible |
| PR-014 | Initial | Provide sample datasets, reproducible local development, product documentation, evaluation artifacts, and release instructions | A clean-environment verification record identifies exact commands, versions, results, and limitations |
| PR-015 | Coursework release | Expose approved read-only capabilities through MCP using the same validation and deterministic modules as the web application | Protocol and external-client tests demonstrate no bypass of authorization, validation, or provenance |
| PR-016 | Planned enhancement | Add personal cash flow analysis as a deterministic domain module available to authorized agents, not as a seventh LLM agent | The interface supports normalized transaction imports and goal summaries without changing existing agent identities |

## 4. Six-agent product contract

The definitive per-agent interfaces are in system design §3. At the requirement level:

- **Finance Q&A** teaches financial literacy, terminology, products, asset classes, risk, diversification, and general personal finance using Finance Education RAG.
- **Portfolio Analysis** validates portfolios, enriches instruments, invokes deterministic analysis, and explains valuation coverage, concentration, expenses, uncertainty, and stale or missing inputs.
- **Market Analysis** retrieves current and historical quotations, describes price movement and market statistics, and exposes provider provenance and freshness without forecasting guarantees.
- **Goal Planning** defines goals and invokes deterministic contribution, compounding, inflation, and multi-scenario projections. It may consume portfolio and future cash-flow summaries but remains separate from Market Analysis.
- **News Synthesizer** retrieves and attributes financial news, distinguishes reported facts from interpretation, and connects developments to a user question without predicting prices.
- **Tax Education** explains U.S. federal investment taxation and retirement-account concepts using Tax Education RAG filtered by applicable year and jurisdiction; it does not give individualized tax advice.

An agent may request another agent only through the orchestrator. Agents must not call each other recursively or duplicate another agent’s domain authority.

## 5. Portfolio domain and import requirements

### 5.1 Imported user data

A Portfolio has a portfolio identifier, optional user label, base currency, one or more Accounts, and an import timestamp. Each Account has an account identifier, account type, optional institution label, and Holdings. Each Holding has:

- holding identifier and account identifier;
- at least one security identifier appropriate to the instrument, such as ticker, CUSIP, ISIN, or an explicit user-defined identifier;
- quantity and currency;
- optional user-declared asset class;
- optional total or per-unit cost basis with acquisition date or lot detail when supplied;
- optional user-supplied price, price timestamp, and provenance label;
- optional expense ratio and sector classification;
- explicit unknown values rather than placeholder zeroes.

User-defined identifiers need not be globally meaningful. The import record retains original values and source row references for error reporting.

### 5.2 Provider enrichment and calculated results

Provider-enriched security information is a separate record keyed to a Holding. It can contain canonical identifiers, name, verified asset class, sector, trading currency, expense ratio, current price, price timestamp, retrieval timestamp, provider, delay state, and cache state.

Calculated metrics form a time-specific Portfolio Snapshot and include per-holding value, total value, allocation, coverage ratios, asset and sector concentration where supported, weighted expense ratios with coverage, diversification heuristics, and warnings. Calculations must identify which price snapshot and enrichment records they used.

Conflicts between user data and provider data are reported with provenance. Provider information does not silently overwrite imported data.

### 5.3 Validation

Manual, JSON, CSV, and XLSX paths apply the same domain validation. Validation must:

- reject invalid encodings, unsupported file types, unsafe formulas/macros, nonfinite numbers, negative quantities unless an approved short-position model exists, and missing required fields;
- enforce documented limits on file size, row count, text length, and decompression;
- normalize headers and supported identifier formats without changing source evidence;
- detect duplicate rows and likely duplicate Holdings using documented keys, report them, and require an explicit merge decision;
- report file-, row-, and field-level errors together when safe rather than failing one row at a time;
- distinguish fatal errors, accepted warnings, unsupported instruments, missing prices, currency gaps, and partial valuation coverage;
- never synthesize quantities, prices, cost bases, expense ratios, sectors, or account types.

Versioned sample datasets must cover valid multi-account input, duplicate rows, missing optional fields, unknown securities, mixed currencies, stale prices, and malformed content.

## 6. Knowledge requirements

### 6.1 Logical knowledge bases

**Finance Education KB** may use SEC Investor.gov, FINRA investor resources, CFPB education, and permitted supplementary sources such as Bogleheads Wiki or independently written glossary material.

**Tax Education KB** prioritizes IRS Publications 550, 590-A, 590-B, and 17, plus applicable IRS forms and official guidance. Tax records require tax-year and jurisdiction metadata; prior tax years remain available for historical questions.

The source registry records publisher, canonical URL, retrieval method, ownership or permitted-use notes, effective dates, review cadence, content hash, and status. The project must not assume bulk redistribution rights for copyrighted third-party material.

### 6.2 Offline ingestion and activation

Ingestion is separate from application startup and follows the ten-step workflow in system design §7: discover/register, fetch, extract/normalize, validate, detect changes/duplicates, chunk, represent, persist, evaluate, and activate. It supports idempotent processing, incremental re-indexing, document versions, source hashes, collection versions, and rollback.

Application startup connects to existing active collections and checks expected payload schema, dense and sparse representation versions, embedding model identifiers, and collection readiness. A missing or incompatible collection produces a not-ready state rather than an implicit rebuild.

### 6.3 Retrieval

Retrieval supports semantic search, metadata filters, attribution, relevance thresholds, dense/sparse hybrid search, and Reciprocal Rank Fusion where evaluation justifies it. Query planning chooses the least expensive strategy that meets the need; hybrid retrieval is not mandatory for every query. A fixed, versioned test set evaluates each proposed collection before activation.

Maintenance policy:

- financial fundamentals: quarterly human content review;
- investment-product and regulatory guidance: monthly source-change checks;
- tax publications and guidance: monthly checks plus event-driven review after material guidance changes;
- changed content: incremental validation and re-indexing;
- embedding or sparse-model changes: versioned rebuild, comparative evaluation, then explicit activation.

A source-change check that finds no content change does not trigger re-embedding.

## 7. Planned CashFlowAnalysisService

The planned CashFlowAnalysisService is a deterministic module, not an agent. Its future interface accepts versioned bank-transaction and credit-card CSV imports and returns normalized transactions, categorization with confidence/override state, income and spending summaries, detected recurring expenses, reconciled transfers and card payments, monthly surplus, trends, coverage, and warnings.

The initial design must allow Goal Planning to consume an authorized cash-flow summary without exposing raw transactions to unrelated agents. Transfer reconciliation must prevent double-counting across accounts. The initial release does not implement live banking connections, automated transfers or trades, or PDF statement extraction. Those require separate approval and threat modeling.

## 8. Product quality requirements

| ID | Initial-release requirement | Production-hardening extension | Verification |
|---|---|---|---|
| QR-001 Privacy and minimization | Collect only fields needed for the requested analysis; keep raw records out of prompts, traces, and logs unless strictly required and sanitized | Formal data inventory, privacy notice, purpose/consent controls, regional review | Log/trace inspection and data-flow tests |
| QR-002 Secure file handling | Type/size/row limits, isolated parsing, formula neutralization, safe temporary-file cleanup, and no execution of embedded content | Malware scanning, encrypted object storage, quarantine, abuse monitoring | Malicious and oversized fixture tests |
| QR-003 Authentication/authorization | Local demo binds to an explicitly local interface and is labeled unauthenticated; access to a Session or Portfolio is scoped by unguessable identifiers and server checks | Identity provider, strong authentication, per-resource authorization, administrative roles | Negative authorization and cross-session tests |
| QR-004 Session isolation | State, streams, caches, checkpoints, and traces are keyed and checked by user/session context | Tenant isolation review and penetration testing | Concurrent two-session regression suite |
| QR-005 Secrets | Secrets come from environment or an approved local secret mechanism and are redacted from errors and traces | Managed secret store, rotation, least-privilege credentials | Repository scan and forced-error tests |
| QR-006 Retention/deletion | Define local retention per artifact; support deletion of imported files, normalized records, sessions, runs, and traces; knowledge provenance is retained independently | User-facing export/deletion workflow, retention enforcement jobs, legal-policy review | Lifecycle and deletion tests |
| QR-007 Observability/auditability | Structured correlation, routing, provider/retrieval provenance, failure, latency, and measured usage events without hidden reasoning or raw financial records | Centralized access-controlled logs, alerting, audit retention, tamper controls | Trace-schema, redaction, and incident fixture tests |
| QR-008 Retrieval quality | Fixed qrels, relevance thresholds, valid citations, collection/version reporting, and explicit no-evidence behavior | Drift monitoring and reviewed activation workflow | Recall/ranking/citation and historical-year tests |
| QR-009 Calculation accuracy | Decimal or a documented numerical representation, explicit rounding/currency policy, deterministic results, and 100% pass on approved golden cases | Independent financial-model validation and change control | Golden, property, metamorphic, and edge tests |
| QR-010 Reliability | Typed failures, bounded retries with jitter, timeouts, idempotent writes, partial results, and no unlabeled fallback data | Availability objectives, durable queues where needed, disaster recovery and load testing | Timeout, retry, duplicate, restart, and partial-result tests |
| QR-011 Provider limits/caching | Provider-specific rate policy, bounded caches, provenance and freshness, and circuit behavior | Distributed quota coordination and contractual data entitlements | 429, stale-cache, invalid-data, and outage tests |
| QR-012 LLM quality and safety | Versioned prompts/models, structured results, grounding checks, tool allow-lists, bounded steps, prompt-injection treatment of external text as data, and financial safety review | Continuous red-team program, model-risk governance, abuse controls | Labeled routing/grounding/injection/advice suite |
| QR-013 Accessibility | WCAG 2.2 AA design target; keyboard access, semantic labels, focus management, contrast, and nonvisual tables for charts/graphs | Formal accessibility audit with assistive technologies | Automated checks plus keyboard/screen-reader review |
| QR-014 Performance/cost | Record p50/p95 task latency, provider/cache timing, tokens and estimated cost when supplied; show “not available” otherwise | Calibrated objectives, capacity tests, budgets and alerts | Versioned benchmark report |
| QR-015 Reproducibility | Pinned tools/dependencies, deterministic fixtures, documented setup, mock mode, migration and collection version checks | Reproducible deployment artifacts and supply-chain controls | Clean-environment run and artifact hashes |

## 9. Core acceptance scenarios

| ID | Scenario and expected behavior |
|---|---|
| EV-01 | “What is an ETF?” routes to Finance Q&A, retrieves Finance KB evidence, and cites it |
| EV-02 | “Compare ETFs with stocks and explain tax differences” coordinates Finance Q&A and Tax Education without merging jurisdictions or years |
| EV-03 | A valid multi-account import produces exact values and allocation; a missing price produces partial coverage, not a fabricated value |
| EV-04 | Duplicate or malformed JSON/CSV/XLSX rows produce actionable row/field errors and no silent merge |
| EV-05 | “What changed in AAPL today?” produces timestamped provider data or an explicit stale/unavailable response |
| EV-06 | A $500 monthly goal over 15 years produces reproducible scenarios with nominal, inflation, and contribution assumptions |
| EV-07 | News about portfolio holdings remains dated and attributed and does not claim predictive power |
| EV-08 | A historical tax question selects the requested tax year and retains an authoritative citation |
| EV-09 | A provider failure yields bounded retries and a labeled partial result; fallback data is never presented as live |
| EV-10 | Malicious instructions in a document, import, or news item remain untrusted data and cannot expand tool authority |
| EV-11 | Concurrent Sessions cannot access each other’s portfolio, answer, checkpoint, stream, or trace |
| EV-12 | The Inspector’s timeline and graph match recorded events, handle reconnect/deduplication, and redact protected fields |
| EV-13 | Startup with an absent or incompatible Qdrant collection reports not ready without embedding documents |
| EV-14 | A collection update re-indexes only changed documents, passes fixed retrieval evaluation, activates atomically, and can roll back |
| EV-15 | Deleting a local user artifact removes its defined stored forms without deleting the independent source registry |

## 10. Out of scope without separate approval

Brokerage execution, automated financial transactions, custody, bank aggregation or live banking connections, personalized security buy/sell instructions, tax return preparation or filing, guaranteed real-time market data, PDF statement extraction, non-U.S. tax guidance, autonomous browsing beyond approved sources, voice, and public multi-tenant deployment are outside the initial release.

## 11. Traceability

| Requirements | Decisions/design | Milestones | Evaluation |
|---|---|---|---|
| PR-001–PR-002 | ADR-001/002; design §2–3 | M4 | EV-01/02, routing and collaboration suites |
| PR-003, PR-009 | ADR-009/018; design §5–6 | M2, M6 | EV-03/04, arithmetic and import suites |
| PR-004, PR-006 | ADR-006; design §9 | M3–M4 | EV-05/07/09 |
| PR-005 | ADR-009; design §6 | M2, M6 | EV-06 |
| PR-007–PR-008 | ADR-016/017; design §7–8 | M1, M4 | EV-01/02/08/13/14 |
| PR-010–PR-012 | ADR-007/013/014/015; design §10–11 | M5–M7 | EV-12 and browser/contract suites |
| PR-013 | ADR-003/019; design §12 | M0, M5, M8 | EV-11/15 |
| PR-014 | ADR-011; docs index | M8–M9 | clean-environment and product release audit |
| PR-015 | ADR-010; coursework criteria | M9 | MCP protocol/client and coursework evidence |
| PR-016 | ADR-020; design §13 | Interface in M2; implementation later | future cash-flow contract and reconciliation suite |
| QR-001–QR-015 | ADR-011/012/019; design §12 | Every milestone; consolidated M8 | security, quality, reliability, and benchmark suites |

## 12. Resolved conflicts and open decisions

Resolved architectural conflicts:

- The product is an extensible financial education and analysis platform; the capstone is a release obligation.
- Qdrant replaces the proposed FAISS-first architecture.
- Goal Planning and Market Analysis remain separate agent responsibilities.
- Cash flow is a deterministic module and planned enhancement, not a seventh agent.
- React/FastAPI and the Inspector remain product requirements even though the rubric names Streamlit.

Open decisions that require implementation research or owner approval:

- deployment target and the corresponding production identity, storage, encryption, and retention mechanisms;
- authoritative market and news providers, licensing, entitlements, cache terms, and fallback ordering;
- Qdrant hosting mode, embedding and sparse models, distance metric, chunk policy, and relevance thresholds, chosen through M1 evaluation;
- production FX-provider/conversion behavior and any future short-position model beyond the conservative ADR-021 initial policy;
- durable stores and retention periods for portfolios, checkpoints, runs, and traces;
- any diversification methodology beyond the versioned HHI/effective-holdings heuristic accepted by ADR-021;
- instructor confirmation of rubric, React substitution, MCP status, and named-provider flexibility.
