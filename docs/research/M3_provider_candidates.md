# M3 market and news provider candidate research

Status: M3 decision input, not an accepted provider decision

Researched: 2026-10-27

Scope: PR-004/PR-006/PR-014, QR-005/QR-007/QR-010/QR-011/QR-012/QR-014/QR-015, ADR-006/ADR-011/ADR-012/ADR-019/ADR-023

This note evaluates Tavily, Alpha Vantage, and yfinance against the M3 provider seam. A service being publicly reachable, free, or easy to call is not approval to use its data in the product. M3 still requires an identified license/entitlement, cache and display rights, contract fixtures, failure tests, and a recorded selection decision. This is engineering research, not legal advice.

The confirmed release target is a production-oriented private demonstration release, not a public launch. The demonstration must stay within the exact provider plan's terms and configured request limits. It also needs a separately selected credential-free mode that demonstrates the same product states with labeled deterministic data; a Run must never mix live and fake provider results.

## Recommendation

1. Implement `MarketDataProvider` and `NewsProvider` contracts plus deterministic fake adapters before selecting any live adapter. Continuous integration and the credential-free demo use fakes, while an explicitly selected live-demo mode may use an approved provider within its predeclared request budget.
2. Treat **Alpha Vantage as a conditional MarketDataProvider candidate** for end-of-day quotes and historical OHLCV. Do not call it the production provider until written terms cover the intended application, users, display, caching, and redistribution. Realtime or 15-minute-delayed U.S. data also requires the appropriate paid exchange entitlement.
3. Treat **Tavily as a conditional NewsProvider discovery candidate**, not a financial-news publisher or market-data authority. Request links and attributed snippets, disable its generated answer, preserve the original publisher, and independently validate publication time and source rights. Do not send portfolio holdings, user financial data, or other sensitive context in search queries.
4. **Do not select yfinance as the production MarketDataProvider.** It is useful for an individual's local research spike, but it is unofficial, has no product SLA or contractual entitlement, and its own documentation says the underlying Yahoo Finance API is for personal use only. Its Apache-2.0 code license does not license Yahoo's data.
5. Alpha Vantage's `NEWS_SENTIMENT` can be a comparison candidate if its commercial terms are approved, but M3 should not use provider sentiment as fact or as a price prediction. The news contract should preserve article-level attribution and let the News Synthesizer distinguish facts from interpretations.

## What the M3 ports mean

The ports are application-owned contracts, not wrappers that leak a vendor's response shape.

### MarketDataProvider

The minimum M3 interface should cover symbol/identifier resolution, one current quote, and a bounded historical series. A normalized quote or bar needs:

- requested and resolved security identifier;
- price and currency;
- market/data timestamp and application retrieval timestamp;
- provider and provider request/reference identifier when supplied;
- explicit realtime, delayed, end-of-day, historical, stale, cached, or unavailable state;
- cache status and expiry;
- adjustment basis for historical data;
- typed warnings/errors without raw credentials or unrestricted payloads.

Provider adapters own authentication, response validation, provider-specific error detection, rate limiting, bounded retry/jitter, circuit behavior, and cache policy. Portfolio analysis consumes a consistent quote set; it does not call a vendor directly.

### NewsProvider

The minimum interface should accept a bounded topic/security query and time window and return zero or more attributed `NewsItem` records containing:

- publisher/source name, canonical article URL, and provider result identifier;
- title and a bounded attributed excerpt when permitted;
- publisher-reported publication time, or an explicit unavailable/estimated state;
- application retrieval time and provider;
- matched topics/security identifiers;
- freshness/cache status and safe warnings.

The provider does not author the final product summary. External article text and snippets remain untrusted data; the later News Synthesizer receives bounded records through the graph and must retain attribution.

### Fake adapters

`FakeMarketDataProvider` and `FakeNewsProvider` should implement the exact same ports using versioned, synthetic fixtures. They must cover success, empty, delayed, stale, cache hit/miss, invalid input, 401/403, 429/quota, timeout, malformed response, conflict, and provider-unavailable cases. No fake result may be labeled live. Recorded live payloads may be committed only when the provider agreement permits fixture storage and redistribution; otherwise use hand-authored shape-equivalent synthetic fixtures.

## Candidate findings

### Tavily

Tavily Search is a general web search API. Its current endpoint accepts `topic` values including `news` and `finance`, date windows, domain restrictions, and up to 20 results. Results are relevance-ranked and include source URLs and bounded content snippets; the response also includes request ID, response time, and optional credit usage. ([Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search))

For news searches, Tavily can include `published_date`, but its documentation calls this Tavily's best estimate of publication or last-update time, allows `null`, warns that it can be later than the original publication date, and labels the feature beta. It is therefore not sufficient as an unquestioned publisher timestamp. The adapter should preserve the estimate as such or verify it against the article before populating a publisher-reported field. ([Search date fields](https://docs.tavily.com/documentation/api-reference/endpoint/search#include-published-date))

