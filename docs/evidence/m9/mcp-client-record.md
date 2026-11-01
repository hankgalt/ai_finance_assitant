# M9 MCP client record

Date: 2026-10-31

Adapter: `read-only-mcp-v1`  
Transport: stdio  
SDK: official Python `mcp` package, locked to 2.3.0

## Exposed surface

| Tool | Shared authority | External world | Mutation |
|---|---|---|---|
| `search_education` | active `KnowledgeRetrieval` | no | none |
| `get_market_quote` | configured `MarketDataProvider` | provider-dependent | none |
| `analyze_portfolio` | `PortfolioImport` + `PortfolioAnalysis` | no | in-memory only; stores nothing |
| `project_goal` | `GoalProjection` | no | none |

All four protocol descriptions advertise `readOnlyHint=true`, `destructiveHint=false`, and
`idempotentHint=true`. There are no Session, saved-Portfolio, delete, administration, credential,
trade, or arbitrary-tool surfaces. Tax retrieval requires an explicit year; retrieval and provider
failures return sanitized tool errors. Inputs use the same bounded Pydantic/domain contracts as the
application modules.

## Client evidence

Command:

```text
cd backend && uv run pytest -q tests/test_mcp_adapter.py
```

Result: `2 passed in 2.14s`.

The first test uses the SDK client against an in-memory protocol server and invokes all four tools,
verifying attributed retrieval, synthetic quote provenance, deterministic Portfolio total, Goal
warnings, and annotations. The second launches
`python -m ai_finance_assistant.mcp_adapter` as an external stdio subprocess, lists the surface, and
invokes `get_market_quote`. It loads `.test.env` and a temporary SQLite path; no live credential or
external request is used.

Static quality run: Ruff format/check passed, strict mypy reported no issues in 136 source files,
and the two protocol tests passed. The final full-suite result is recorded separately by the M9
clean-start record.
