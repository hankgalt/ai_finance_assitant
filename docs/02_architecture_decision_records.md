# AI Finance Assistant — Architecture decision records

Version 1.12 | Status: Product architecture baseline plus repository-implemented proposed private-demo edge and corrected workload/secret decisions | 2026-11-12

The existing single-file register is retained to avoid unnecessary file churn. “Accepted” records are architectural constraints; “Proposed” records require validation during the named milestone. Proof references are future completion evidence, not claims of implementation.

### ADR-001: LangGraph StateGraph for orchestration — Accepted

Use a typed LangGraph StateGraph with an explicit router, conditional edges, specialist nodes, synthesis, and checkpointing. Intent selection is a schema-constrained decision made through the Run's fixed ModelAdapter; a deterministic scripted adapter is permitted only for credential-free tests and demonstrations. A lexical substring table is not routing authority. This provides inspectable workflows, bounded collaboration, and measured model/route events for the Inspector. A single opaque tool-calling agent and CrewAI were rejected because the six responsibilities and routing behavior must remain testable.

### ADR-002: Six agent interfaces over shared deep modules — Accepted

Expose six specialist agent interfaces and put retrieval, providers, validation, and financial calculations behind shared deep modules. Agents return a common structured AgentResult and may coordinate only through the graph. This concentrates arithmetic and data-quality rules in one test seam instead of reproducing them in prompts.

### ADR-003: Durable conversation checkpoints with explicit deployment modes — Accepted

Key checkpoints by Session and Workflow version. Automated unit tests may use an in-memory adapter. The private local demonstration uses the official LangGraph SQLite saver in the same local database as the versioned application schema, with a dedicated connection, WAL, foreign keys, a busy timeout, and strict checkpoint deserialization. React state is not the source of truth. This synchronous store is appropriate only for the bounded local/private demonstration; a public deployment still requires an access-controlled managed store selected through a new decision and migration plan.

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

### ADR-010: Read-only MCP adapter after core product modules — Accepted

For the coursework release, expose approved education, quote, portfolio-analysis, and goal-projection interfaces through a read-only MCP adapter backed by the same modules as FastAPI. It cannot bypass validation, authorization, provenance, or secret handling. Its ambiguous rubric status is resolved conservatively as required pending instructor confirmation.

M9 validated the decision with official-SDK in-memory and external stdio clients, bounded schemas,
read-only/non-destructive annotations, deterministic shared-module results, provider provenance, and
an explicit absence of persistence, administration, credential, Session, deletion, and trade tools.

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

### ADR-026: Two-tier durable provider cache with an owner-only retention exception — Accepted

Add a bounded in-memory front cache and a SQLite-backed cache of normalized historical daily bars behind one application-owned persistence port. Persist bars and successful coverage windows by provider, canonical instrument, one-day interval, trading date, currency, adjustment basis, schema version, and cache-policy version; satisfy ranges from valid stored coverage, fetch only gaps and the configured recent refresh window, and never silently merge observations from different keys. Application migrations are transactional and versioned. SQLite uses WAL, foreign keys, a busy timeout, and keyed in-process request coalescing; this is a local/private-demo concurrency decision, not a distributed-lock design.

The initial policy bounds the exact-request memory tier to 128 entries for five minutes, retains eligible normalized historical bars for at most 3,650 days, treats the latest seven calendar days as a refresh tail, and revalidates that tail after six hours. Provider-specific configuration may shorten those bounds but not extend them silently. Administrative purge can scope deletion by provider and records the affected count. Current quotes and news retain their existing short in-memory endpoint lifecycles.

Stored values remain derived provider data with original market/retrieval timestamps and rights metadata, not an authoritative market-data warehouse. Raw payloads, credentials, news bodies, and user/portfolio context are excluded. Synthetic fixture data may use the durable cache without a rights exception. Live data whose retention permission is unverified requires an explicit owner-only local risk-acceptance setting; the setting and rows carry that label. It is not evidence of contractual permission and makes shared-demo and public-deployment readiness fail until an approved retention/display-rights review changes the status.

### ADR-027: Archive before permanent Session deletion — Accepted

Treat clearing the Active Session as an `active → archived` transition that preserves its owned artifacts and checkpoint as read-only history and opens a new Active Session. Permanent deletion is a separate, explicitly confirmed action available only for an Archived Session; it cascades owned artifacts and removes the checkpoint thread. Archived Sessions remain subject to the configured retention expiry. This preserves useful history and makes irreversible deletion unambiguous, at the cost of a schema migration and a two-step lifecycle instead of immediate deletion.

### ADR-028: Evidence-bound Redis response cache — Accepted

