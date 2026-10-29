# M4 delivery report — LangGraph orchestration and all six agents

Status: Complete for the internal credential-free workflow interface; API and durable persistence remain M5 work

Completed: 2026-10-28

Scope: PR-001, PR-002, PR-004, PR-006, PR-007, PR-008; QR-004, QR-005, QR-007, QR-010, QR-012, QR-014, QR-015; EV-01, EV-02, EV-05–EV-11; ADR-001, ADR-002, ADR-005, ADR-008, ADR-009, ADR-011, ADR-012, ADR-018

## Outcome

M4 delivers a typed, bounded LangGraph workflow with exactly six specialist nodes: Finance Q&A, Portfolio Analysis, Market Analysis, Goal Planning, News Synthesizer, and Tax Education. The router may select several independent nodes, agents never call one another, and every selected result remains separately typed through synthesis. Goal Planning consumes explicit deterministic projection assumptions and remains separate from Market Analysis.

Finance and Tax use the M1 retrieval seam and return Run-scoped evidence references. Portfolio and Goal delegate arithmetic to M2 modules. Market and News consume one M3 ProviderBundle created for each Run. The included model adapter is a deterministic credential-free structured-output adapter for tests and the private demo path; a production model selection remains an ADR-008 implementation decision.

Measured RunEvents cover Run, route, node, retrieval, provider tool, model, and terminal lifecycles. They remain the authoritative product execution record. A vendor-neutral observability interface supplies disabled, in-memory, and OpenTelemetry adapters. Trace identifiers correlate exported spans with RunEvents; telemetry fields are allow-listed before recording/export, and failed telemetry cannot fail product execution. Optional LangSmith tracing is disabled by default and hides all inputs and outputs when enabled.

## Delivered interfaces

- `workflow.models.WorkflowRequest` and `WorkflowRunResult`: versioned Run input and terminal result.
- `workflow.graph.FinanceState` and `FinanceWorkflow`: router, conditional fan-out, synthesis, deadline/hop limits, checkpoints, and actual Mermaid graph output.
- `workflow.application.WorkflowApplication`: hides six-agent assembly and creates one selected provider bundle for each Run.
- `agents.specialists`: the six documented specialist responsibilities and explicit clarification/error states.
- `agents.runtime.AgentRuntime`: shared measured retrieval, structured-model, and allow-listed provider-tool execution.
- `llm.ports.ModelAdapter`: structured external-model seam plus deterministic credential-free adapter.
- `workflow.events.RunEventRecorder`: pre-persistence redaction, safe metadata filtering, monotonic sequence, parent links, and Session-scoped retrieval.
- `observability`: no-op, in-memory, OpenTelemetry, safe failure wrapper, configuration factory, and optional privacy-hidden LangSmith context.
- `data/workflow/routing_cases.v1.json`: 40 reviewable routing cases covering all six domains, multi-domain requests, clarification, and checkpoint follow-ups.

No FastAPI workflow route, SSE stream, browser integration, durable user store, durable checkpoint store, or durable RunEvent store was added. Those are explicitly M5/M6 boundaries.

## Acceptance evidence

| Acceptance statement | Result and evidence |
| --- | --- |
| All six agents have distinct behavior | Direct contract tests exercise Finance/Tax evidence, deterministic Portfolio/Goal outputs, provider-backed Market/News outputs, attribution, assumptions, and prohibited prediction/guarantee behavior. |
| Labeled requests route correctly | All 40 versioned cases exactly match their expected agent sets. See `backend/artifacts/m4/routing-confusion-matrix.v1.json`. |
| Multi-agent boundaries and partial failure are preserved | Graph tests prove Finance/Tax fan-out, independent exception conversion, ordered typed results, and a partial terminal state without discarding the successful result. |
| Bounds and restart behavior are explicit | Tests exercise expired deadlines, LangGraph recursion limits, reconstruction with a shared checkpointer, checkpoint follow-up routing, and cross-Session isolation. |
| Evidence and hostile content stay bounded | Finance and Tax citations resolve to retrieved Evidence; Tax retrieval filters the requested year; hostile retrieved instructions do not appear in output or events; malformed model output is rejected. |
| RunEvents describe measured execution | Tests and the captured sample verify monotonic event order, route/node/retrieval/model/terminal events, parent identifiers, measured usage method, and terminal state. Provider tool lifecycle is exercised by Market, News, and Portfolio tests. |
| Observability is correlated and non-blocking | The OpenTelemetry test exports a complete in-memory trace and verifies the same trace identifier on every RunEvent. A throwing adapter leaves the product result complete and marks trace data unavailable. |
| External telemetry is privacy-filtered | Tests remove prompt/message/token attributes, redact authorization values, allow-list persisted metadata, and verify LangSmith `hide_inputs=True` and `hide_outputs=True`. |

