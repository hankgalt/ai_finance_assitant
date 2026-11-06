# 5–10 minute private-demo script

Target duration: 8 minutes. Default provider mode: credential-free. External request budget: zero.
All imported positions and prices are synthetic.

## 0:00–0:45 — Scope and readiness

Show `/api/health/ready`, name the private-demo boundary, and state that the product provides
education and deterministic analysis—not trades, forecasts, individualized advice, or tax-return
preparation. Point out the credential-free provider/model labels.

## 0:45–2:00 — Finance and Tax retrieval

Ask `What is the difference between ETFs and mutual funds?` and show attributed Finance evidence.
Ask `What U.S. federal tax considerations apply to pension and annuity income for 2025?` and show
the tax year, jurisdiction, and IRS citations. Explain that active Qdrant collections are built
offline and runtime does not regenerate embeddings.

Optional cache demonstration: repeat or closely paraphrase the Finance question. In serving mode,
show lower latency only when the approved evidence/version-bound match exceeds the cutoff. A miss is
correct and falls through to normal generation.

## 2:00–3:30 — Portfolio workflow

Open Portfolio, import
[`balanced_multi_account.json`](../../examples/portfolios/balanced_multi_account.json), validate,
save, and analyze it. Verify three Accounts, seven Holdings, explicit synthetic user-price warnings,
coverage, allocations, and the accessible table. Explain that imported records, provider enrichment,
and calculated snapshots are separate.

## 3:30–4:45 — Contextual Assistant follow-up

Ask `How many holdings in my saved portfolio have usable prices?` Select the saved Portfolio if
prompted. Follow with `Which asset class is most concentrated?` to demonstrate Session-scoped
Portfolio context. Open **Change portfolio** to show how the user can explicitly switch context.

## 4:45–5:45 — Market, News, and Goal

Show the Market view using the synthetic provider and point out provider, timestamp, freshness, and
synthetic labeling. Ask for the latest financial news and show attributed fixture articles. In Goals,
run two user-controlled return scenarios and point out nominal/real values, assumptions, and the
no-guarantee warning.

## 5:45–6:45 — Multi-agent and Inspector

Ask `How can fund fees and taxable distributions affect a long-term ETF versus mutual-fund choice?`
Show the Finance + Tax synthesis. Open Inspector and reconcile numbered graph nodes with the ordered
RunEvent timeline; show that missing measurements remain unavailable rather than inferred.

## 6:45–7:30 — Session lifecycle and failure behavior

Clear the Active Session and show it under Archived History. Demonstrate that an Archived Session is
read-only and permanent deletion is separate. If time permits, show an unavailable-provider fixture
or a partial response with an explicit warning.

## 7:30–8:00 — MCP and evidence

Run `cd backend && uv run pytest -q tests/test_mcp_adapter.py` or show its recorded result. Explain
that the stdio client discovered and invoked four read-only tools over the same modules. Close with
the M8 qualification report, backend 91.55% coverage, frontend 93.85% line coverage, and the public-
deployment limitations.

## Optional live variation

Only after preflight, substitute one live quote and one Tavily news query. Keep the provider smoke
ceiling at three selected-market requests plus one Tavily request, retain all provenance labels, and
do not use Massive individual-plan output for an audience beyond the owner without approved rights.
If any live readiness check fails, return to the credential-free script; do not silently mix modes.
