# M5 evidence artifacts

- `test-results.json` records the exact focused, backend, frontend, and Collector-config gates.
- `migration-record.v1.json` records application schema version 1 and the durable table set.
- `sse-replay-transcript.v1.json` records an actual credential-free Run, frame order, and replay
  cursor result without copying the full event payloads.
- `lifecycle-isolation.v1.json` maps restart, expiry, deletion, idempotency, and Session-isolation
  assertions to their tests.
- `provider-cache-transcript.v1.json` records provider-call counts and durable range behavior.
- `trace-correlation-sample.v1.json` records the deterministic W3C correlation assertion.
- `metric-inventory.v1.json` lists implemented bounded measurements and attributes.
- `security-lifecycle.v1.json` records local retention, rights gating, and deployment limits.

The authoritative interface manifest is `contracts/m5-api-contract.v1.json`. The Collector
configuration is `ops/otel-collector.yaml`; M5 status and limitations are in
`docs/M5_delivery_report.md`.
