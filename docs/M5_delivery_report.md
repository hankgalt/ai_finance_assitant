# M5 delivery report — FastAPI integration and durable local persistence

Date: 2026-10-29
Status: Complete for the production-oriented private local demonstration  
Scope: PR-004, PR-006, PR-010–PR-013; QR-001–QR-007, QR-010, QR-011,
QR-014, QR-015; ADR-003, ADR-007, ADR-011, ADR-014, ADR-019, ADR-026, ADR-027

## Outcome

M5 delivers authoritative versioned FastAPI resources for Sessions, Runs, saved Portfolios,
Portfolio Snapshots, market queries, goal projections, and authorized trace history. Run creation
executes the existing six-agent graph; stable REST resources carry terminal state while replayable
SSE carries persisted RunEvents plus a terminal response chunk. `Last-Event-ID` resumes after a
known event without replaying it, and REST history remains the recovery source.

Application schema version 3 stores local resources and normalized historical daily bars in
SQLite. The official LangGraph SQLite saver persists checkpoints through a dedicated connection to
the same file using strict deserialization. Startup applies transactional migrations, rejects a
newer schema, purges expired records/cache rows, and removes checkpoint threads for expired
Sessions. Schema version 1 upgrades in place by adding Archived Session state, and version 3 adds a
nullable submitted request message to Run records so legacy history remains readable. Clearing an Active
Session archives it as read-only history while preserving owned data and its checkpoint; permanent
deletion is rejected until archive, then cascades owned data and explicitly removes the checkpoint
thread. Archived Sessions remain subject to the configured retention expiry.

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
- `persistence/`: schema/migrations, repositories, archive/history/deletion/retention behavior, and official
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
| Session/history/stream isolation, restart, archive/read-only history, deletion, expiry, and checkpoint cleanup | Passed |
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

- `make m5-check` — passed: 109 backend source/test files formatted, Ruff clean, 109 source files
  type-checked, and 32 focused tests passed in 1.35 seconds.
- `make backend-check` — passed: 117 files formatted, Ruff clean, 109 source files type-checked,
  169 tests passed, 1 Qdrant integration test skipped, 3 opt-in live tests deselected, and 87%
  total coverage.
- `make frontend-check` — passed: Prettier, ESLint, TypeScript, 13 Vitest tests, and the Vite
  production build.
- `docker compose --profile observability config --quiet` — passed.

No live provider, OpenAI, LangSmith, Qdrant, or telemetry-backend call was required or made by
these final M5 gates. The Qdrant skip is intentional when no opt-in integration URL is supplied;
M1 records its separate integration evidence. Live provider/model tests remain explicit markers.

Post-completion response-contract maintenance added a distinct 4,000-character user narrative
bound to the M5 interface manifest and FastAPI schemas. A 1,399-character deterministic narrative
regression proves exact preservation through the Agent result, Workflow result, SQLite Run record,
REST recovery, and SSE response chunk; RunEvents remain short and response-free. The current full
offline gate passes 175 backend tests with 87% coverage and 15 frontend tests. The separately
approved one-call OpenAI semantic replay is recorded with M4.1 evidence, not as an M5 gate.

Portfolio lifecycle maintenance qualifies the existing Session-scoped Portfolio delete resource.
Deletion cascades saved Snapshots and authorized agent context, now also removes the corresponding
idempotency record so the same user-controlled Portfolio can be imported again without a stale
reference. The focused API regression verifies cross-Session denial, cascade deletion, an empty
authorized list, and same-key re-import. Eleven focused M5 API tests, Ruff formatting/lint, and mypy
over 110 source files pass.

Run-context maintenance keeps the existing `context_references` API as the authorization seam for
Assistant portfolio questions. The Portfolio specialist now consumes every distinct authorized
Portfolio reference in request order, calculates a separate Snapshot for each, and returns a
clarification when none resolves in the Run's Session. It no longer silently selects the first of
several references. The model receives bounded deterministic facts for explanation and cannot
combine Portfolio or currency totals. Focused agent regressions cover no-context, one-context, and
explicit multi-context behavior without a live provider or model call.

Conditional Portfolio continuation maintenance adds the versioned
`POST /sessions/{session_id}/runs/{execution_id}/continue` resource. It accepts only bounded opaque
context identifiers for a source Run that is waiting on typed Portfolio input, re-authorizes every
identifier in the same Active Session, and creates a separately persisted Run linked to its source.
The continuation preserves the original selected-agent set and enters the graph at the context gate,
so the classifier is not invoked twice. Repeated continuation attempts return the already linked Run;
cross-Session, missing, non-Portfolio, and non-waiting contexts fail closed with safe errors.

## Security, privacy, and lifecycle impact

- The demo remains unauthenticated and is allowed only on loopback. Session scope prevents
  accidental cross-session access but is not identity or authorization for a public service.
- Request bodies, prompts, portfolio rows, provider payloads, credentials, hidden reasoning, and
  unrestricted results are absent from logs, metric attributes, and operational spans. Persisted
  RunEvents use the existing redaction/allow-list path.
- New Run records persist the submitted request message for authorized conversation history. It
  follows Session retention/archive/deletion, remains absent from logs/metrics/operational traces,
  and is unavailable rather than inferred for pre-migration Runs.
- SQLite is a local private-demo store. It is not encrypted by this application and has no backup,
  disaster recovery, distributed locking, or multi-instance coordination.
- Archive is not indefinite preservation: Archived Sessions follow the same configured 30-day
  Session retention and can be removed by expiry or explicit permanent deletion.
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

M5 remains within its acceptance gate. M6 has since completed; M7 is the next permitted milestone.