Add an application-owned `ModelResponseCache` seam with Redis 8 and RedisVL as the private-demo adapter, plus disabled and deterministic in-memory adapters for tests. Do not use a framework-global LLM cache: the application must decide eligibility, construct versioned keys and filters, validate cached schemas, and record reuse at the same model boundary used by the six agents. Redis is an optional acceleration store, not conversation memory, a knowledge base, an execution record, or a source of financial truth.

Initial reuse is deliberately narrow and Session-isolated under QR-004. An exact match may reuse the route for a previously qualified, standalone public Finance Q&A or U.S. Tax Education request in the same authorized Session scope. A semantic match may reuse only a successful schema-validated generation from the same single RAG domain in that scope after the current request has been routed and the corresponding active Finance or Tax collection has been queried again. Tax reuse additionally requires an exact U.S. federal jurisdiction and resolved tax-year match. The semantic lookup uses a pinned local embedding adapter, initially the existing `BAAI/bge-small-en-v1.5` FastEmbed representation if M6.1 calibration accepts it; it does not add an external embedding call. A generation entry is usable only when exact metadata filters match an opaque server-derived Session scope, the agent, model/provider, prompt and workflow versions, response schema and cache-policy versions, locale/jurisdiction, resolved tax year where applicable, and an evidence fingerprint made from the active collection version plus the retrieved chunk identifiers and content hashes. The new Run rebuilds citations from that current Evidence and never returns a stored whole-Run result.

The first policy excludes multi-agent requests, context references and checkpoint-dependent follow-ups, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, personalized inputs, errors, partial/no-evidence results, and any request that cannot be confidently classified as standalone public Finance or U.S. federal Tax education. A frozen Finance-and-Tax paraphrase and near-miss evaluation set must calibrate the similarity threshold in shadow mode before semantic hits are enabled; the threshold is a versioned policy value, not a library default.

For the local/private demonstration, Redis binds only to loopback, uses an explicitly pinned image/dependency set, has persistence disabled, applies an initial maximum TTL of 24 hours, stores only an opaque server-derived Session scope, the normalized policy-qualified public education query, and the validated structured response, and stores no system prompt, raw Session/Run identifier, context reference, or financial/provider payload. Cross-Session reuse is prohibited. Session archival and permanent deletion remove that Session's cache namespace; administrative purge remains available. Cache unavailability, corruption, timeout, or schema mismatch is a measured bypass/miss and never fails the workflow. Concurrent identical misses are coalesced only within the same Session scope and documented deployment boundary. RunEvents and operational telemetry record lookup outcome, entry age, policy version, and a bounded similarity-distance bucket; model lifecycle events are emitted only when a model call actually occurs. M8 compares cache-disabled, exact-hit, qualified semantic-hit, and near-miss paths for latency, avoided calls/tokens, answer/citation equivalence, Session isolation, privacy, and false-hit safety.

Caching complete `WorkflowRunResult` objects, citations, personalized calculations, time-sensitive provider results, all-agent responses, system prompts, unqualified user messages, or cross-Session results was rejected because it would hide current evidence/freshness checks and expand privacy and correctness risk. LangChain's global cache was rejected for this product seam because the repository invokes a custom structured `ModelAdapter` and requires application-specific eligibility, Session isolation, evidence binding, event truth, and invalidation.

### ADR-029: Product capabilities own durable repository assets — Accepted

Organize committed data, generated artifacts, machine contracts, and tests by the durable product
capability or interface they describe. Cross-product verification belongs to `quality`,
`qualification`, or `release`; milestone identifiers remain only in planning, delivery reports, and
historical evidence. This keeps a module's implementation inputs, interface evidence, and tests at a
stable seam after the delivery sequence has ended, so maintainers do not need milestone history to
find or change current behavior.

Machine-readable paths are part of the reproducibility interface. A layout migration therefore
updates CLI defaults, Make targets, manifests, checksums, tests, documentation links, and release
audits atomically. Compatibility Make targets may retain milestone names while existing delivery
reports depend on them, but new durable targets use capability or release terminology. Runtime
state remains ignored and is not moved by this decision because changing its location requires a
separate data-migration and rollback design.

Keeping milestone directories as the permanent repository taxonomy was rejected because one
capability then spans several unrelated delivery folders. Duplicating or symlinking artifacts into
both taxonomies was rejected because it creates competing sources of truth and weakens path and
checksum validation.

### ADR-030: IAP-protected GCP private multi-user deployment — Proposed

The first accepted outcome of this decision is a private-demo MVP: the existing locally qualified
product is usable by the owner at the target URL with equivalent product capabilities. It is not a
production-readiness decision, availability commitment, disaster-recovery claim, or approval for
anonymous/general-public access. Controls needed to protect identity, Principal-owned data,
secrets, and the workload origin remain mandatory even for the demo.

