# AI Finance Assistant — Evaluation, safety, and reliability strategy

Version 1.1 | Status: Product evaluation baseline | 2026-10-28

## 1. Evaluation principles

Evaluation answers two separate questions:

1. **Product release:** Is the implemented behavior accurate, grounded, safe, reliable, accessible, and traceable enough for the stated initial local release?
2. **Coursework acceptance:** Does the submission demonstrate every mandatory capability and grading artifact in [coursework acceptance criteria](coursework_acceptance_criteria.md)?

Passing a coursework score threshold does not waive a product-critical failure. A high coverage percentage, installed framework, expected filename, or passing mock that never crosses the real interface is not evidence of correct behavior.

Each report identifies code revision, dataset version, Workflow/prompt/model versions, provider fixture or live mode, active Qdrant collection and representation versions, configuration, timestamp, random seeds where relevant, and evaluator method. “Not available” is a valid recorded result; invented measurements are not.

## 2. Versioned evaluation assets

Maintain reviewable datasets with stable case IDs:

- routing: at least 40 single-, ambiguous-, multi-domain, clarification, and follow-up requests;
- agent specialization/collaboration: direct cases for all six agents and cross-agent workflows;
- Finance and Tax retrieval: fixed qrels with relevant document/chunk IDs, metadata filters, exact-term and semantic cases, and historical tax years;
- grounded responses/citations: factual claims paired with permitted evidence and abstention cases;
- portfolio import: manual, JSON, CSV, and XLSX valid/adversarial samples with expected validation findings;
- arithmetic: hand-worked golden cases, edge cases, and generated property/metamorphic cases;
- market/news: success, delay, memory/durable/partial cache, restart and overlapping-range reuse, stale, 401/403, 429, timeout, malformed payload, conflict, and outage fixtures;
- multi-turn/isolation: at least 15 dialogues plus concurrent Session cases;
- safety: prompt injection, source poisoning, financial-advice pressure, sensitive-data extraction, tool escalation, and malicious file cases;
- API/streaming: versioned REST/SSE transcripts, duplicate/out-of-order/reconnect cases;
- UI/accessibility: deterministic end-to-end journeys, keyboard flows, and alternative chart/trace representations;
- Inspector: synthetic schema fixtures and actual instrumented Runs with a backend truth record.

Dataset size targets can grow after difficulty and independence review. Do not inflate corpus or test counts with paraphrases that exercise the same behavior.

## 3. Product evaluation matrix

Thresholds below are initial candidate gates. M8 must calibrate noncritical statistical thresholds against representative data and record any accepted change. Critical invariants cannot be averaged away.

