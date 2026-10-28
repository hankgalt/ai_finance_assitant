# M3 provider policy and activation gate

Version: `provider-policy-v2`

Status: Implemented for credential-free use; live activation remains entitlement-gated

Decision: ADR-024, ADR-025

This policy is the M3 implementation record for PR-004, PR-006, and PR-014. It does not grant data rights or replace the terms of an exact provider account.

## Selected adapters and modes

| Mode | MarketDataProvider | NewsProvider | Intended use |
| --- | --- | --- | --- |
| `credential_free` (default) | `FakeMarketDataProvider` | `FakeNewsProvider` | CI, local development, and deterministic private demonstration |
| `live` + `alpha_vantage` | `AlphaVantageMarketDataProvider` | `TavilyNewsProvider` | Conditional private demonstration after the activation gate passes |
| `live` + `massive` | `MassiveMarketDataProvider` | `TavilyNewsProvider` | Owner-only testing, or a shared demonstration covered by approved Business/commercial rights |

`AIFA_PROVIDER_MODE` selects one mode and `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive` selects one live market adapter before a workflow. `ProviderBundle` rejects mixed live/synthetic modes. Each live adapter additionally requires its explicit `AIFA_*_TERMS_APPROVED=true` activation flag; setting the flag records an operator decision but does not itself create legal rights. Missing credentials, an unapproved flag, an open circuit, or insufficient request budget makes live readiness fail and prevents a call; it does not silently select fake data or the other live market adapter. The M4 workflow must create one bundle per Run and retain its mode and actual provider in RunEvents.

Alpha Vantage supplies symbol search, `GLOBAL_QUOTE`, and compact `TIME_SERIES_DAILY`. Massive supplies ticker search, the previous-day aggregate, and unadjusted one-day aggregate ranges. Both quote paths are labeled end-of-day and daily bars historical; currency comes from the validated request when the price response does not establish it. Daily-bar volume is a bounded nonnegative Decimal because Massive's documented numeric `v` field can contain fractional values; adapters never truncate it. Massive authentication uses an authorization header rather than a URL query value. Tavily uses Search with `topic=finance`, basic depth, a maximum of ten results, an explicit date window, `include_answer=false`, and `include_raw_content=false`. It preserves article URL/host attribution and treats `published_date` as a provider estimate, not publisher-confirmed fact.

## Bounded execution policy

| Operation | Timeout | Attempts | Cache TTL | Stale-on-error window |
| --- | ---: | ---: | ---: | ---: |
| Alpha Vantage symbol search | 5 s | 2 | 24 h | 7 d |
| Alpha Vantage end-of-day quote | 5 s | 2 | 5 min | 1 h |
| Alpha Vantage raw daily history | 8 s | 2 | 6 h | 24 h |
| Massive ticker search | 5 s | 2 | 24 h | 7 d |
| Massive previous-day quote | 5 s | 2 | 5 min | 1 h |
| Massive raw daily history | 8 s | 2 | 6 h | 24 h |
| Tavily finance-news discovery | 8 s | 2 | 15 min | 1 h |

Default private-demo workflow budgets are five selected-market requests and three Tavily requests. Local rate bounds are five Alpha Vantage or Massive requests/minute and ten Tavily requests/minute, with at most two concurrent calls per adapter and 128 in-memory cache entries. These conservative application bounds do not override a lower provider/account limit. A demo owner must configure lower values when the account entitlement is lower.

Timeouts and 5xx failures may receive one bounded retry using exponential full jitter. Alpha Vantage HTTP 429 may use a bounded provider `Retry-After`; Massive HTTP 429 is not immediately retried because its public documentation does not establish a dependable reset header. Authentication, authorization, invalid request/symbol, malformed payload, local budget exhaustion, and plan exhaustion are not retried as transient failures. Alpha Vantage HTTP-200 `Note`/`Information` limit responses are likewise non-retryable because they can represent daily or plan exhaustion. Three consecutive retryable failures open the default circuit for 30 seconds. A stale cache result is returned only within the stated stale-on-error window and retains its original retrieval/data timestamp, cache age, failure cause, and stale warning. Otherwise the result is unavailable.

