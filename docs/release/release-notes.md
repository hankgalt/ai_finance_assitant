# Release notes — private-demo-2026-10-31

## Delivered

- Exactly six specialist agents in a bounded LangGraph workflow with single/multi-agent routing,
  Session-scoped follow-up context, clarification, partial results, and measured RunEvents.
- Persistent versioned Finance and Tax Qdrant collections with dense+sparse hybrid retrieval,
  metadata filters, citations, tax-year handling, offline activation, and rollback records.
- Deterministic Portfolio import/analysis and Goal projection, conditional market/news providers,
  durable historical price cache, and qualified public-RAG Redis response caching.
- Versioned FastAPI REST/replayable SSE, durable local SQLite/checkpoints, archive/history/delete
  lifecycle, and responsive React Assistant, Portfolio, Market, Goal, History, and Inspector views.
- Optional OpenAI, LangSmith, and OpenTelemetry adapters with credential-free deterministic paths.
- Four-tool read-only MCP stdio adapter plus in-memory and external-client protocol tests.
- M8 release qualification and M9 user/developer/operator/coursework packaging.

## Qualification snapshot

The final M8 report passed EVAL-01 through EVAL-18 with zero critical failures or incomplete gates.
The M9-regenerated qualification has 274 backend tests, 35 frontend tests, nine browser journeys,
real Qdrant, and real Redis checks passing. Backend coverage is 87.28%. M9 adds measured frontend line coverage of
80.25% and closes the previous "coverage unavailable" risk. A 2026-11-05 test-only update raised
backend coverage to 91.46% and frontend coverage to 93.85% lines and 92.98% statements across every
application module; see the [coverage report](../evidence/m8/coverage.md). Post-release M2.1 adds
cost-basis unrealized gain/return and top-five concentration to Portfolio Snapshots; see the
[M2.1 delivery report](../M2_1_delivery_report.md). The final M9 command record is in the
[clean-start record](../evidence/m9/clean-start-record.md).

## Compatibility and upgrade notes

This is a new owner-only private-demo package, not a public API compatibility commitment. SQLite
schema version 3 is required. Active Qdrant aliases must satisfy the exact collection/model/schema
contract. The new `mcp` Python dependency is locked, and frontend coverage adds
`@vitest/coverage-v8` as a development dependency. Use the [operator runbook](operator-runbook.md)
for rollback boundaries.

## Known limitations

See [limitations and disclaimer](limitations.md). M10 cash-flow import, public identity/multi-user
authorization, managed storage/backup/HA, approved public-provider rights, and public SLO/load
capacity are not part of this release.
