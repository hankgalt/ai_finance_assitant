# M5 delivery report — FastAPI integration and durable local persistence

Date: 2026-10-28  
Status: Complete for the production-oriented private local demonstration  
Scope: PR-004, PR-006, PR-010–PR-013; QR-001–QR-007, QR-010, QR-011,
QR-014, QR-015; ADR-003, ADR-007, ADR-011, ADR-014, ADR-019, ADR-026

## Outcome

M5 delivers authoritative versioned FastAPI resources for Sessions, Runs, saved Portfolios,
Portfolio Snapshots, market queries, goal projections, and authorized trace history. Run creation
executes the existing six-agent graph; stable REST resources carry terminal state while replayable
SSE carries persisted RunEvents plus a terminal response chunk. `Last-Event-ID` resumes after a
known event without replaying it, and REST history remains the recovery source.

Application schema version 1 stores local resources and normalized historical daily bars in
SQLite. The official LangGraph SQLite saver persists checkpoints through a dedicated connection to
the same file using strict deserialization. Startup applies transactional migrations, rejects a
newer schema, purges expired records/cache rows, and removes checkpoint threads for expired
Sessions. Session deletion cascades owned data and explicitly removes its checkpoint thread.

The ADR-026 cache uses a bounded exact-request memory tier over a relational range cache. It
isolates provider, instrument, interval, currency, adjustment basis, schema, and policy; reuses
fresh coverage after restart; fetches only gaps and an approved recent-tail refresh window;
coalesces concurrent same-key calls; recovers from malformed rows; preserves stale data only with
truthful warnings; and supports token-protected administrative purge. Unverified live-data
retention is allowed only through explicit owner-only risk acceptance and fails shared/public
readiness.

FastAPI, HTTPX, workflow modules, providers, retrieval, cache, and persistence emit
privacy-filtered OpenTelemetry signals. W3C context correlates inbound requests, module spans,
RunEvents, and outbound calls. JSON logs add bounded correlation fields. An optional loopback OTLP
Collector configuration exports traces and metrics to a debug sink; exporter failure cannot change
product behavior. LangSmith remains an optional agent/LLM backend and is not the source of Run
history or operational metrics.

## Interfaces and configuration

- `api/routes/v1.py`: versioned resources, stable safe errors, idempotency, authorized history,
  replayable SSE, and administrative cache purge.
- `persistence/`: schema/migrations, repositories, deletion/retention behavior, and official
  `SqliteSaver` construction.
- `providers/durable_cache.py`: two-tier historical range cache and provenance transitions.
- `observability/factory.py` and API middleware: OTLP-capable runtime, FastAPI/HTTPX
  instrumentation, bounded metrics, and structured correlation logs.
- `contracts/m5-api-contract.v1.json` and `frontend/src/types/contracts.ts`: exact `/api/v1`
  manifest plus contract-verified frontend resource/cache types.
- `.env.example`, `compose.yaml`, `ops/otel-collector.yaml`, and `Makefile`: documented local
  storage/cache/telemetry settings and M5/Collector commands.

Default settings are: loopback binding; 30-day Session and RunEvent retention; 365-day Portfolio
retention; 3,650-day maximum eligible historical-bar retention; seven-day recent-tail refresh after
six hours; 128 memory entries for five minutes; OTLP export disabled; local admin purge disabled
until a token is configured. Credential-free mode is deterministic and requires no external call.

## Acceptance and evidence

| Gate | Result |
| --- | --- |
| API contract, idempotency, errors, CORS, limits, and concurrent Sessions/Runs | Passed |
| Session/history/stream isolation, restart, deletion, expiry, and checkpoint cleanup | Passed |
| SSE framing, stable IDs, replay cursor, and REST recovery | Passed |
| Migration compatibility and newer-schema rejection | Passed |
| Exact/overlap/restart cache reuse and gap-only provider calls | Passed |
| Memory/durable/provider/partial/stale/unavailable provenance | Passed |
| Cache concurrency, key isolation, malformed rows, expiry, and purge | Passed |
| Owner-only versus shared/public unverified-rights readiness | Passed |
| Inbound/outbound W3C propagation, route cardinality, health exclusion, and metric inventory | Passed |
| Throwing telemetry/exporter adapter leaves product result unchanged | Passed in the existing M4 regression included by the full backend gate |

Evidence is under `backend/artifacts/m5/`. The authoritative interface manifest is
`contracts/m5-api-contract.v1.json`; Collector configuration is `ops/otel-collector.yaml`.

## Verification record

- `make m5-check` — passed: 107 backend source/test files formatted, Ruff clean, 107 source files
  type-checked, and 31 focused tests passed in 0.73 seconds.
- `make backend-check` — passed: 114 files formatted, Ruff clean, 107 source files type-checked,
  157 tests passed, 1 Qdrant integration test skipped, 3 opt-in live tests deselected, and 87%
  total coverage.
- `make frontend-check` — passed: Prettier, ESLint, TypeScript, 3 Vitest tests, and the Vite
  production build.
- `docker compose --profile observability config --quiet` — passed.

No live provider, OpenAI, LangSmith, Qdrant, or telemetry-backend call was required or made by
these final M5 gates. The Qdrant skip is intentional when no opt-in integration URL is supplied;
M1 records its separate integration evidence. Live provider/model tests remain explicit markers.

## Security, privacy, and lifecycle impact

- The demo remains unauthenticated and is allowed only on loopback. Session scope prevents
  accidental cross-session access but is not identity or authorization for a public service.
- Request bodies, prompts, portfolio rows, provider payloads, credentials, hidden reasoning, and
  unrestricted results are absent from logs, metric attributes, and operational spans. Persisted
  RunEvents use the existing redaction/allow-list path.
- SQLite is a local private-demo store. It is not encrypted by this application and has no backup,
  disaster recovery, distributed locking, or multi-instance coordination.
- Provider cache rows contain normalized derived bars and coverage plus provenance, entitlement,
  retention label, and expiry. They exclude raw payloads, credentials, news bodies, and user
  portfolio context.
- Owner-only unverified-rights acceptance does not establish contractual permission. It cannot
  satisfy shared-demo or public readiness.

## Limitations and unresolved decisions

- Strong identity, per-user authorization, a managed public store, encryption/key management,
  backup/recovery, availability objectives, and public threat review remain ADR-019 work.
- SQLite and in-process request coalescing are bounded local-demo choices, not distributed
  concurrency controls. The synchronous FastAPI Run endpoint does not provide cancellation after
  client disconnect; later reliability evaluation must revisit cancellation and scale.
- The supplied Collector uses a local debug exporter. A protected operational backend, sampling,
  retention, dashboards, and alerts remain deployment decisions.
- Current quotes and news keep their existing short in-memory lifecycles. Only normalized daily
  history has approved M5 durable behavior.
- Live cache/display/redistribution rights are still account- and provider-specific. Public or
  shared operation remains blocked until an approved rights decision changes readiness state.
- Frontend product experiences and browser telemetry remain M6; the Inspector remains M7.

M5 has satisfied its acceptance gate. M6 is the next permitted milestone.
