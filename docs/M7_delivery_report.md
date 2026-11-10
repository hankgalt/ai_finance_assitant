# M7 delivery report — Agent Execution Inspector

Date: 2026-10-30  
Status: Complete for the production-oriented private local demonstration  
Scope: PR-010, PR-011, PR-012; QR-001, QR-003, QR-004, QR-005, QR-007,
QR-010, QR-013, QR-014, QR-015; EV-12; ADR-011, ADR-012, ADR-013,
ADR-014, ADR-019

Maintenance update: 2026-10-31 — graph nodes now show the exact persisted sequence positions of
their aggregated events. Consecutive node-local positions are compressed into ranges, while gaps
remain explicit so parallel/interleaved execution is not misrepresented. Sequence remains display
evidence only and never creates an edge or measured-duration claim.

## Outcome

M7 replaces the Inspector placeholder with an authorized Session-scoped Run selector, persisted
RunEvent timeline, measured React Flow graph, event details, safe retrieval/tool metadata,
measurement availability, and support-correlation identifiers. The graph never derives work from a
Run's final response. Its model deduplicates stable event identifiers, orders by recorded sequence,
isolates one execution, and creates an edge only from `parent_event_id` or
`routing.selected_node_ids` evidence whose source and target nodes were both recorded.

Each graph node aggregates all events with its recorded `node_id` and displays their exact timeline
positions. For example, Router can show `#2–#4`, while a Workflow node whose start and terminal
events surround other work shows `#1, #31`. A range is used only when every included sequence is
consecutive for that node; it is not an inferred execution edge or elapsed-time interval.

The accessible ordered timeline is a complete alternative to the graph. Selecting an event exposes
its safe summary, status, timestamps, measured duration or unavailable reason, routing outcome,
tool result, retrieval source identifiers, usage/cost or unavailable reason, allow-listed metadata,
and safe error. Submitted prompts, final-response bodies, hidden reasoning, credentials, raw
financial records, and arbitrary payloads are not rendered. A Run can resume the SSE stream from
the latest stable event identifier and then reload persisted REST history as the source of truth.

M7 was intentionally completed before M6.1. Response-cache activity is absent until M6.1 emits it
through the existing generic tool-event contract; the Inspector has no cache-specific inference or
external trace-backend dependency.

## Delivered interfaces

- `frontend/src/features/inspector/inspectorModel.ts`: event normalization and recorded-evidence
  graph projection behind one typed interface.
- `frontend/src/features/inspector/InspectorExperience.tsx`: Run selection, correlation, React Flow,
  ordered timeline, details, unavailable states, synthetic-fixture labeling, and reconnect controls.
- `frontend/src/lib/api.ts`: authorized RunEvent history client and Inspector-labeled SSE recovery.
- `contracts/inspector/execution-inspector.v1.json`: required REST/SSE paths, frontend types, identity
  fields, graph evidence, and forbidden Inspector sources.
- `backend/tests/test_inspector_contract.py`: OpenAPI/frontend/model seam reconciliation.
- `frontend/e2e/execution-inspector.spec.ts`: deterministic success, partial, and failed browser paths plus Axe and
  prompt non-rendering assertions.
- `make m7-check`: repeatable focused milestone gate.

## Acceptance and evidence

| Gate | Result |
| --- | --- |
| Every dynamic node resolves to recorded RunEvents | Passed by projection and browser tests |
| Node sequence labels reconcile with the timeline | Passed for consecutive ranges, gaps, duplicate positions, and out-of-order input |
| Every edge has recorded route or parent evidence | Passed; no sequence-derived edge exists |
| Duplicate/out-of-order and missing-sequence behavior | Passed by unit fixtures and visible recovery state |
| REST authority with Last-Event-ID reconnect | Passed by component, API, and M5 replay tests |
| Success, partial, and failed paths remain truthful | Passed; three browser screenshots recorded |
| Duration, tokens, cost, and trace missing states | Passed; unavailable reasons render instead of zero |
| Synthetic evidence is labeled | Passed from recorded fixture/provider metadata |
| Prompt, hidden reasoning, credentials, unsafe payloads | Passed by UI assertion and bounded contract review |
| Keyboard/screen-reader alternative | Ordered interactive list delivered; zero serious/critical Axe findings |
| Session/run isolation | Existing M5 scoped repositories and API tests passed |

The evidence index is [docs/evidence/m7/README.md](evidence/m7/README.md).

## Verification record

- Backend full gate: Ruff format/check passed; mypy passed for 111 source files; 192 tests passed,
  one opt-in Qdrant test skipped, three live tests deselected; total coverage 88%.
- Focused backend M5/M7 gate: 20 tests passed for the manifest, authorized event history/SSE, and
  persistence behavior.
- Frontend gate: Prettier, ESLint, TypeScript, all 30 Vitest tests, and the production build passed.
- Chrome M7 journey: one test passed with success/partial/failure states, reconnect-capable UI,
  prompt non-rendering, screenshots, and zero serious/critical Axe findings.
- No live provider, OpenAI, LangSmith, Qdrant, Redis, or external telemetry service was called.

Sequence-label maintenance verification on 2026-10-31:

- Frontend Prettier, ESLint, TypeScript, all 32 Vitest tests, and the production build passed.
- The focused backend M5/M7 contract, API, persistence, observability, contract, and redaction gate
  passed 31 tests after updating the Inspector contract manifest.
- `UV_CACHE_DIR=/tmp/aifa-uv-cache make m7-check` passed the complete gate after approval to bind
  the loopback Vite server: all frontend and backend checks above plus one Chrome journey in 3.0
  seconds. An earlier sandbox-only attempt reached Playwright after passing every preceding check
  but could not bind `127.0.0.1:5173`; it was an environment restriction, not a test failure.
- The Chrome journey regenerated all three sequence-labeled evidence screenshots.
- No external account or network provider was used.

## Security and privacy impact

- The Inspector consumes only Session-scoped persisted RunEvents after the backend authorizes the
  Run. It does not query LangSmith or another external trace backend.
- Run request messages are deliberately excluded even though the Run selector receives the record.
  Selector text contains only opaque Run identity, terminal status, and creation time.
- Event detail is limited to the versioned safe contract. Structured metadata values are not
  expanded in the compact UI, and backend redaction remains authoritative before persistence.
- Synthetic/fake/deterministic evidence is visibly distinguished from a live provider execution.

## Limitations and unresolved decisions

- The private demo is still unauthenticated and loopback-only; opaque Session identifiers provide
  scoping, not public multi-user authorization.
- Browser evidence uses deterministic fixtures. Actual persistence, isolation, replay, event
  contracts, and instrumentation are independently covered by backend tests; full-stack live-model
  Inspector qualification remains part of M8.
- React Flow positions are deterministic presentation positions, not measured workflow timing.
  Only nodes, edges, statuses, and metadata claim execution evidence.
- M6.1 response-cache events do not exist yet and are truthfully described as unavailable. M6.1 may
  add generic tool events but may not introduce cache-specific graph inference.
- External trace links, broad performance qualification, adversarial accessibility, and public
  authentication/authorization remain M8 or production-hardening work.

M7 satisfies its acceptance gate. M6.1 is the next permitted milestone; M8 remains blocked until
M6.1 and its cache qualification artifacts are complete.
