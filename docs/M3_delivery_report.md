# M3 delivery report — External market and news integrations

Status: Complete for the credential-free release path; conditional live adapters remain disabled by the documented activation gate

Completed: 2026-10-27

Scope: PR-004, PR-006, PR-014; QR-005, QR-007, QR-010, QR-011, QR-012, QR-014, QR-015; EV-05, EV-07, EV-09; ADR-006, ADR-011, ADR-012, ADR-019, ADR-023, ADR-024, ADR-025

## Outcome

M3 delivers application-owned MarketDataProvider and NewsProvider ports, normalized quote/history/instrument/news contracts, deterministic credential-free adapters, conditional Alpha Vantage or Massive market adapters, a conditional Tavily news adapter, and a bounded execution runtime for request budgets, local rate/concurrency limits, timeout/retry/full-jitter behavior, circuits, cache reuse, and stale-on-error results.

Provider selection is explicit and truthful. Credential-free mode is the default. A ProviderBundle cannot mix live and synthetic adapters, and `AIFA_MARKET_DATA_PROVIDER` selects Alpha Vantage or Massive before a live workflow. Live readiness and calls fail without credentials, explicit terms-approval flags, rights metadata, budget, or circuit availability and never change the selected mode or market adapter. The exact endpoint policy, rights gate, and limitations are in [M3 provider policy](M3_provider_policy.md).

## Delivered interfaces and evidence

- `providers.ports.MarketDataProvider`: instrument search, current quote, historical daily series, and readiness.
- `providers.ports.NewsProvider`: bounded dated-news discovery and readiness.
- `providers.ports.ProviderBundle`: one mode per future workflow/Run.
- `AlphaVantageMarketDataProvider`: conditional symbol-search, end-of-day quote, and raw daily-history adapter.
- `MassiveMarketDataProvider`: conditional ticker-search, previous-day quote, and raw daily-aggregate adapter using authorization-header credentials.
- `TavilyNewsProvider`: conditional attributed-link/snippet discovery with generated answers and raw content disabled.
- `FakeMarketDataProvider` and `FakeNewsProvider`: deterministic synthetic implementations of the same ports.
- `ProviderRuntime`: bounded in-memory cache, workflow budget, rate/concurrency limit, retry/full jitter, circuit, and stale-cache behavior.
- `backend/data/providers/`: hand-authored synthetic response fixtures with no captured provider content.
- `backend/artifacts/m3/`: privacy-safe test, coverage, failure-matrix, and demo-budget evidence.

## Acceptance evidence

| Acceptance statement | Result and evidence |
| --- | --- |
| Success, empty, delayed/end-of-day, cache, and stale states are observable | Contract tests verify normalized data, date-only/end-of-day labels, empty results, miss/hit age, and stale fallback with original retrieval time. |
| Provider failures are typed | Tests cover invalid request/symbol, 401, 403, 429/plan exhaustion, timeout, 5xx, malformed JSON/fields, unavailable, local rate, concurrency, budget, and open circuit. |
| Quotas are bounded before calls | Runtime preflight and reservation prevent HTTP when credentials, budget, local rate, concurrency, or circuit conditions fail. Repeated reads use the permitted cache without another call. |
| Synthetic or alternate-provider data cannot appear under the wrong selection | Frozen provenance validates that credential-free results are synthetic and live results are not. ProviderBundle rejects mixed modes. Settings select one mode and one live market adapter and do not silently fall back. |
| News remains attributed and minimized | Tests verify source host/URL, estimated/unavailable publication time, bounded excerpt, public query, and disabled answer/raw-content request fields. |
| Credential-free journey is reproducible | Fake adapters return deterministic quote, history, symbol, and news states without keys or network. Fixtures and tests are versioned. |
| Live mode stays inside the approved gate | With no approved credentials in the qualification environment, readiness refused the live journey and made zero external calls. This is a safe gate, not a claim of live-provider validation. |

## Verification record

Final qualification commands:

~~~bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m3-check
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify
cd backend && .venv/bin/pytest -q --cov=ai_finance_assistant --cov-report=json:artifacts/m3/coverage.json --cov-report=term tests
~~~

Observed results:

- Focused M3 suite: 31 passed.
- Backend formatting, Ruff, and strict mypy: pass.
- Full backend suite: 75 passed and 1 skipped; overall measured coverage 85%.
- The only skip is the existing opt-in live-Qdrant integration test because `AIFA_TEST_QDRANT_URL` was not configured; M1 records its separate live pass.
- Frontend formatting, lint, typecheck, 3 tests, and production build: pass.
- Live-provider calls: zero; both credentials were absent and readiness correctly blocked live mode.

Machine-readable results are `backend/artifacts/m3/test-results.json`, `coverage.json`, `failure-matrix.v1.json`, and `demo-budget-transcript.v1.json`.

