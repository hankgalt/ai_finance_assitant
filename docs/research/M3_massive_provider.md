# M3 Massive market-data adapter research

Status: M3 extension decision input, not an access-rights approval

Researched: 2026-10-28

Scope: PR-004/PR-006/PR-014, QR-005/QR-007/QR-010/QR-011/QR-012/QR-014/QR-015, ADR-006/ADR-011/ADR-012/ADR-019/ADR-023/ADR-024

This note evaluates Massive (formerly Polygon.io) as a second conditional `MarketDataProvider` adapter for the private-demo release. It uses Massive's current first-party documentation and terms. Product names, plan entitlements, limits, and terms can change; the exact account and order form remain authoritative. This is engineering research, not legal advice.

## Recommendation

Implement a conditional `MassiveMarketDataProvider` behind the existing application-owned port, with deterministic synthetic contract tests and an opt-in live-account test. Keep Alpha Vantage available. Add an explicit market-adapter setting such as `AIFA_MARKET_DATA_PROVIDER=alpha_vantage|massive`; select it before a Run and retain the selected provider in provenance. Do not automatically switch providers after a quota or availability failure, because a mid-Run switch would make the quote set inconsistent and would violate the current explicit-selection policy.

Massive is technically attractive for a personal owner-only demonstration: Stocks Basic publishes a five-request-per-minute cap, two years of historical aggregates, end-of-day data, reference data, and no documented daily request cap. However, the published pricing page's omission of a daily cap is not a contractual promise that no account-specific ceiling exists. Configure the adapter from the actual account entitlement and keep a finite per-workflow budget.

The individual-plan rights are the larger constraint. Massive's current Market Data Terms limit individual market-data use to personal, non-business, non-commercial use and prohibit building an application intended for anyone other than the subscriber. Massive also says that showing data to testers, staging users, customers, or other viewers requires a Business subscription or other commercial license. Therefore the adapter may be implemented and exercised by the owner, but it must remain entitlement-gated for any demonstration where another person can see the market data. ([Market Data Terms](https://www.massive.com/legal/market-data-terms-of-service), [redistribution guidance](https://massive.com/knowledge-base/article/how-can-i-redistribute-massives-market-data), [account guidance](https://massive.com/knowledge-base/categories/account))

## API and contract mapping

Massive's REST base URL is `https://api.massive.com`. It accepts an API key either as `apiKey` in the query string or as `Authorization: Bearer ...`. The adapter should use the authorization header so credentials do not enter URLs, access logs, or request identifiers. ([REST quickstart](https://massive.com/docs/rest))

| Application operation | Massive endpoint and mapping | Contract implications |
| --- | --- | --- |
| Instrument search | `GET /v3/reference/tickers` with `market=stocks`, `active=true`, bounded `search`, and `limit` | Map `ticker`, `name`, `locale`, and `currency_name` to `InstrumentMatch`. Massive does not provide a comparable match score, so leave it unavailable. The endpoint is included in all Stocks plans and reference data is updated daily. |
| End-of-day quote | `GET /v2/aggs/ticker/{ticker}/prev` with an explicit `adjusted` choice | Use the most recent returned daily bar's close as the quote, retain the bar timestamp, label it end-of-day/date-only, and never describe it as current realtime data. The endpoint is included in all Stocks plans. |
| Daily history | `GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}` with `sort=asc`, `adjusted=false`, and a bounded limit | Map `o`, `h`, `l`, `c`, numeric `v`, and Unix-millisecond `t` to raw daily `PriceBar` records. Preserve fractional volume as a bounded nonnegative Decimal rather than truncating it, retain `request_id`, report `AdjustmentBasis.RAW`, and treat a successful empty `results` array as an observable empty result. |