Deploy the Finance Assistant as an internet-routable but non-public application at
`https://apps.comfforts.com/finance_assistant`, with Google Cloud as the target platform and Google
Identity-Aware Proxy as the only browser authentication flow. IAP admits only the owner and
explicitly approved Google Workspace or consumer Google accounts. FastAPI independently validates
the signed IAP assertion, maps its issuer and subject to an immutable Application Principal, and
authorizes every Session, Portfolio, Snapshot, Goal, Run, stream, History record, and Inspector view
against that Principal. Email is admission and display metadata, not a resource-ownership key.
Anonymous access, trusting unsigned IAP headers, frontend-only authorization, and adding a second
`@react-oauth/google` login to this application are rejected because they either weaken the boundary
or create competing identities.

The application-access decisions are approved as follows. The initial owner admission email is
`vtalwar.w@comfforts.com`; additional consumer-Google viewers are admitted only by explicit
allow-list. Owner and viewer Principals may read and mutate only their own product resources. Only
the owner role may invoke application administrative operations. A disabled Principal has no
application access. Removing the edge IAP grant blocks a viewer at the edge; setting the application
Principal to disabled is enforced at the next HTTP request or SSE reconnect. Revocation does not
cancel a request already executing, reassign data, or silently delete retained data. Live-provider
use by viewers stays denied until role-specific rights are approved under ADRs 024–026.

The application remains available locally through a separately configured, explicitly labeled
loopback-development Principal (`urn:ai-finance-assistant:identity:loopback-development`, subject
`owner`, display email `local-owner@example.invalid`, owner role). Local and deployed navigation
both use `/finance_assistant`. The deployed application store starts empty; existing local product
data is not copied to the owner Principal, and current RAG collections are transferred by the
separate knowledge-release workflow. The deployed path is served through an HTTPS load balancer
with HTTP redirect, IAP, and
no direct workload bypass. Application workloads are stateless with respect to authoritative user
state; managed persistence, deployed Qdrant, response-cache topology, encryption, region, and cost
controls must be selected and the MVP identity, migration, readiness, and destroy/recreate paths
must be qualified before this ADR can be accepted. Backup/PITR, HA, disaster recovery, load/soak,
formal SLO/alert rehearsal, and production capacity qualification are deferred hardening work and
cannot be inferred from MVP acceptance. Finance and Tax collections continue to be built, evaluated, and activated by the
offline knowledge workflow rather than application startup. Provider access remains governed by
ADRs 024–026 and must be entitlement-aware for each Application Principal; this deployment decision
does not create display, caching, or redistribution rights.

The load balancer maps the exact `/finance_assistant` path and its descendants to a dedicated
IAP-protected backend policy. API requests remove only that public base-path prefix before reaching
FastAPI's `/api` origin contract; frontend paths are not rewritten. Unmatched paths fail closed. A
future application on another path must
use its own backend and authentication decision and cannot infer or reuse the Finance Assistant
Principal. Because paths on one hostname share a browser origin, such an application also shares a
browser trust boundary unless it moves to a separate hostname; that future application is outside
M11.

The repository implementation uses separate IAP-enabled frontend and backend backend services so
the API routes can derive the signed-assertion audience from the backend service's immutable
generated identifier. Before that identifier exists, workloads retain a deliberately invalid
fail-closed audience. Only the Google-managed IAP service agent receives Cloud Run invocation; the
workloads retain internal-and-load-balancer ingress with their default URLs disabled. The OAuth
client secret is entered directly into the dedicated regional Secret Manager secret and consumed by
Terraform through an ephemeral/write-only value. It must not appear in repository files, ordinary
Terraform variables, saved plans, state, workflow configuration, evidence, or operator logs. The
external address and edge are applied before the owner creates the registrar record. The reviewed
live edge now qualifies IAP, origin denial, routing, TLS, owner admission, unmatched-path denial,
and drift. ADR-030 remains Proposed because integrated identity/isolation and deployed product
journeys are still acceptance gates.

The corrected owner-approved MVP managed-state target uses single-zone Cloud SQL for PostgreSQL 17
Enterprise in `us-west1` on `db-g1-small` with the service-minimum 10 GiB SSD. It holds distinct
application, LangGraph checkpoint, and purgeable provider-cache boundaries; local development
continues to use SQLite. The deployed response cache is disabled and no managed Redis service is
provisioned. Each created demo store starts empty. Destroying the demo runtime intentionally
discards its Principal-owned application data; no local data migration, backup, PITR, RPO, or RTO
guarantee is part of the MVP. Session/Run/checkpoint and RunEvent retention remains 30 days while an
instance exists, saved Portfolio and Snapshot retention remains 365 days while an instance exists,
and provider observations require provider-specific approved rights and TTLs. Google-managed
encryption and standard Secret Manager with user-managed replication restricted to `us-west1` are
selected initially; CMEK is not selected. Cloud Run receives the Qdrant runtime key through native
environment injection pinned to a positive numeric secret version, never `latest`. Terraform owns
only secret metadata and IAM. A clean runtime destroy removes the secret and its versions, so the
owner enters the value directly in Secret Manager again on recreation. This replaces the earlier
regional-secret proposal because Cloud Run cannot natively inject regional secrets; adding an
application-side secret client was rejected as unnecessary private-demo complexity.