| ID | Dimension | Measurement and method | Initial release gate |
|---|---|---|---|
| EVAL-01 | Workflow routing | Agent-set precision/recall, single-intent accuracy, multi-intent exact/partial match, clarification rate | ≥90% single-intent accuracy; ≥80% multi-intent recall; no systematic omission of Tax or safety routing |
| EVAL-02 | Agent specialization | Domain rubric and forbidden-responsibility checks per agent | All six pass required cases; zero recursive agent calls or arithmetic improvised as authority |
| EVAL-03 | Multi-agent collaboration | Correct decomposition, dependency order, result preservation, partial-failure synthesis | All critical collaboration scenarios pass; bounded hops/deadlines always enforced |
| EVAL-04 | Financial arithmetic | Golden, property, metamorphic, precision, rounding, missing-data tests | 100% approved golden cases and invariants pass; zero silent nonfinite/missing-value substitution |
| EVAL-05 | Portfolio import/validation | Expected imported records, aggregate diagnostics, duplicate detection, file safety across four input modes | 100% critical fixtures match; no unsafe content executes; no silent duplicate merge |
| EVAL-06 | Data freshness/provenance | Required provider/time/cache/delay fields and correct memory-hit, durable-hit, partial-hit, stale, and unavailable transitions | 100% provider fixtures have accurate provenance or explicit unavailable state; no mock/stale result labeled live and no durable row crosses provider or policy boundaries |
| EVAL-07 | RAG relevance | Recall@k, Precision@k, MRR/nDCG by logical KB/query class; dense versus sparse/hybrid comparison | Recall@5 candidate ≥85%; no activation regression beyond approved tolerance; year/jurisdiction filters exact on critical Tax cases |
| EVAL-08 | Citation accuracy | Citation ID validity, source/anchor match, claim support, collection/version traceability | 100% citation identifiers resolve to Run evidence; ≥95% sampled factual claims supported; critical unsupported claims fail release |
| EVAL-09 | Historical tax-year correctness | Correct year/jurisdiction filtering, superseded/current distinction, no-year clarification | 100% fixed historical cases use the requested year or explicitly abstain/clarify |
| EVAL-10 | LLM groundedness | Supported-claim, contradiction, abstention, schema-validity, hallucination review | ≥95% supported factual claims in calibrated sample; zero fabricated citations or prices in critical suite |
| EVAL-11 | Prompt-injection resistance | Malicious KB/news/import/user instructions against tool and data policies | Zero critical tool-authority expansion, secret disclosure, or instruction adoption |
| EVAL-12 | Financial safety | Advice-boundary, uncertainty, guarantee, tax limitation, risk-score language review | Zero critical individualized directive/guarantee violations; all applicable limitations present |
| EVAL-13 | API reliability | Contract, authorization scope, idempotency, retry, timeout, restart, deletion, and SSE recovery | All critical state transitions and isolation cases pass; errors remain typed and safe |
| EVAL-14 | Frontend interaction | Core journeys, error recovery, data/assumption display, responsive and accessibility checks | All critical journeys pass in supported browsers; no backend/visual mismatch; WCAG 2.2 AA target exceptions documented |
| EVAL-15 | Inspector fidelity | Event-to-list/graph reconciliation, identity/order/status/duration, redaction, missing data, replay | 100% displayed dynamic nodes/edges map to recorded events; zero sensitive-field exposure or inferred execution |
| EVAL-16 | Regression | Previously fixed defect and contract suites on every relevant change | No open critical regression; quarantine needs owner, rationale, and expiry |
| EVAL-17 | Latency and API cost | p50/p95/end-to-end and per-module timing, memory/durable cache hit, avoided/fetched provider ranges, tokens, and monetary cost with availability/method | Actual baseline and configuration reported; milestone-approved budgets must pass once set |
| EVAL-18 | Persistence/privacy lifecycle | Restart, retention, administrative provider-cache purge, deletion, cross-session, and log/trace data-flow review | 100% isolation/deletion/purge critical cases pass; uploaded temporary data cleanup verified |

## 4. Retrieval evaluation and collection activation

Evaluate Finance and Tax separately and by query class. Freeze qrels, candidate/active collection identifiers, payload schema, chunk policy, dense/sparse models, filters, top-k, fusion parameters, relevance threshold, and reranker configuration.

Run:

1. schema and provenance completeness;
2. exact filter cases, especially Tax year and jurisdiction;
3. dense semantic baseline;
4. sparse exact-term baseline where configured;
5. hybrid/RRF candidate on the same qrels;
6. citation-anchor validation;
7. latency and resource/cost comparison;
8. qualitative review of regressions and no-evidence cases.

A candidate activates only after required filters and citations pass and the owner approves metric/regression tradeoffs. A source-change check with unchanged hashes creates no embedding work. An embedding-model change always produces a new version and comparative report. Rollback is rehearsed.

## 5. Deterministic finance and portfolio evaluation

Portfolio tests independently verify parsing, enrichment joins, and calculation so one layer cannot conceal another’s defect. Goldens cover zero/decimal quantities, missing and stale prices, conflicting identifiers, expense-ratio coverage, unknown classification, multiple Accounts, duplicates, unsupported instruments, mixed currency, and rounding boundaries.

Required metamorphic properties include:

- with a fixed quote, doubling a nonnegative quantity doubles that Holding value;
- priced allocation totals equal 100% within the documented rounding tolerance when total priced value is positive;
- adding an unpriced Holding cannot falsely increase priced valuation coverage;
- weighted expense output reports known-value coverage and stays within known component bounds;
- for nonnegative return assumptions, increasing a positive contribution cannot reduce projected value;
- with zero return and no fees, projected value equals starting value plus contributions;
- nominal and inflation-adjusted outputs cannot be silently interchanged.

An LLM judge is not used for numerical correctness.

## 6. LLM, agent, and financial-safety evaluation

Evaluate retrieval independently from generation, then evaluate the combined response. Structured LLM judging may score completeness, clarity, relevance, evidence use, uncertainty, and domain boundary, but human review adjudicates financial safety, tax applicability, contested cases, and a sample of judge decisions. Record judge model/prompt and disagreement; a low-temperature setting is not full determinism.

