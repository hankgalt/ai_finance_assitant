# AI Finance Assistant — Architecture decision records

Version 1.2 | Status: Product architecture baseline | 2026-10-28

The existing single-file register is retained to avoid unnecessary file churn. “Accepted” records are architectural constraints; “Proposed” records require validation during the named milestone. Proof references are future completion evidence, not claims of implementation.

### ADR-001: LangGraph StateGraph for orchestration — Accepted

Use a typed LangGraph StateGraph with an explicit router, conditional edges, specialist nodes, synthesis, and checkpointing. This provides inspectable workflows, bounded collaboration, and measured events for the Inspector. A single opaque tool-calling agent and CrewAI were rejected because the six responsibilities and routing behavior must remain testable.

### ADR-002: Six agent interfaces over shared deep modules — Accepted

Expose six specialist agent interfaces and put retrieval, providers, validation, and financial calculations behind shared deep modules. Agents return a common structured AgentResult and may coordinate only through the graph. This concentrates arithmetic and data-quality rules in one test seam instead of reproducing them in prompts.

### ADR-003: Durable conversation checkpoints with explicit deployment modes — Proposed

Key checkpoints by Session and Workflow version. Automated tests may use an in-memory adapter; local development requires a durable adapter that survives restart; a public deployment requires an access-controlled managed store. React state is not the source of truth. Select the concrete durable store in M0/M5 after deployment constraints are known.

### ADR-004: FAISS local vector retrieval plus metadata catalog — Superseded by ADR-016

The earlier plan combined FAISS with SQLite/JSON metadata because a coursework milestone named FAISS. It is not the product baseline: persistence, metadata filtering, collection activation, and hybrid retrieval would be split across shallow interfaces. Coursework equivalence is documented in the coursework acceptance criteria.

### ADR-005: Evaluation-driven hybrid retrieval — Accepted

Maintain a dense semantic baseline, support sparse retrieval and Reciprocal Rank Fusion, and enable them per query class or collection only when the fixed retrieval set shows value. Hybrid retrieval is a capability, not a requirement for every query. This controls latency and cost while preserving exact-term performance where it matters.

### ADR-006: Provider adapters with truthful freshness — Accepted

Define MarketDataProvider and NewsProvider ports at true external seams. Production adapters and deterministic fake adapters satisfy the same interfaces. Every result carries provenance and timing; bounded caching, quota handling, retry with jitter, and stale/unavailable outcomes are part of the interface. Provider selection and licensing remain open through M3.

### ADR-007: React and FastAPI application architecture — Accepted

Use React, TypeScript, Vite, Tailwind CSS, shadcn/ui, and TanStack Query in a separate web client with a Python FastAPI backend. The backend owns orchestration, access checks, financial calculations, integrations, and provenance. Streamlit is faster for a prototype but less suitable for the intended product interface; coursework substitution evidence remains mandatory.

### ADR-008: Configurable LLM adapter and no mandatory fine-tuning — Accepted

Place model invocation behind a structured LLM adapter, record the model/prompt version used for a Run, and test with deterministic fakes. Choose an economical current model through evaluation rather than hard-code historical course guidance. Fine-tuning requires measured benefit and is not an initial-release requirement.

### ADR-009: Deterministic finance modules are numerical authority — Accepted

Portfolio and goal arithmetic belongs in tested Python modules with validated inputs, documented precision/rounding, structured warnings, and returned results. LLMs may explain those results but cannot improvise authoritative arithmetic. This is a financial safety seam and applies to the planned cash-flow module as well.

### ADR-010: Read-only MCP adapter after core product modules — Proposed

For the coursework release, expose approved education, quote, portfolio-analysis, and goal-projection interfaces through a read-only MCP adapter backed by the same modules as FastAPI. It cannot bypass validation, authorization, provenance, or secret handling. Its ambiguous rubric status is resolved conservatively as required pending instructor confirmation.

### ADR-011: Observability and evaluation are product features — Accepted

Emit structured, privacy-filtered execution and provider/retrieval events with correlation identifiers, measured latency, status, and usage/cost when available. Store versioned evaluation inputs, configuration, and outputs. LangSmith or another backend may be an adapter, not the only record of product behavior.

### ADR-012: External and retrieved content is untrusted data — Accepted

