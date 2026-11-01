# User guide

## What this release does

AI Finance Assistant is a U.S.-focused educational private demo. It can answer attributed Finance
and U.S. federal Tax education questions, import and analyze synthetic or user-supplied Portfolios,
show market data and financial news with provenance, calculate illustrative goal scenarios, and
show the measured execution timeline for an Assistant Run.

It does not place trades, choose investments, calculate a tax return, guarantee outcomes, or
replace a qualified financial, tax, or legal professional. Read the full [limitations and
disclaimer](limitations.md) before using non-synthetic data.

## Start and navigate

Follow the [developer guide](developer-guide.md) for local setup, then open
`http://127.0.0.1:5173`. The navigation exposes:

- **Assistant** for Finance, Tax, Portfolio, Market, Goal, and News questions;
- **Portfolio** to import, validate, save, select, analyze, and delete Portfolios;
- **Market** for current or historical market results with timestamps and source state;
- **Goals** for deterministic scenarios with visible assumptions;
- **Inspector** for the RunEvent timeline, graph, and measured details;
- **History** for Active and Archived Sessions.

Completed, partial, clarification, unavailable, and failed states are intentionally different. A
partial response contains usable results plus explicit missing inputs or failed dependencies. It is
not silently completed by a later response unless the new Run says so.

## Use the Assistant

Ask one bounded question at a time. Examples:

- `What is the difference between ETFs and mutual funds?`
- `What U.S. federal tax considerations apply to pension and annuity income for 2025?`
- `What is the latest financial news?`
- `How many holdings in my saved portfolio have usable prices?`

When a Portfolio question has no selected context, the Assistant asks for a saved Portfolio. The
selection remains Session-scoped for follow-ups. Use **Change portfolio** to switch context for the
next Portfolio question. If no Portfolio is saved, import one in the Portfolio view; the Assistant
does not display an empty selector.

The public Finance and Tax RAG paths may use the qualified Redis response cache. Portfolio,
Market, News, Goal, multi-agent, and context-bearing requests bypass it. Citations, tax year,
jurisdiction, freshness, synthetic state, and warnings remain part of the visible result.

## Import a Portfolio

Use **Import portfolio**, then choose Manual, JSON, CSV, or XLSX. Validate before saving. Import
findings identify row/field errors, duplicates, unsafe input, and missing values; the application
does not invent replacements. The [sample portfolio guide](../../examples/portfolios/README.md)
contains three synthetic credential-free examples and expected counts.

Saved Portfolio data, provider enrichment, and calculated snapshots remain separate. Deleting a
saved Portfolio permanently removes it and its snapshots from the current Session. Clearing the
Active Session archives it in History; permanent deletion is a separate action on an Archived
Session.

## Interpret Portfolio and Goal output

Portfolio totals include only holdings with usable prices. Coverage, currency, price source, and
warnings explain exclusions. Concentration and effective-holdings values are transparent
heuristics, not a suitability or risk score. Goal scenarios use user-controlled return, inflation,
fee, contribution, and timing assumptions. They are illustrations, not forecasts.

## Data and privacy

The demo binds to loopback and stores application state locally in SQLite. Qdrant and Redis are
local Docker services. Do not enter sensitive production financial data. External provider,
OpenAI, LangSmith, or OTLP export is optional and must be deliberately enabled by the operator.
The UI displays a trace correlation identifier, not hidden reasoning.
