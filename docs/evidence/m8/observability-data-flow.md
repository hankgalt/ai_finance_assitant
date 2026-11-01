# M8 observability data flow

Date: 2026-10-31 | Authority: ADR-011, ADR-014, ADR-019, ADR-028

```text
React browser telemetry ──versioned REST──┐
                                          v
FastAPI middleware ── spans/metrics ── SafeObservability ── OTLP/Collector (optional)
        │                                 │
        ├─ request correlation            └─ exporter failure is swallowed and measured as unavailable
        v
LangGraph workflow ─ agents ─ retrieval/providers/model
        │
        ├─ privacy-filtered RunEvents ── SQLite (authoritative Inspector record)
        ├─ hidden-input/output LangSmith trace (optional, configured project)
        └─ returned trace_id or explicit trace_unavailable_reason
```

The browser never sends holdings, prompts, responses, Session IDs, Run IDs, or URLs as telemetry
attributes. Backend metric routes use templates. `SafeObservability` and RunEvent metadata have
separate allow-lists and reject arbitrary keys. Response-cache telemetry records only bounded
operation/outcome/match/policy dimensions; RunEvents additionally retain bounded similarity and
age buckets plus whether a model request was avoided.

RunEvents are the authoritative Inspector input. OpenTelemetry and LangSmith are operational
correlation surfaces and may be unavailable without changing product state. Local Session and
RunEvent defaults are 30 days; Portfolios default to 365 days. Local Redis response-cache entries
are non-persistent with a maximum 24-hour TTL and are purged with Session archive/deletion.
External trace retention and sampling are deployment-owned and therefore remain a production gap;
the application must not imply that a Collector or LangSmith retention setting is enforced here.