## Verification record

Final qualification commands:

~~~bash
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m4-check
cd backend && UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run pytest -q --cov=ai_finance_assistant --cov-report=term-missing
UV_NO_SYNC=1 UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify
~~~

Observed results:

- Focused M4 formatting, Ruff, strict mypy, and 16 behavior tests: pass.
- Full backend suite: 103 passed, 1 skipped, and 2 opt-in live-provider tests deselected; measured repository coverage rounds to 87%.
- Frontend formatting, lint, typecheck, 3 tests, and production build: pass.
- The skip is the existing opt-in live-Qdrant integration test because no live test URL was supplied; M1 records its separate integration evidence.
- No live provider or LangSmith request was made. Credential-free fake providers and the in-memory OpenTelemetry exporter supplied deterministic evidence.

Machine-readable evidence and the actual compiled graph are under `backend/artifacts/m4/`.

## Security, privacy, and observability impact

- User messages, retrieved excerpts, holdings, transactions, model inputs/outputs, credentials, unrestricted provider payloads, and hidden reasoning are excluded from RunEvent safe metadata and exported span attributes.
- Retrieved documents, news, provider payloads, and user content remain data. Model instructions explicitly define the boundary, structured output is schema-validated, and external operations are fixed allow-listed methods supplied by code.
- Context lookup is scoped by Session plus opaque context reference. Checkpoints use `Session:Workflow` thread identifiers and tests prove that a new Session cannot inherit prior routing state.
- OpenTelemetry is enabled by default for local backend modules without a network exporter. `AIFA_OBSERVABILITY_MODE` can select disabled, in-memory, or OpenTelemetry behavior. M5 owns FastAPI/outbound-client instrumentation and Collector export; M6 owns frontend Web Vitals, error, navigation, and API telemetry. LangSmith is backend-only and never belongs in the browser.
- RunEvents remain authoritative even when OpenTelemetry or LangSmith is disabled or unavailable. M5 must persist and authorize them before the Inspector can consume actual history.

## Limitations and unresolved decisions

- The included checkpointer and RunEvent repository are in-memory. They demonstrate restart through application reconstruction in one process, not process-restart durability. Store selection, migrations, retention, deletion, and access-controlled history are M5 decisions.
- OpenTelemetry spans are generated and correlated, but no OTLP Collector/exporter or operational backend is configured in M4. That runtime integration belongs to M5. The captured evidence uses the SDK's in-memory exporter.
- LangSmith is optional and was not connected during qualification. The configuration/test evidence proves the privacy defaults, not a successful external LangSmith account trace.
- The deterministic model adapter is intentionally not represented as a production LLM. ADR-008 still requires the selected production model/provider policy, retry budget, and cost/usage behavior before live model activation.
- The 40-case lexical router passes its versioned development set but is not a statistical production-traffic claim. M8 must expand, independently review, and calibrate routing, groundedness, injection, and financial-safety evaluation.
- Focused M4 tests use static permitted Evidence and credential-free providers. M1 separately owns active-Qdrant integration evidence, while M3 separately owns conditional live-provider qualification and rights gates.
- Repository coverage is 87%, above the preserved coursework fallback target but below its aspirational 90% tier. M8/M9 must report final scope-adjusted coverage honestly; this milestone does not claim the top tier.

The implementation plan now assigns production-model selection, adapter implementation, and live-model qualification to M4.1. M4.1 is a required dependency of M5 rather than an activity deferred to M8 evaluation.

These limitations do not invalidate the completed deterministic M4 graph and specialist contracts. They do block M5 and claims that durable history, external telemetry export, live LangSmith, a production LLM, or public multi-user operation are complete until the newly explicit M4.1 gate passes.
