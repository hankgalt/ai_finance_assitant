# M4.1 delivery report — production LLM adapter and live-model qualification

Date: 2026-10-28  
Status: Complete  
Scope: PR-001, PR-002, PR-004, PR-006, PR-007, PR-008; QR-004, QR-005, QR-007,
QR-010, QR-012, QR-014, QR-015; EV-01, EV-02, EV-05–EV-11; ADR-001, ADR-002,
ADR-005, ADR-008, ADR-009, ADR-011, ADR-012, ADR-018, ADR-023

Maintenance update: 2026-10-29 — the shared OpenAI adapter now produces both specialist
`ModelOutput` and router `RoutingModelOutput`; ordinary tests are isolated in `backend/.test.env`.
The specialist prompt is now `openai-agent-system-v2`: user-facing summaries have a distinct
4,000-character contract, while warnings exclude internal provider and generation mechanics.

## Outcome

M4.1 implements the shared conditional OpenAI adapter selected in the
[model-selection record](research/M4_1_openai_model_selection.md). OpenAI `gpt-6.1-sol` uses the
Responses API with Pydantic `ModelOutput` and `RoutingModelOutput` v1 parsing, `store=False`, no
tools, fixed per-operation reasoning effort, deadline-aware timeouts, bounded backoff, and a
thread-safe per-Run attempt budget. Credential-free mode remains the default and ordinary CI
loads `backend/.test.env`, performs no external model call, and does not read `backend/.env`.

`WorkflowApplication` constructs one model adapter per Run and supplies it to the router and all
selected specialists, just as it constructs one provider bundle per Run. A failed live readiness
gate returns a typed model error and never substitutes the deterministic adapter. Specialist
model output contains only summary and warning fields. All authoritative
facts—especially Portfolio and Goal arithmetic plus Market and News provenance—remain the exact
code-owned facts passed to the model for explanation.

The implementation and deterministic regression gates pass. Eighteen approved external requests
returned HTTP 200 and structured output across three six-call approvals. The second aggregate run
proved all six live agent contracts, deterministic facts, model identity, and measured usage, then
its final privacy assertion exposed a terminal RunEvent copying the synthesized user-facing model
summary. The terminal event now records only workflow status, and a workflow-level regression test
proves that the response remains in `WorkflowRunResult` while every RunEvent excludes it. The third
approved aggregate run passed every live assertion, including the corrected privacy check. M4.1 is
complete and its dependency no longer blocks M5.

Post-completion maintenance corrected a response-contract defect that clipped successful model
output at 512 characters and could surface a model-authored generation warning. The narrative
contract now remains intact through the model adapter, Agent result, Workflow result, persistence,
REST, and SSE. A one-call live Finance QA replay produced a complete 1,547-character answer with
terminal punctuation and no internal-generation warning.

## Interfaces and files changed

- `ai_finance_assistant.llm.openai.OpenAIModelAdapter`: Responses structured-output adapter.
- `ai_finance_assistant.llm.factory.model_adapter_from_settings`: credential-free/live selection
  and fail-closed readiness behavior.
- `ModelRequest`/`ModelOutput`: deadline-aware request; explanation-only response schema.
- `RoutingModelRequest`/`RoutingModelOutput`: prior-agent context and a closed set of selected
  agents plus reason categories; no free-form reasoning.
- `ModelProviderError`: stable not-ready, authentication, rate-limit, timeout, unavailable,
  refusal, incomplete, malformed, deadline, size, and request-budget states.
- `AgentRuntime`: safe error mapping plus provider/model/prompt identity and measured usage events.
- `WorkflowApplication`: one selected model adapter per Run.
- Settings and `.env.example`: OpenAI controls and current/legacy LangSmith aliases.
- `live_model` marker, `make m4-1-check`, and `make model-live-check`.
- `docs/research/M4_1_openai_model_selection.md` and `backend/artifacts/m4_1/` evidence.

No FastAPI workflow route, SSE interface, durable checkpoint/event adapter, frontend feature, or
later-milestone behavior was added.

## Behavior and failure evidence

| Behavior | Evidence |
|---|---|
| Structured success and provider-reported token usage | `test_structured_success_uses_responses_parse_without_storage_or_fact_rewrite` |
| Complete narrative preservation and warning semantics | `test_structured_success_preserves_a_complete_educational_narrative`, `test_generation_prompt_keeps_internal_mechanics_out_of_user_warnings`, and the M5 API persistence/SSE regression |
| Structured LLM routing without a lexical table | `test_routing_uses_model_structured_output_without_lexical_classification` and the 44-case scripted contract suite, including explicit out-of-scope decisions |
| Fixed reasoning policy for all six agents | `test_reasoning_policy_is_fixed_by_agent` |
| Authentication, rate limit, timeout, and outage mapping | adapter parameterized failure tests |
| Refusal, incomplete, malformed, extra, or missing output | structured non-success tests; all fail closed |
| Retry and backoff | connection failure recovers only within attempt and deadline budgets |
| Per-Run request budget and concurrency | sequential and concurrent budget tests; attempts cannot exceed the cap |
| Deadline and input budget | provider is not called for expired or oversized requests |
| Fake/live separation | factory tests and one model adapter construction per Run |
| Deterministic authority | agents return original code-owned facts; response schema has no facts field |
| Privacy | hostile evidence remains data; prompts/evidence/responses/keys are absent from RunEvents and operational span attributes |
| Optional LangSmith isolation | inputs/outputs hidden; client failure does not change product behavior |

