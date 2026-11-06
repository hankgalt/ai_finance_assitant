# Limitations and disclaimer

This release is educational software for an owner-only private demonstration. It is not financial,
investment, tax, accounting, or legal advice. It does not know the user's full circumstances, act as
a fiduciary, place or authorize trades, prepare a tax return, make elections, predict markets, or
guarantee results. Users remain responsible for verifying source dates and consulting qualified
professionals where appropriate.

## Product limitations

- Portfolio analysis uses supplied/imported data and available prices. Missing prices,
  classifications, currencies, fund look-through holdings, correlations, goals, or risk context
  reduce coverage and can produce a partial result.
- Diversification and concentration measures are versioned heuristics, not individualized
  suitability decisions. Overlap cannot be quantified without underlying-holdings data.
- Goal results depend entirely on declared scenarios and simplify taxes, sequence risk, market
  variation, and changing circumstances.
- Tax education is limited to supported U.S. federal years/jurisdiction and indexed authoritative
  material. State/local rules and unsupported years require abstention or explicit limitation.
- News and market data may be delayed, stale, cached, rate-limited, unavailable, synthetic, or
  restricted by provider rights. News is not a price predictor.
- Semantic cache matches are limited to qualified public Finance/Tax RAG responses and can miss.
  The cutoff reduces but cannot mathematically eliminate all semantic false-match risk.
- LLM output can be incomplete or erroneous. Citations, deterministic calculations, provenance,
  warnings, and Inspector events should be reviewed rather than treating fluent text as authority.

## Deployment limitations

There is no public identity provider, public multi-user authorization, managed encryption/backup,
high availability, disaster recovery, WAF, distributed quota control, or public capacity/SLO claim.
SQLite, local unauthenticated Qdrant/Redis, Vite, and loopback FastAPI are appropriate only for the
documented private-demo boundary. External telemetry retention and sampling are operator/vendor
settings, not enforced after export. Live-provider display/retention rights remain account-specific.
Proposed ADR-030 and M11 plan a private multi-user GCP deployment but do not change these current
release limitations until their implementation and qualification evidence passes.

Portfolio unrealized gain and return (M2.1) are price change against imported cost basis only.
They exclude dividends, distributions, separately paid fees, taxes, and cash flows, use one basis per
Holding, are not time-weighted or money-weighted returns, and are not forecasts. History-based
volatility, drawdown, and risk-adjusted metrics are not implemented.

Backend coverage is 91.55% and frontend coverage is 93.85% lines and 92.98% statements, meeting
the transcribed 90% "Excellent" target. Frontend branch coverage (78.53%) remains below 90% and is
reported separately. Real Qdrant and Redis behavior is still proven only by the opt-in marked
integration tests; the CI coverage for those adapters uses deterministic fakes.