Treat knowledge documents, imports, provider payloads, news, and user-supplied text as data rather than instructions. Enforce tool allow-lists, schemas, timeouts, step bounds, output validation, access checks, and redaction in code outside prompts. Test prompt injection and malicious file content at the relevant seams.

### ADR-013: React Flow Inspector renders measured execution — Accepted

The Agent Execution Inspector renders actual LangGraph lifecycle events as a React Flow graph plus an accessible ordered timeline and detail view. It never infers dynamic execution from a final answer and never displays hidden reasoning, credentials, raw financial records, or sensitive tool payloads. Contracts begin in M0, instrumentation in M4, UI in M7, and fidelity testing in M8.

### ADR-014: Versioned REST plus Server-Sent Events — Accepted

Use versioned REST for ordinary operations and authoritative final state. Use Server-Sent Events for one-way conversational tokens and execution events where streaming improves the experience. Stable execution, event, Session, and Workflow identifiers plus per-run sequence enable correlation and reconnection. WebSockets remain unnecessary until bidirectional run control is approved.

### ADR-015: Recharts for financial charts and React Flow for traces — Accepted

Use Recharts for portfolio, market, and goal visualizations and React Flow only for execution paths. Each visualization has a readable tabular or timeline alternative. Additional chart libraries require a demonstrated capability gap.

### ADR-016: Qdrant is the initial persistent vector database — Accepted

Use standalone Qdrant as the initial vector database because it persists independently of application runtime, filters rich payload metadata, supports multiple logical knowledge bases, accommodates dense and sparse representations, supports hybrid retrieval and Reciprocal Rank Fusion, and has a growth path beyond a local in-process index. Application startup validates and consumes existing collections; it does not create embeddings. Compared with FAISS plus a side catalog, Qdrant provides a deeper retrieval interface and a clearer activation/rollback seam at the cost of operating a separate process.

### ADR-017: Offline, versioned ingestion with explicit activation — Accepted

Build knowledge collections in a separate ingestion workflow. Each document and chunk carries source/version hashes and model/schema identifiers; unchanged inputs are idempotent, changed documents are incrementally re-indexed, and embedding-model changes create a new collection version. A candidate becomes active only after validation and fixed-set retrieval evaluation, and the previous version remains available for rollback.

### ADR-018: Imported, enriched, and calculated portfolio data stay separate — Accepted

Keep user-imported portfolio records immutable as evidence, attach provider-enriched security reference records with provenance, and create time-specific calculated Portfolio Snapshots. This avoids silently rewriting user data, makes conflicts visible, and lets calculations be reproduced against an exact quote set. The tradeoff is explicit joining and lifecycle management across three record types.

### ADR-019: Security posture is deployment-mode explicit — Accepted

The initial local demonstration may run without authentication only when bound and labeled as local. Session checks, minimization, redaction, deletion, and secure file parsing still apply. A public or multi-user deployment is not permitted until strong identity, per-resource authorization, protected persistence, enforced retention, monitoring, and deployment threat review are implemented and verified.

### ADR-020: Cash flow is a planned deterministic module, not a seventh agent — Accepted

Reserve a CashFlowAnalysisService interface for normalized transaction imports, categorization, reconciliation, summaries, surplus, and trends. Goal Planning can later consume an authorized summary through this seam; raw transactions stay outside unrelated agent state. This preserves the six-agent model and makes future bank and card support possible without putting reconciliation arithmetic in an LLM.

### ADR-021: Conservative M2 calculation and portfolio policy — Accepted

Use Decimal arithmetic under the versioned M2 calculation policy, with half-even output rounding and explicit coverage for missing inputs. The initial release rejects negative quantities because no short-position model has been approved. It never combines currencies without an identified FX conversion set; absent that set, valuation, allocation, expense, concentration, and diversification results remain partitioned by currency. The diversification heuristic is holding-value HHI plus effective holding count, reported with coverage and an explicit limitation that it is not a correlation, volatility, suitability, or risk score. These choices favor reproducibility and truthful partial results over invented conversions or implied financial judgment.

### ADR-022: Cash-flow import is provider-independent — Accepted