## Security, privacy, and observability impact

- Credentials use server-side secret configuration and are never stored in results. Safe errors do not include provider payload text, keys, query strings, or response bodies, and JSON log formatting redacts query-string credentials and authorization values.
- External payloads are schema-validated and converted into bounded immutable models. Raw provider objects do not cross the adapter seam.
- Tavily receives only the public query field. The request deliberately omits portfolio/transaction context, generated answer, and raw article content.
- M3 emits no browser telemetry and adds no REST endpoint. M4 must record only bounded provider/mode/status/cache/freshness/attempt/count/timing fields in RunEvents; it must not record news queries, URLs containing secrets, payloads, or user financial context.
- The in-memory cache contains normalized public market/news results only. It is bounded and disappears with the process; no new user-data deletion lifecycle is introduced.

## Limitations and unresolved decisions

- The Massive and Tavily demo contracts were validated against the configured live accounts, but exact account entitlements and display rights were not independently verified. Alpha Vantage remains unqualified after a body-level account limit response. Live mode therefore still requires the documented per-provider terms and entitlement gate.
- The selected adapters do not establish rights for a future public or commercial release. That release needs a new contractual review and may choose different adapters behind the same ports.
- No automatic cross-provider fallback is implemented. Alpha Vantage or Massive is selected before a Run; stale cache is the only within-provider data fallback, and credential-free mode remains a separate pre-Run selection.
- Cache/circuit state is process-local. Durable cache storage, access control, retention, and deletion belong to M5.
- M3 does not calculate technical indicators, infer sentiment, summarize news, predict prices, expose API routes, or implement agents. Those are later-milestone concerns.

These limitations do not block the credential-free M3 interface milestone, M4 consumption, or the validated Massive-plus-Tavily private demo path. They do block any claim that public-production display rights or Alpha Vantage live access are operational.

## Post-completion live-test harness — 2026-10-28

Two integration tests marked `live_provider` exercise the selected application ports against an explicitly selected Alpha Vantage or Massive market account plus Tavily. The default Pytest marker expression excludes them, and `make provider-live-check` is the only repository target that enables their external-call gate. The target is bounded to at most three selected-market calls and one Tavily call; each market operation is asserted before the next begins. A diagnostic execution reached Alpha Vantage and received a body-level account limit after a successful symbol search; this is not a passing Alpha Vantage qualification result. After the Massive volume fix, `AIFA_MARKET_DATA_PROVIDER=massive make provider-live-check` passed both the selected-market search/quote/history contract and the Tavily news contract in 1.01 seconds. The Alpha adapter treats its ambiguous daily/plan-limit response as non-retryable, Massive 429 responses are not immediately retried, and log formatting redacts credentials embedded in HTTP client messages. Machine-readable exclusion and gating evidence is in `backend/artifacts/m3/live-test-harness.v1.json`.

Post-fix verification used `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m3-check` and `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify`. The focused provider suite passed 32 tests. The ordinary backend suite collected 80 tests, deselected both `live_provider` tests, passed 77, and skipped only the existing opt-in Qdrant integration; frontend formatting, linting, type checking, three tests, and production build passed. These verification commands made zero live-provider calls.

## Post-completion Massive adapter extension — 2026-10-28

ADR-025 adds `MassiveMarketDataProvider` without changing the application port. Hand-authored synthetic Massive fixtures cover ticker search, previous-day quote, raw daily history, provider request identifiers, cache reuse, 401, 403 entitlement, 429, 5xx retry, invalid request, and non-OK body validation. The factory explicitly selects Alpha Vantage or Massive and proves that an unavailable selected adapter never falls back to the other. The opt-in live test exercises the selected market adapter and stops after its first failed operation. [Massive adapter research](research/M3_massive_provider.md) records the official endpoint, plan-limit, recency, and owner-only rights evidence.

A bounded live diagnostic initially found that Massive returned fractional numeric volume for all 22 IBM daily bars while every required field, timestamp, price precision, and OHLC relationship was otherwise valid. The integer-only `PriceBar.volume` contract rejected that legitimate response. Volume is now preserved as bounded nonnegative Decimal across adapters, and the same one-request live history loop succeeded with 22 bars in one attempt. The complete selected-market plus Tavily live contract subsequently passed; account display rights remain a separate policy decision that the test cannot qualify.

Extension verification used `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m3-check`, `UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify`, and the full backend JSON-coverage command recorded above. The focused provider suite passed 42 tests. The ordinary backend suite collected 90 tests, deselected both `live_provider` tests, passed 87, and skipped only the existing opt-in Qdrant integration; overall backend coverage remained 85%. Frontend formatting, linting, type checking, three tests, and production build passed. The disabled selected-Massive live harness skipped both tests and made zero provider calls.
