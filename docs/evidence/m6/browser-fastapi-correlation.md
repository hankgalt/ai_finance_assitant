# Browser-to-FastAPI correlation record

For every product request, the browser client creates:

1. `traceparent: 00-<32 hex trace id>-<16 hex span id>-01`;
2. `X-Request-ID: web-<24 hex characters>`;
3. a bounded timing event carrying the same trace and request identities.

The first-party telemetry request uses the same trace identity in its own `traceparent` header and
the same `X-Request-ID`. FastAPI's M5 correlation middleware and OpenTelemetry instrumentation
therefore receive the browser context on both the product request and its timing signal. Trace and
request identities are intentionally excluded from metric attributes to prevent high-cardinality
labels; operational traces/log correlation carries them instead.

`frontend/src/lib/api.test.ts` verifies valid W3C/header shapes and matching trace identities.
`backend/tests/test_m6_browser_contract.py` verifies the collector records only bounded attributes
and does not record the request identifier or rejected content. Existing M5 observability tests
verify inbound trace propagation and log/span correlation.