The demo runtime is created and destroyed on demand through reviewed Terraform workflows rather
than kept live continuously. The reproducibility foundation needed to recreate it—protected
Terraform state, immutable images, short-lived delivery identity, non-secret configuration, and
the private VPC, allocated internal range, and Service Networking connection—may remain. [Google
Cloud can retain deleted Cloud SQL producer networking for up to four
days](https://docs.cloud.google.com/vpc/docs/configure-private-services-access); teardown therefore accepts only
that exact three-resource networking residue after independently confirming that Cloud SQL and all
other staging runtime resources are absent. The lifecycle contract must make data loss explicit
before destroy and prove clean recreation, schema migration, readiness, and application smoke. The
previously provisioned
`db-f1-micro`, backup, and PITR settings remain truthful historical staging evidence; they are not
the corrected MVP target and do not make recovery qualification an MVP gate.

Staging and the protected demo share project `comfforts-369117` as an accepted private-demo
limitation, but use separate Terraform state, workload identities, secrets, database roles, and
synthetic data; restore qualification uses an ephemeral database instance. The public GitHub Pro
repository `hankgalt/ai_finance_assitant` has `hankgalt` as its sole deployment approver. Self-review
therefore remains permitted and is recorded as a single-operator control rather than independent
review. The combined soft monthly budget is USD 100 with 50%, 80%, and 100% alerts; it is not a hard
spending cap.

The selected Qdrant Free cluster `finance-assistant-demo` is a single-node GCP service in
`us-central1`, because the free tier did not offer `us-west1`. This cross-region, no-SLA topology is
an explicit private-demo exception. It stores only shared immutable knowledge collections and never
Application-Principal-owned data. Its runtime key and offline release key remain separate secrets.
Broader availability or regional-residency claims require a paid topology or a separately approved
decision.

Terraform owns reproducible GCP resources, while GitHub Actions uses short-lived Workload Identity
Federation rather than stored service-account keys for validated plan, build, and approval-gated
deployment workflows. DNS changes at the external registrar may remain a documented operator step.
Implementation assets and evidence are organized under durable identity/access, persistence,
knowledge, infrastructure, observability, quality, and release ownership in accordance with
ADR-029; `M11` appears only in planning and historical delivery evidence. Before this proposal may
become Accepted for the private-demo MVP, M11 must validate cross-Principal denial across every
product experience, IAP-bypass and direct-origin resistance, clean empty-store creation, schema
migration, retention/deletion while deployed, active-collection readiness, provider gates,
destroy/recreate, and local-feature-parity smoke at the protected URL. Backup/restore, PITR,
application/infrastructure/collection rollback rehearsal, capacity/soak, production monitoring,
and disaster recovery remain explicit post-MVP hardening gates for any later production-readiness
claim.

The selected deployment inputs are GCP project `comfforts-369117` (project number
`730340912967`) in the `comfforts.com` organization, region `us-west1`, a single-region/low-traffic
posture, and the owner-approved managed-state contract in
`contracts/deployment/managed-state.v1.json`. Secret values are entered directly in Google
Secret Manager and never committed or passed as Terraform variables. The owner retains Squarespace
DNS control and will add the reviewed record after a load-balancer address exists. These selections
do not authorize infrastructure provisioning in the application-access slice.

## Decision register still open

The following are not silently decided by these records: final acceptance of the proposed GCP
private-demo topology before measured MVP qualification; the exact post-MVP backup/recovery,
availability, capacity, and production-operations posture; commercial market-data rights for approved
viewers; initial institution-specific Cash-flow import profiles; and authoritative coursework rubric
interpretations. M1 resolved the initial representation and ranking
experiment; ADR-021 resolves initial multi-currency behavior, short positions, and the
diversification heuristic; ADR-022 resolves that cash-flow import does not depend on a provider;
ADR-023 resolves the initial private demonstration posture; ADRs 024–026 resolve provider adapters
and private-demo cache policy without granting shared market-data rights; ADR-027 resolves the local
Session lifecycle without approving indefinite retention; ADR-028 resolves only the bounded
private-demo response-cache policy; ADR-029 makes capability ownership durable; and proposed ADR-030
has a qualified live edge but remains unaccepted pending the assembled M11 product journeys.
Remaining decisions require measured, operational, or contractual evidence in their owning
capability and M11 acceptance gate.