The ticker-search response can include `next_url`; the aggregate response can also include it. A search request is already bounded to ten application results, so the first page is sufficient. The application's maximum ten-year daily range is fewer than the aggregate endpoint's 50,000-base-aggregate limit when requesting one-day bars, but the adapter should still reject or safely follow an unexpected `next_url` rather than silently presenting a partial series. Never forward a `next_url` to a browser, and do not assume it excludes credentials. ([All Tickers](https://massive.com/docs/rest/stocks/tickers/all-tickers), [Custom Bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars), [Stocks endpoint overview](https://massive.com/docs/rest/stocks/overview))

Massive's aggregate bars can be adjusted for splits. The first adapter should request `adjusted=false` to match the existing raw-history contract and avoid presenting provider-adjusted data as raw. If adjusted bars are later enabled, the selection must be explicit and the provenance must change to `AdjustmentBasis.ADJUSTED`. ([Custom Bars](https://massive.com/docs/rest/stocks/aggregates/custom-bars))

## Free-tier recency and request policy

Stocks Basic currently advertises five API calls per minute, two years of historical data, end-of-day data, reference data, and minute aggregates. The current pricing page does not publish a daily request cap for Basic; paid Stocks tiers are described as having unlimited API calls. The implementation should record the exact account's limits rather than translating “no published daily cap” into an unbounded runtime. A safe initial local configuration is five requests per minute with a three-request workflow qualification budget, while the demo retains headroom and uses cache hits for repeated views. ([Stocks pricing](https://massive.com/pricing?product=stocks))

On Stocks Basic, a trading day's REST aggregates are not available until after midnight Eastern Time, when that day is no longer current. A request for the current Eastern trading date can return HTTP 403 even after the market closes. Live tests must therefore use the previous accessible trading day, and normalized results must remain labeled end-of-day. Paid Starter/Developer tiers advertise 15-minute delayed data, while Advanced advertises realtime data; the adapter must not infer these entitlements from the presence of a key. ([Basic end-of-day availability](https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data), [Stocks pricing](https://massive.com/pricing?product=stocks))

For an account entitled to delayed current-day aggregates, Massive can return HTTP 200 with schema-valid bars and body status `DELAYED`. Massive explicitly defines that status as usable delayed data rather than an error, so an adapter may accept it only after ordinary payload validation and must preserve delayed provenance. A range ending before the current date returns `OK` on the same delayed account. ([Massive delayed REST status guidance](https://massive.com/knowledge-base/article/how-quickly-can-i-access-massives-market-date))

The two-year Basic history window rolls forward with the request date. An older range can return HTTP 403 `NOT_AUTHORIZED`; a successful response may also omit bars before the entitled window, so the adapter must preserve the returned first/last data dates and make partial coverage visible. ([historical coverage](https://massive.com/knowledge-base/article/how-much-historical-stock-data-does-massive-have))

## Failure normalization

Normalize failures without retaining raw bodies or secrets:

- HTTP 401: `UNAUTHORIZED`; a missing or invalid key is not retryable.
- HTTP 403: `ENTITLEMENT_REQUIRED` when the key is valid but the product, endpoint, recency, exchange agreement, or history window is unavailable; it is not retryable within the same request.
- HTTP 429: `RATE_LIMITED`. Massive documents the five-per-minute Basic threshold but does not document a dependable `Retry-After` contract. Do not immediately retry within the live test; expose the limit and let a later workflow retry after the operator-controlled window.
- HTTP 5xx, connection errors, and timeouts: `UNAVAILABLE` or `TIMEOUT`, eligible for the existing single bounded retry and circuit behavior.
- HTTP 200 with body status `DELAYED` and schema-valid aggregate bars: success with `DelayStatus.DELAYED`, not an error or realtime result.
- HTTP 200 with `status=OK` and no results: `EMPTY`, not an outage.
- Invalid JSON, missing fields, non-finite values, or invalid OHLC relationships: `MALFORMED_RESPONSE`.

Massive commonly returns a `request_id` in response bodies and an `x-request-id` header. Retain the bounded identifier for support correlation, but do not retain request URLs or response bodies. Massive explicitly distinguishes 401, 403, and 429 entitlement/rate responses from service outages. ([authorization failures](https://massive.com/knowledge-base/article/why-am-i-not-authorized-when-attempting-to-connect-to-massives-websockets), [status guidance](https://massive.com/knowledge-base/article/does-massive-have-a-system-status-page), [request identifiers](https://massive.com/knowledge-base/article/how-should-i-go-about-reporting-a-possible-massive-data-discrepancy))

## Rights and activation gate

Before `AIFA_MARKET_DATA_PROVIDER=massive` can be used, record for the exact account:

1. whether only the subscribing owner will see the data, or a Business/commercial agreement covers every approved viewer and tester;
2. permitted display, derived calculations, attribution, in-memory and persistent caching, storage duration, screenshots/recordings, fixtures, and redistribution;
3. Stocks product/tier, historical window, data delay, enabled endpoints, and any required exchange agreements;
4. request/minute and any account-specific daily, concurrency, or abuse-prevention limits;
5. secret owner/rotation and confirmation that authorization headers and provider payloads are redacted;
6. a declared demo call plan below the configured limits.

The public individual terms prohibit redistribution and broadly restrict display, derived works, copying, and server publication absent additional consent. Do not assume that an in-memory or persistent cache is permitted merely because the API technically returns data. Hand-author synthetic contract fixtures unless the exact agreement explicitly permits storing and committing captured provider responses. ([Market Data Terms](https://www.massive.com/legal/market-data-terms-of-service), [redistribution guidance](https://massive.com/knowledge-base/article/how-can-i-redistribute-massives-market-data))

## Implementation acceptance additions

- `MassiveMarketDataProvider` satisfies the existing search, quote, history, readiness, provenance, stale/cache, and typed-error contracts without changing the port.
- Configuration independently selects provider mode (`credential_free|live`) and live market adapter (`alpha_vantage|massive`); the selected NewsProvider remains Tavily.
- A `ProviderBundle` remains one mode and one selected market provider for a Run. Quota failure never causes an automatic Alpha-to-Massive or Massive-to-Alpha switch.
- Credential-free and ordinary CI tests make no Massive calls. Hand-authored synthetic fixtures cover success, empty, 401, 403, 429, timeout, 5xx, malformed response, partial history, cache, budget, rate, and circuit behavior.
- A separate `live_provider` Massive test requires an explicit execution gate, API key, terms flag, selected market adapter, and a three-request budget. It stops after the first failing operation and uses only dates available to Stocks Basic.
- The live-test result records the exact account tier and observed delay/coverage without claiming public-production rights.

## Unresolved account questions

The official public material does not prove that the user's exact account has no daily or abuse-prevention ceiling, does not document a reliable `Retry-After` header for 429 responses, and does not grant a private-demo right when anyone other than the individual subscriber sees the data. Those items require dashboard/account evidence or written confirmation from Massive before live activation beyond owner-only testing.