There is no automatic cross-provider fallback. Alpha Vantage and Massive are separately selected and separately entitlement-gated; a failure never combines their quote sets within one Run. Credential-free mode is also an explicit pre-Run selection, not a mid-Run fallback.

## Rights, privacy, and activation gate

The committed JSON files under `backend/data/providers/` are hand-authored, shape-equivalent synthetic fixtures. They are not captured provider payloads. yfinance is not an adapter because Apache-2.0 licensing of its code does not grant product rights to Yahoo Finance data. Massive's individual terms allow only the subscribing owner's personal use and do not permit showing its market data to testers, viewers, or other users; those cases require approved Business/commercial rights. See [the official-source Massive research](research/M3_massive_provider.md).

Before live mode may be called, record for each exact provider account:

1. permission for the controlled private demonstration and whether any organizational/commercial use is included;
2. permitted display, derived calculations, attribution, cache duration, persistent storage, fixtures, and redistribution;
3. enabled endpoints, asset coverage, realtime/delayed/end-of-day entitlement, timestamps, and adjustments;
4. account request/day, request/minute, monthly credit, concurrency, overage, and cost ceiling;
5. secret owner/rotation and a privacy review of outbound fields;
6. a declared demo call plan with headroom below every applicable limit.

The Tavily query must contain public topics/security symbols only. Portfolio rows, positions, account identifiers, transactions, payment-card data, tax data, user prompts containing financial context, and credentials must not be sent. Returned links/snippets remain untrusted third-party data and require source attribution; Tavily discovery does not confer republication rights. Massive credentials are sent only in the authorization header, and no captured market payload is committed.

No live call was made for M3 qualification because account-specific credentials and approvals were not available. The live-mode transcript therefore proves safe preflight refusal and zero external calls. This is within budget but is not evidence that live access, latency, data quality, or public-production rights are operational.

## Opt-in live account qualification

Tests marked `live_provider` are excluded by the default Pytest configuration and by all ordinary repository gates. After both credentials and explicit terms-approval flags are configured in the ignored `backend/.env`, run:

~~~bash
make provider-live-check
~~~

The explicit target enables the external-call gate and live mode, then uses `AIFA_MARKET_DATA_PROVIDER` to select Alpha Vantage or Massive. It performs at most three selected-market requests—symbol search, one end-of-day quote, and one 30-day daily-history request—and one bounded Tavily finance-news search. Each market operation is validated before the next request, so the test stops consuming market quota after the first failed operation. The Massive history window ends before the current Eastern date because Basic current-day data is unavailable until after midnight ET. Missing credentials, unapproved terms, readiness failure, authentication failure, quota/entitlement failure, contract drift, or malformed normalized results fail the explicit run. Application log formatting redacts query-string credentials and authorization values, and the test does not save raw responses. Repeated execution consumes fresh provider quota because the cache is process-local.

## Known limitations

- The cache and circuit are process-local and non-durable. M5 owns any persistent implementation and deletion policy.
- Alpha Vantage compact daily history may not cover a requested long window; an empty or partial bounded series remains explicit. Adjusted history and realtime/delayed U.S. data are not enabled.
- The Alpha Vantage quote/daily responses used here do not independently verify currency, exchange timezone, corporate-action adjustment, or identifier identity beyond the resolved symbol.
- Massive Basic is documented as end-of-day, five requests/minute, and two years of history, but the omission of a published daily cap is not a contractual guarantee. Current-day bars can return 403 until after midnight ET, and individual-plan data cannot be displayed to other people.
- Tavily publication dates can be estimated or missing. Source article facts and publication metadata are not independently fetched or verified in M3.
- Provider code is not yet reachable through REST or agents. M4 consumes the ports and emits measured provider RunEvents; M5/M6 own API/UI exposure.
- Live network and account-entitlement qualification remains incomplete and must be repeated after Alpha Vantage quota is available and the exact account rights are recorded. A future public release requires a separate commercial-rights decision.