The free plan currently provides 1,000 credits per month. Basic search costs one credit and advanced search two; paid and enterprise tiers increase volume. Development and production keys have separate published rate limits. These are budgeting inputs, not availability guarantees. ([Credits and pricing](https://docs.tavily.com/documentation/api-credits), [rate limits](https://help.tavily.com/articles/3240802908-rate-limits))

The platform terms permit integration with customer applications subject to the subscription/order form, but impose usage limits and make the customer responsible for third-party terms and output verification. They also restrict high-risk financial automated decisions and prohibit specified sensitive information in input, including financial-account credentials, tax-return data, credit reports, payment-card data, and data subject to GLBA/FCRA restrictions. The current terms grant broad processing rights over customer input and describe possible processing by third parties. M3 must therefore send only public search terms—never portfolio rows, transaction data, credentials, or user-specific financial context—and obtain an explicit product/privacy review before enabling a live adapter. ([Tavily platform terms](https://www.tavily.com/terms), [acceptable-use policy](https://www.tavily.com/acceptable-use-policy))

Tavily does not grant rights to republish every third-party article it finds. M3 must record whether titles/snippets may be displayed or cached, retain links and publisher attribution, avoid raw-content storage by default, and honor the source publisher's terms. Recommended first experiment: `include_answer=false`, `include_raw_content=false`, `include_published_date=true`, an explicit date window, bounded `max_results`, and either an approved-domain restrict list or a reviewed open-web result policy.

**Disposition:** conditional NewsProvider experiment; not approved production provider yet. It should not be used for authoritative prices.

### Alpha Vantage

Alpha Vantage documents current quote, intraday, daily, weekly, monthly, adjusted-series, symbol-search, and related market endpoints. `TIME_SERIES_DAILY` returns raw daily OHLCV and a compact free response of the latest 100 points; full daily history and adjusted daily data have premium restrictions. `GLOBAL_QUOTE` defaults to end-of-day updates, while realtime and 15-minute-delayed U.S. data require paid entitlement. ([API documentation](https://www.alphavantage.co/documentation/))

The support page currently describes a free limit of 25 requests per day for most datasets and says verified open-source or educational projects may receive unlimited requests; higher volume requires premium service. The premium page advertises no daily limit, but endpoint access and requests-per-minute still depend on the selected plan or agreement. M3 must configure limits from the actual account entitlement rather than encode website marketing copy as a permanent constant. ([Support and limits](https://www.alphavantage.co/support/), [premium plans](https://www.alphavantage.co/premium/))

The terms grant personal, non-commercial use unless Alpha Vantage agrees otherwise in writing. They classify organizational use or exposing accessed information to other people/entities through commercial activity as commercial use and direct commercial users to contact Alpha Vantage. The API documentation likewise tells commercial users to contact sales for realtime/delayed market data. A paid self-service key by itself is not evidence that this product has all necessary commercial display, cache, and redistribution rights. ([Terms of service](https://www.alphavantage.co/terms_of_service/), [API entitlement notes](https://www.alphavantage.co/documentation/))

Alpha Vantage also offers a `NEWS_SENTIMENT` endpoint with ticker/time filters and article results; current documentation labels the illustrated function premium. This can be compared with Tavily, but sentiment/topic scores must remain provider claims, not product truth. ([News and sentiment endpoint](https://www.alphavantage.co/documentation/#news-sentiment))

**Disposition:** preferred technical MarketDataProvider experiment for end-of-day and historical behavior, conditional on written rights and measured quota/latency. Realtime/delayed behavior is unavailable unless the configured entitlement expressly permits it. Optional NewsProvider comparator, also conditional.

### yfinance and Yahoo Finance

yfinance is an Apache-2.0 Python library that can retrieve quotes/history, actions, ticker information, news/search results, and streaming data from publicly reachable Yahoo Finance interfaces. Its documentation explicitly says it is not affiliated with, endorsed by, or vetted by Yahoo, is intended for research and educational purposes, and that the Yahoo Finance API is intended for personal use only. ([yfinance documentation](https://ranaroussi.github.io/yfinance/), [package metadata](https://pypi.org/project/yfinance/))

The software license covers yfinance code, not the rights to Yahoo data. The library does not supply an application entitlement, contractual quota, stable response contract, or SLA; upstream behavior can change independently. Yahoo's developer terms/guidelines add separate restrictions for APIs and non-commercial services. ([Yahoo API terms](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html), [Yahoo developer guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html))

**Disposition:** exclude from M3 production selection and committed provider fixtures unless a separate written Yahoo entitlement is obtained. It may be used only for a clearly labeled, personal local research spike that is not part of CI, release evidence, or user-facing fallback.

## Required selection experiment and decision record

M3 should not accept a provider until it records all of the following for the exact plan/account:

1. permission for the intended controlled private demonstration and any potential future commercial/public application use, recorded separately rather than assuming the former grants the latter;
2. allowed display, derived calculations, attribution, caching duration, persistent storage, test fixtures, and redistribution;
3. endpoint inventory, asset coverage, adjustment definitions, timestamps, delay state, and timezone behavior;
4. request/day and request/minute limits, concurrency, overage behavior, expected 429/error shapes, and cost ceiling;
5. success, invalid-symbol/query, 401/403, 429, timeout, malformed, stale-cache, and outage contract tests;
6. measured latency and data-quality comparison against hand-checked cases;
7. secret handling, query minimization, redaction, and exporter/log exclusions;
8. fallback behavior that never relabels fake, cached, delayed, or unavailable data as live.

Until those checks pass, implement only the ports, fake adapters, provider configuration, and conditional experiment adapters. A fallback may switch providers only when both are independently approved and the result retains the actual provider, freshness, and cache provenance.

## Private-demo quota policy

- The demo script declares its live calls by provider and endpoint before execution and reserves headroom below the configured daily/monthly and per-minute limits.
- Startup or an explicit preflight selects `live` or `credential-free` mode. Missing credentials, insufficient configured budget, or failed readiness selects the credential-free journey before the Run begins rather than silently switching its data source mid-Run.
- Repeated UI reads reuse a permitted bounded cache instead of making new provider calls. Cache timestamps and stale state remain visible.
- The live demo uses a small fixed symbol/query set and records actual call counts, 429 responses, cache hits, and unavailable results. It never circumvents limits with multiple keys.
- Credential-free results remain synthetic and labeled in the API, UI, RunEvents, traces, screenshots, and demonstration narration.