Implement the planned cash-flow capability first through versioned user-controlled JSON and CSV imports plus Cash-flow import profiles that map source-specific columns and conventions to canonical transactions. A financial-data provider or live bank connection may later be an optional adapter to the same canonical seam, but it is not a dependency or acceptance requirement. This preserves local reproducibility, avoids making personal analysis contingent on credentials, commercial terms, or account aggregation, and keeps the security scope bounded; the tradeoff is explicit mapping review and user-managed exports.

### ADR-023: The initial release is a private demonstration release — Accepted

Build and qualify the initial release with production-oriented interfaces, security boundaries, failure behavior, and evidence, but operate it only in a controlled local or private environment for the owner and approved viewers; it is not a public launch. A live demonstration may call approved providers only within an explicit entitlement-aware request budget, while a separately selected credential-free mode uses clearly labeled deterministic adapters and never silently mixes synthetic and live results. This makes the full feature set reproducibly demonstrable without implying public-production readiness; public deployment still requires ADR-019 hardening and approved commercial provider rights.

### ADR-024: Conditional Alpha Vantage and Tavily adapters with a deterministic default — Accepted

Implement Alpha Vantage as the initial live MarketDataProvider adapter for symbol search, end-of-day quotes, and raw daily history, and Tavily as the initial live NewsProvider discovery adapter for attributed links and bounded snippets. These adapters are production-shaped but remain disabled unless the exact account terms, market-data entitlement, display/cache rights, credentials, and per-workflow budgets are approved. Credential-free deterministic adapters are the default for development, CI, and demonstrations without approved live access. Provider mode is selected before a workflow; a readiness failure never changes a running workflow from live to synthetic. yfinance is excluded because its software license does not establish product rights to Yahoo Finance data. A future public release requires a new rights review and may replace either adapter without changing the application ports.

### ADR-025: Explicit Alpha Vantage or Massive live market-adapter selection — Accepted

Add Massive as a second conditional implementation of the existing MarketDataProvider port while retaining Alpha Vantage. `AIFA_MARKET_DATA_PROVIDER` selects exactly one live market adapter before a workflow; a quota, entitlement, or availability failure never triggers automatic mid-workflow failover, so quote-set provenance and approved request budgets remain coherent. Massive uses ticker reference, previous-day aggregate, and raw daily aggregate endpoints with authorization-header credentials and a five-request-per-minute local bound. Its individual-plan data is allowed only for the subscribing owner's personal use under the current published terms; showing data to testers or other viewers requires approved Business/commercial rights. Credential-free mode remains the reproducible default, and a future public release still requires an account-specific commercial data-rights decision.

### ADR-026: Two-tier durable provider cache with an owner-only retention exception — Proposed

Add a bounded in-memory front cache and a database-backed cache of normalized historical market observations behind one application-owned persistence port. Persist bars by provider, canonical instrument, interval, trading date, currency, adjustment basis, and schema/policy version; satisfy ranges from valid stored coverage, fetch only gaps and the configured recent refresh window, and never silently merge observations from different providers. Stored values remain derived provider data with original market/retrieval timestamps and rights metadata, not an authoritative market-data warehouse. M5 must select and validate the concrete relational store, migrations, concurrency control, purge behavior, and freshness policy. For owner-only local development, an operator may explicitly accept the risk of long-term retention when provider cache permission has not been confirmed; this exception is not evidence of contractual permission and cannot enable shared demonstrations or public deployment without an approved retention/display-rights review.

## Decision register still open

The following are not silently decided by these records: a future public deployment target; identity provider; concrete checkpoint, portfolio, run-event, and durable provider-cache stores; provider-specific refresh and retention periods; commercial/public market and news rights; production Qdrant hosting mode; initial institution-specific Cash-flow import profiles; and authoritative coursework rubric interpretations. M1 resolved the initial representation and ranking experiment; ADR-021 resolves initial multi-currency behavior, short positions, and the diversification heuristic; ADR-022 resolves that cash-flow import does not depend on a provider; ADR-023 resolves the private demonstration posture; ADR-024 resolves the initial adapters and safe default; ADR-025 resolves explicit Alpha Vantage/Massive selection without claiming shared-demo or public-production data rights; ADR-026 proposes the durable-cache shape and a narrowly labeled owner-only risk exception while leaving its concrete store and policies to M5 validation. Remaining decisions require measured or contractual evidence in their owning milestone.
