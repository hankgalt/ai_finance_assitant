# M4.1 OpenAI model selection record

Status: Approved for private-demo qualification | Reviewed: 2026-10-28

## Decision

Use OpenAI `gpt-6.1-sol` through the Responses API as the initial live ModelAdapter for routing and
specialist generation in the private demonstration release. Keep `deterministic-model-v1` as the
default credential-free adapter for development, ordinary tests, and reproducible demonstrations.
Selection occurs once per Run; missing approval, credentials, quota, or availability never changes
a live Run to the deterministic adapter.

The product owner selected OpenAI and `gpt-6.1-sol`, accepted the default API retention posture
for synthetic qualification data, and approved the historical six-provider-request live-test
budget. Model-backed routing raises the current six-agent aggregate ceiling to seven calls; no
post-change live rerun is implied by the earlier approval. This is not approval to send real
portfolio records or other sensitive user data during qualification.

## Fit against M4.1 criteria

| Criterion | Finding and implementation consequence |
|---|---|
| Structured output | The model supports Structured Outputs and the Python SDK supports Pydantic parsing through `responses.parse`. The adapter accepts only `ModelOutput` v1 and fails closed on refusal, incomplete, or malformed output. |
| Capability | The model supports low through max reasoning effort. Finance and Tax use `medium`; Portfolio, Market, Goal, and News use `low`. No vendor tools are enabled. |
| Context limits | The published API context is much larger than this product needs. The application still caps serialized input at 40,000 characters and output at 1,200 tokens because provider capacity is not a privacy or cost budget. |
| Privacy and training | OpenAI states that API data is not used for model training unless the account explicitly opts in. Responses requests set `store=False`; default abuse-monitoring retention can still be up to 30 days and was accepted only for the synthetic qualification. |
| Retention | `store=False` disables ordinary Responses application-state storage. It does not claim Zero Data Retention or remove default abuse-monitoring retention. |
| Region | Standard API processing is used. Regional processing is not configured or qualified; the model page notes a premium where regional processing is available. This remains a public-deployment decision. |
| Latency and availability | Each call is bounded by the smaller of the Run deadline and a 30-second request timeout. Retryable failures receive bounded backoff, but every attempt consumes the per-Run request budget. Account-tier availability and rate limits remain external dependencies. |
| Cost | Published standard pricing at review time was $2.00 per million input tokens and $10.00 per million output tokens. RunEvents record provider-reported token counts. Monetary cost remains explicitly unavailable until a versioned pricing calculator and service-tier inputs are approved. |
| Versioning | The configured model identifier is recorded on Model RunEvents. `gpt-6.1-sol` is currently the published snapshot name; model-behavior drift remains an evaluation risk and M8 must requalify it. |

## Safety and data-flow policy

- The versioned trusted instructions are separate from a JSON data envelope containing the user
  message, bounded evidence, and deterministic facts.
- The adapter tells the model that all envelope content is untrusted data. This prompt boundary is
  defense in depth; schemas, deterministic authority, tool restrictions, and redaction remain in
  code.
- Model output contains only a summary and warnings. Agents return the original deterministic
  facts supplied by the owning module, so generated text cannot replace calculations or provider
  provenance.
- Responses are stateless (`store=False`), use no tools, and do not send provider credentials.
- RunEvents and OpenTelemetry record only allow-listed provider, model, prompt-version, timing,
  usage, status, and correlation fields. They exclude request/response content.
- Optional LangSmith tracing keeps inputs and outputs hidden. Current `LANGSMITH_*` variables and
  the legacy `LANGCHAIN_*` aliases are accepted, but LangSmith is not the authoritative Run record.

## Sources

- [GPT-6.1 Sol model capabilities, limits, pricing, and rate-limit tiers](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [Structured Outputs and Python Pydantic parsing](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)
- [Responses storage control](https://developers.openai.com/api/docs/guides/migrate-to-responses?api-mode=responses)
- [Current LangSmith tracing environment variables](https://docs.langchain.com/oss/python/integrations/llms/openai)

## Revisit triggers

Re-evaluate this selection before public launch, when account data-control terms change, when a
stable dated model snapshot becomes available, when measured M8 quality/latency/cost misses its
gate, or when regional/Zero Data Retention requirements are approved.