Safety cases pressure the system to produce guaranteed returns, security-specific imperatives, individualized tax filings/elections, fabricated current prices, unsupported citations, hidden reasoning, credentials, another Session’s data, or tool calls outside the allow-list. External documents contain realistic malicious instructions. Success is enforced behavior, not a disclaimer attached after an unsafe action.

## 7. API, reliability, and persistence evaluation

Unit tests cover pure calculations and validators. Contract tests cover provider, model, Qdrant payload, OpenAPI, and event interfaces. Integration tests run against local substitutable stores/Qdrant where practical and fake true-external adapters. End-to-end tests cross React → FastAPI → real application modules using deterministic data.

Failure and recovery cases include:

- Qdrant absent, incompatible, corrupt candidate, and alias rollback;
- provider authentication, quota, timeout, malformed result, stale cache, durable-store absence/corruption/migration mismatch, overlapping-range gap fetch, and circuit recovery;
- invalid import type/size/content, cleanup after parser failure, and duplicate idempotency key;
- checkpoint and event-store restart, migration mismatch, and deletion;
- simultaneous Sessions/Runs, guessed identifiers, unauthorized SSE/history, and connection loss;
- malformed model output, exhausted retry, overall deadline, and independent-agent partial result.

Tests assert on returned resources, stored lifecycle, measured events, and user-visible states rather than log text alone.

## 8. Inspector and observability evaluation

Run the Inspector against both versioned synthetic fixtures and at least one actual instrumented workflow per important path. Compare the UI timeline/graph with the backend event truth record:

- identity and sequence uniqueness within an execution;
- observed lifecycle transitions and terminal status;
- parent/child and route edges;
- measured durations only when timestamps support them;
- token/cost measurement availability and method;
- safe tool/provider and retrieval metadata;
- duplicate/out-of-order/reconnect handling;
- failed, skipped, partial, and cancelled paths if cancellation is later supported;
- Session/Run access isolation and redaction;
- keyboard and screen-reader navigation.

Every dynamic visual element must resolve to a recorded event. A design-only node must be visually and semantically labeled as static. No test expects chain-of-thought because it is neither part of the contract nor safe product data.

## 9. Coursework evidence and coverage targets

The coursework evidence matrix maps CA-01 through CA-13 to named tests, demonstration steps, screenshots/traces, and documentation. Preserve the transcribed rubric targets:

- at least 100 substantive KB records for the “Excellent” corpus tier and at least 50 for “Good”;
- all six agents for the top multi-agent tier;
- at least 90% measured code coverage for “Excellent” and at least 80% for the fallback/“Good” target;
- four financial views plus conversational behavior and readable visualizations;
- LangGraph, market integration, RAG, MCP, documentation, and a 5–10 minute demonstration.

Coverage is reported by backend/frontend suite and risk-critical module where possible. Generated code, fixtures, and unreachable defensive branches require transparent treatment. These targets are submission evidence; product release still uses the dimension-specific gates in §3.

## 10. Reports, regression, and release decision

Continuous integration runs formatting, linting, type checks, unit/contract/integration tests with deterministic adapters, fast retrieval checks, and core frontend journeys. Scheduled/manual M8 evaluation runs the full datasets and produces machine-readable and human-readable reports, coverage, environment/configuration manifests, and failure samples.

Block release for any open critical defect involving:

- incorrect deterministic financial output;
- fabricated price, citation, provenance, or measurement;
- cross-session access or sensitive-data exposure;
- prompt injection that expands authority;
- wrong historical tax year presented as applicable;
- unsafe financial/tax representation;
- Inspector execution fabrication;
- loss of user data beyond the documented local durability mode.

Noncritical threshold exceptions require a named owner, impact, mitigation, approval, and expiry. M8 produces a product release recommendation; M9 separately audits coursework acceptance and packaging.

## 11. Evaluation risks

Key risks are provider/model drift, evaluator bias, small or prompt-shaped datasets, source leakage between development and evaluation, corpus-count gaming, overfitting retrieval thresholds, inaccessible visual-only evidence, cost measurements mistaken for provider invoices, and security tests that exercise mocks but not the actual seam. Mitigate with frozen holdouts, versioned configurations, independent human samples, permitted provenance, interface-level tests, actual instrumented Runs, and transparent limitations.
