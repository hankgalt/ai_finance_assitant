# M9 coursework and product evidence matrix

Date: 2026-10-31

| Criterion | Evidence | Demonstration step | Status |
|---|---|---|---|
| CA-01 — six agents | `docs/M4_delivery_report.md`; `backend/tests/test_agents.py` | Route single-domain cases and one collaboration | Pass |
| CA-02 — LangGraph/persistence | `backend/tests/test_workflow.py`; `backend/tests/test_workflow_application.py` | Portfolio context follow-up and Inspector route | Pass |
| CA-03 — attributed RAG | M1 manifests/evaluations; `backend/tests/test_knowledge_pipeline.py` | Finance and Tax citations | Pass |
| CA-04 — corpus count | Finance 106 points; Tax 6,295 points; immutable manifests | Show active manifests and explain non-gamed chunks | Pass, exceeds 100 records |
| CA-05 — market integration | `docs/M3_delivery_report.md`; provider adapter/live-marker tests | Synthetic quote; optional preflighted live quote | Pass |
| CA-06 — responsive web UI | `docs/M6_delivery_report.md`; `frontend/e2e/m6.spec.ts` | Assistant, Portfolio, Market, Goal, History | Pass |
| CA-07 — Portfolio analysis | M2 report/tests; `examples/portfolios/manifest.v1.json` | Import balanced JSON and verify totals/coverage | Pass |
| CA-08 — Goal projection | M2 report; `backend/tests/test_goal_projection.py` | Compare two visible scenarios | Pass |
| CA-09 — dated news | M3/M4 reports; provider and agent tests | Show attributed synthetic news | Pass |
| CA-10 — Tax education | Tax manifest; tax-year/filter/citation tests | Pension/annuity 2025 question | Pass |
| CA-11 — quality/fallbacks | M8 qualification, threat model, coverage, operator runbook | Show partial/unavailable path and correlation | Pass |
| CA-12 — runnable package/demo | Clean-start record, sample guide, benchmark and demo script | Execute the eight-minute credential-free script | Pass |
| CA-13 — read-only MCP | MCP client record and `backend/tests/test_mcp_adapter.py` | External stdio list/invoke | Pass |

Product PR-001 through PR-015 mappings are machine-checked in
`backend/data/evaluation/m9_release_manifest.v1.json`. Every referenced evidence path exists, the
M8 qualification report passes, sample checksums reproduce, and the MCP surface declares no
mutation tools.

## Coverage and substitution statement

Backend coverage is 87.28%. Frontend V8 coverage is 80.25% lines, 78.43% statements, 64.47%
branches, and 73.79% functions. Only the line measure meets the transcribed 80% fallback; neither
suite reaches the 90% “Excellent” target. Risk-critical arithmetic, access, redaction, and event
truth retain specific behavioral gates independent of aggregate coverage.

React replaces the named Streamlit option and Qdrant replaces FAISS for the reasons in the
developer guide. The implementation demonstrates the required behaviors but does not claim that
the external instructor has pre-approved grading equivalence. The repository follows the stricter
interpretation that CA-13 is required.