The live target defaults to one aggregate Run and fixes `model_maximum_attempts=1`. The current
external-call ceiling is seven: one structured routing decision plus one response for each of six
selected agents. This post-maintenance path has not been externally requalified; the historical
qualification below predates model-backed routing and used six calls per aggregate Run. The internal
`AIFA_LIVE_MODEL_ONLY_AGENT` diagnostic selector exists only to isolate a failed agent without
repeating the other five calls.

## Observability and privacy impact

~~~text
untrusted user/evidence/facts
           |
           v
bounded JSON envelope ----> OpenAI Responses (`store=false`) ----> ModelOutput v1
           |                                                    summary/warnings only
           |
           +--> RunEvents: provider/model/prompt version/status/usage only
           +--> OpenTelemetry: allow-listed correlation and model identity only
           +--> optional LangSmith: graph trace with inputs/outputs hidden
~~~

OpenAI credentials are loaded only from environment settings and are never written to an artifact.
Qualification used synthetic evidence, portfolio, goal, market, and news fixtures. OpenAI's
documented default abuse-monitoring retention can be up to 30 days; the owner accepted that posture
for this synthetic test. `store=False` prevents ordinary Responses application-state storage but
is not represented as Zero Data Retention.

LangSmith is optional. A later synthetic workflow verification confirmed privacy-hidden delivery
to the configured project and the explicit workflow root name; it made no OpenAI call and is not
live-model qualification. Current `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and
`LANGSMITH_PROJECT` variables are supported, along with the requested legacy
`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` names. RunEvents remain
authoritative regardless of LangSmith availability.

## Verification results

Offline gates:

- `make m4-1-check` — passed: formatting, lint, mypy, and 49 focused tests.
- `make backend-check` — passed: 117 files formatted, lint clean, mypy passed for 109 source/test
  files, 174 tests passed, 1 Qdrant integration test skipped, 3 live tests deselected, and 87% total
  coverage. The live-model and live-provider markers were excluded.

Live calls total exactly nineteen: eighteen historical calls across three explicit six-call
approvals before model-backed routing, plus one post-completion narrative replay:

1. Aggregate six-agent command — five HTTP 200 responses; the former deterministic router stopped
   because “market history” did not match its “historical price” keyword. That lexical router has
   since been removed; this entry is retained only as historical evidence of requests actually made.
2. Market-only diagnostic command — one HTTP 200 response and all model/agent assertions passed;
   the final assertion expected `fake-market` instead of the real fixture identifier
   `fake_market_data_v1`. The assertion is corrected.
3. Corrected aggregate command — six HTTP 200 responses; all six agents, structured outputs,
   deterministic facts, model identity, and usage assertions passed. The final privacy assertion
   then found the terminal RunEvent response leak. The event summary is now status-only, and the
   credential-free regression test passes.
4. Final corrected aggregate command — six HTTP 200 responses and `1 passed in 6.46s`; all six
   live agent contracts, deterministic authority, metadata/usage, credential exclusion, and
   RunEvent response-exclusion assertions passed.
5. Post-completion Finance QA replay — one HTTP 200 response using five retrieved evidence items;
   2,051 input tokens and 392 output tokens produced a 1,547-character, terminally punctuated
   answer under `openai-agent-system-v2`, with no internal-generation warning. No raw response was
   recorded in the evidence artifact.

The exact commands and machine-readable outcomes are recorded in
`backend/artifacts/m4_1/test-results.json`.

## Limitations and unresolved decisions

- No external LangSmith trace sample exists yet. Adding the key and tracing/project variables may
  qualify one later, but is not required for model correctness and must preserve hidden inputs and
  outputs.
- Monetary model cost is deliberately unavailable. Provider token counts are measured, but a
  versioned price/service-tier calculator is deferred rather than applying mutable web pricing at
  runtime.
- The synchronous SDK path has deadline and timeout enforcement but no independent cooperative
  cancellation hook. M5/M8 must revisit cancellation when request lifecycle integration exists.
- Standard API processing was qualified; regional processing, Zero Data Retention, organization
  controls, and public-deployment privacy requirements remain unqualified.
- The rolling `gpt-6.1-sol` identifier can change behavior. M8 must re-run fixed quality, safety,
  latency, and cost evaluations and reconsider a dated snapshot if one becomes available.
- Live LLM routing has adapter-level contract coverage but has not been externally requalified
  after the 2026-10-29 routing change. A seven-call aggregate rerun requires an explicit live-call
  approval; ordinary test success is not represented as semantic routing evidence.

## Evidence paths

- `docs/research/M4_1_openai_model_selection.md`
- `backend/artifacts/m4_1/model-prompt-inventory.v1.json`
- `backend/artifacts/m4_1/test-results.json`
- `backend/tests/test_openai_model_adapter.py`
- `backend/tests/test_model_factory.py`
- `backend/tests/test_live_model_adapter.py`

M4.1 has satisfied its acceptance gate. M5 is the next permitted milestone; the remaining items
above are explicit later qualification or production-hardening work, not M4.1 blockers.
