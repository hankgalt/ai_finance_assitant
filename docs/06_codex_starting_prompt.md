# Codex implementation prompt — M0 foundation only

You are implementing **M0 only** for AI Finance Assistant, an extensible U.S.-focused financial education and analysis product. The capstone acceptance criteria are mandatory release evidence, not the product’s architectural identity.

## 1. Establish context before editing

1. Inspect the repository and preserve existing work.
2. Read [README.md](README.md), then the requirements, ADRs, system design, implementation plan, evaluation strategy, coursework acceptance criteria, and [root glossary](../GLOSSARY.md) in the index’s stated order. Read this prompt last.
3. Report any missing or contradictory authoritative document. Use the precedence in docs/README.md. For a safe reversible ambiguity, record the assumption; stop before editing when the ambiguity affects data loss, security posture, a public interface, or a hard-to-reverse technology choice.
4. Summarize the intended M0 changes and their PR/QR/ADR mapping in 5–10 lines.

Context is complete when every proposed change maps to the M0 deliverables and no later milestone behavior is included.

## 2. M0 outcome

Create a maintainable foundation with contracts and honest placeholders:

### Backend

- Python 3.11+ FastAPI foundation with separate liveness and structured readiness. Readiness represents expected Qdrant collection compatibility and configured dependencies without creating a collection, fetching sources, or embedding content.
- Versioned Pydantic contracts for AgentRequest/AgentResult, stable typed errors, provider provenance/freshness, core Portfolio/Account/Holding identifiers, and RunEvent v1 from system design §11.
- RunEvent covers execution/trace/Session/Workflow identity, sequence, node/agent/tool subject, event/status, start/completion/duration availability, safe route/result/error metadata, token/cost availability, and retrieval source metadata.
- Configuration and secret-loading seam, request/execution correlation, privacy-safe structured logging, and allow-list redaction behavior.
- Named identifiers/contracts for all six agents without implementing agent behavior or placeholder agents that appear operational.
- Small interface foundations only where M0 needs them. Financial calculations, import parsers, provider adapters, LangGraph execution, persistence implementations, and the CashFlowAnalysisService belong to later milestones.

### Frontend

- React, TypeScript, Vite, Tailwind CSS, shadcn/ui-compatible foundation, and TanStack Query.
- Accessible navigation shells for Conversational Assistant, Portfolio Dashboard, Market Overview, Goal Planning, and Agent Execution Inspector.
- Typed health/readiness client, disconnected/not-ready states, and contract-verified RunEvent types.
- Inspector placeholder with a clearly labeled, versioned synthetic event timeline fixture. React Flow may render the same fixture if lightweight, but it must be labeled synthetic and must not imply LangGraph ran.
- Recharts and React Flow can be prepared as dependencies for their documented roles; do not create invented portfolio, market, goal, or execution results.

### Development and evidence

- Credential-free deterministic tests for backend health/contracts/redaction and frontend navigation/fixture/accessibility basics.
- Lint, format, typecheck, test, and local run commands; safe local CORS/bind settings; environment template containing no secrets; reproducible package/dependency configuration.
- A concise repository README explaining the product posture, local/demo limitations, and the separate FastAPI, React, and future Qdrant/ingestion processes.
- docs/M0_delivery_report.md with files changed, requirement/ADR mapping, exact commands/results, failures/skips, deviations, privacy/security notes, evidence paths, open decisions, and recommendation for M1.

M0 is complete only when the foundations start locally in the documented mock/local mode, the frontend reports backend health/readiness truthfully, contracts and synthetic fixtures pass their tests, and every later-milestone feature remains visibly unimplemented.

## 3. Architecture guardrails

- FastAPI is the trust seam. The browser does not own access checks, financial calculations, provider credentials, provenance, orchestration, or durable state.
- Qdrant is the persistent vector database. The separate M1 ingestion workflow builds and activates versioned Finance and Tax collections; application startup only validates existing collections. M0 does not implement ingestion.
- Exactly six agents exist in the product design: Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, and Tax Education. Goal Planning and Market Analysis remain distinct. M0 defines identifiers/contracts only.
- Numerical portfolio, goal, and future cash-flow analysis belongs to deterministic Python modules. LLM arithmetic is never authoritative.
- CashFlowAnalysisService is a planned deterministic module, not a seventh agent. Its interface is reserved in M2, not built in M0.
- REST is authoritative for ordinary operations and final state; SSE begins in M5 after actual M4 instrumentation. Do not build a fake streaming server in M0.
- React Flow eventually renders captured RunEvents. It never orchestrates and never derives execution from a final response.
- Protect credentials, raw financial records, raw prompts, hidden reasoning, and sensitive tool payloads from logs, fixtures, traces, and UI.
- Label fixture, mock, stale, unavailable, and unmeasured data. Do not claim measured latency, cost, token usage, trace fidelity, accessibility conformance, security, or test results without evidence.
- Tests cross public interfaces and validate behavior, not the existence of files or dependencies.

## 4. Scope exclusions

M0 does not implement LangGraph workflows, working agents, Qdrant ingestion or collections, dense/sparse retrieval, portfolio file import, financial calculations, market/news/model providers, checkpoints, saved portfolios, production authentication, REST business resources, SSE, MCP, real Inspector instrumentation, cash-flow analysis, live APIs, or product dashboards.

Do not weaken product or coursework requirements to fit M0. Record later work in the delivery report without creating speculative modules.

## 5. Verification and stop condition

Run the repository’s actual formatting, linting, typechecking, unit/component tests, and local startup/health checks. Report the exact commands and unedited outcomes, including failures and skips. Do not install global software, use paid credentials, modify external services, or commit unless explicitly requested.

At completion, provide the M0 delivery report, a concise changed-file summary, actual verification results, unresolved decisions, and the recommended M1 entry checks. **Stop after M0 and request architecture review before beginning M1.**
