# Coursework acceptance criteria

Version 1.0 | Status: Required for the coursework release | 2026-10-26

## 1. Purpose and source authority

This document isolates capstone obligations from enduring product requirements while preserving their mandatory status for submission. It reflects the source labels and rubric values already captured in the repository: *AI Finance Assistant — Problem Statement* (PS), *Project Milestones* (PM), *Grading Rubric_AI Finance Assistant* (GR), and coursework roadmaps. Those original artifacts are not present in this repository, so this document preserves the repository's transcription rather than claiming a new audit of the source files.

Where those sources disagree, the coursework release follows the stricter interpretation until the instructor confirms otherwise. Product architecture may exceed or replace a recommended technology when the source permits alternatives, but the submission must demonstrate equivalent behavior and document the rationale.

## 2. Mandatory coursework capabilities

| ID | Transcribed source | Acceptance requirement | Product mapping | Delivery and evidence |
|---|---|---|---|---|
| CA-01 | PS §2–3; GR | Six distinct agents: Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, and Tax Education | PR-001 through PR-007 | M4; six single-agent cases and multi-agent runs |
| CA-02 | PS §2; PM §5; GR | LangGraph StateGraph orchestration with routing, conditional transitions, collaboration, and persistent conversation | PR-002, PR-013 | M4; routing, aggregation, follow-up, and restart/isolation tests |
| CA-03 | PS §3; PM §2,6; GR | Curated RAG knowledge with metadata and source attribution | PR-008, QR-008 | M1 and M4; corpus manifest, retrieval evaluation, citation checks |
| CA-04 | Existing GR tiers | A defensible corpus count: 50+ records for the transcribed “Good” tier and 100+ for “Excellent” | PR-008 | M1/M9; count only substantive, permitted, non-duplicate records |
| CA-05 | PS §3; PM §8; GR | Current and historical market integration using an approved provider such as Alpha Vantage or yfinance | PR-004 | M3; timestamped success, stale, rate-limit, and unavailable demonstrations |
| CA-06 | PS §3; PM FAQ; GR | A responsive web interface with conversation, Portfolio, Market, and Goal views and readable visualizations | PR-010 | M6; browser tests and accessible alternatives |
| CA-07 | PS §5; PM FAQ | Structured portfolio input and deterministic valuation, allocation, diversification, and expense analysis | PR-003 | M2/M6; exact numerical fixtures and import cases |
| CA-08 | PS §5; PM §4 | Goal projections using horizon, contributions, return assumptions, and declared risk tolerance | PR-005 | M2/M6; scenario fixtures and UI tests |
| CA-09 | PS §2; PM §4 | Dated, attributed financial-news synthesis | PR-006 | M3/M4; provider and failure cases |
| CA-10 | PS §2; PM §4 | Source-grounded U.S. tax education | PR-007, PR-008 | M1/M4; tax-year and jurisdiction cases |
| CA-11 | PS §3–5; GR | Error handling, logging, fallbacks, and reproducible tests and documentation | QR-001 through QR-015 | M0–M9; test reports and delivery evidence |
| CA-12 | PS §5; PM FAQ | Runnable submission, sample data, benchmark summary, and a 5–10 minute demonstration | PR-014 | M9; clean-run record and evidence matrix |
| CA-13 | PS §3, §6; PM §11; GR | Read-only MCP capability backed by the same validated application modules | PR-015 | M9; client invocation and configuration evidence |
| CA-14 | GR | Optional innovation for bonus credit after core criteria are secured | Planned, not a product gate | M9; measurable before/after evidence only |

CA-01 through CA-13 remain coursework obligations. “Optional” in a milestone or FAQ does not override a scored rubric item without instructor confirmation. CA-14 is genuinely optional.

## 3. Preserved grading evidence model

The repository previously transcribed these categories: technical implementation 40 points (multi-agent 10, LangGraph 10, RAG 8, market/data 7, MCP 5); user experience 25 (web 10, conversation 8, visualizations 7); finance knowledge 20 (education 8, portfolio 7, market insights 5); code and documentation 15 (code 5, documentation 5, testing 5); and innovation up to 10 bonus points. Confirm this allocation against the authoritative rubric before submission.

Coverage thresholds are coursework targets, not proof of release quality:

- 90% or greater is the transcribed “Excellent” target.
- 80% or greater is the transcribed fallback or “Good” target.
- Financial arithmetic, authorization, isolation, and trace-redaction cases still require their specific quality gates even if aggregate coverage is high.

## 4. Technology reconciliation

| Coursework wording | Product decision | Required submission treatment |
|---|---|---|
| FAISS is named in a milestone | Persistent Qdrant is selected by ADR-016 | Demonstrate equivalent or stronger RAG behavior and explain persistence, filtering, hybrid retrieval, and reproducibility |
| Streamlit is named in a grading criterion | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts, and React Flow are selected by ADR-007/015 | Map each evaluated UI behavior to the React implementation and do not promise grade equivalence without confirmation |
| Gemini 2.0 Flash and a 60 RPM tier were historical guidance | The model provider remains configurable | Record the actual model, limits, cost, and configuration used for evaluation |
| Four or five agents are permitted in one FAQ while PS/GR expect six | Six agents are required | Demonstrate all six; staged implementation does not reduce the final obligation |
| Testing is called optional in one milestone but scored in GR | Testing is mandatory for submission | Supply measured test and coverage artifacts |
| MCP is described inconsistently as optional or bonus while allocated points | Treat MCP as required for the coursework release pending clarification | Keep it after core product modules but include evidence at M9 |

## 5. Coursework demonstration checklist

The final demonstration must show actual behavior, not the presence of files or library imports:

1. Route representative requests to each of the six agents.
2. Show at least one correct multi-agent collaboration and one clarification or partial-result path.
3. Retrieve attributed Finance and Tax knowledge from active Qdrant collection versions.
4. Import a portfolio sample and verify deterministic totals and missing-value handling.
5. Show current or clearly labeled stale/unavailable market data and dated news.
6. Show goal scenarios with assumptions and no guarantee language.
7. Use the React application’s four financial views and conversation experience.
8. Show the Agent Execution Inspector from captured LangGraph events, including a failure or partial run.
9. Demonstrate isolation, prompt-injection handling, and provider failure behavior.
10. Invoke the read-only MCP interface if CA-13 remains scored.
11. Present actual test, retrieval, latency, token/cost, and coverage results with configuration identifiers.

## 6. Open coursework confirmations

- Obtain the authoritative rubric and confirm the point allocation, corpus thresholds, and whether MCP is core or bonus.
- Confirm that the React implementation receives equivalent consideration to the named Streamlit criterion.
- Confirm whether a provider named in the milestones is compulsory or illustrative.
- Confirm submission packaging and recording requirements.

Until resolved, the implementation plan retains the stricter deliverables.
