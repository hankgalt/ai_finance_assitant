# M8 correlation, redaction, and exporter-failure report

The correlated request evidence is split across first-party artifacts and reconciles one W3C trace
identity through browser request headers, FastAPI/OpenTelemetry, the returned Run, and persisted
RunEvents:

- `docs/evidence/m6/browser-fastapi-correlation.md` verifies browser `traceparent` and request
  correlation without promoting identifiers into metric dimensions.
- `backend/artifacts/m5/trace-correlation-sample.v1.json` records input trace ID
  `11111111111111111111111111111111` as the Run and persisted RunEvent trace ID and confirms
  outbound HTTPX propagation.
- `tests/test_m5_observability.py` verifies actual OpenTelemetry span/RunEvent trace agreement,
  hidden LangSmith inputs/outputs, and product completion when every exporter operation fails.

M8 adds sensitive-field canaries plus 128-session cardinality pressure. Prompt/message/token fields
and synthetic canary `M8-DO-NOT-EXPORT` are absent; all 128 HTTP metrics reduce to one bounded
attribute set. Cache RunEvents retain only bounded operation/outcome/match/policy/mode, age and
similarity buckets, and avoided-call truth. Raw query, Session/Run identity, and unbounded reason
text are dropped.

The selected-model review created privacy-hidden LangSmith Runs in the configured project. Root
and child records exposed timing and bounded lifecycle metadata while inputs and outputs remained
hidden. Four exact-hit roots were retained for p50/p95 comparison. The short-lived harness emitted
background-export shutdown warnings and did not retain every repeated exact-hit trace; all
first-party Run results and RunEvents completed. This demonstrates that optional exporter loss does
not corrupt product state, while RunEvents remain the authoritative Inspector record. See
[the selected-model review packet](live-model-review.md).
