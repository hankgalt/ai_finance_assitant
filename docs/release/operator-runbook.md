# Private-demo operator runbook

## Release boundary

Operate this release only for the owner and approved viewers on a controlled machine. Bind services
to loopback. Do not expose local SQLite, unauthenticated Qdrant, Redis, Vite, FastAPI, or the MCP
stdio process to a public network.

## Select one provider mode before startup

| Mode | Model | Market/news | Intended use |
|---|---|---|---|
| Credential-free | deterministic fake | synthetic fixtures | reproducible demo, CI, outage fallback |
| Live model only | OpenAI `gpt-6.1-sol` | synthetic fixtures | selected-model Assistant demo |
| Live providers | configured OpenAI or fake | selected Alpha Vantage/Massive + Tavily | owner-only quota-bounded provider demo |

Use the credential-free mode unless a live journey has explicit account terms, credentials, and a
request budget. Never silently switch market providers inside a Run. Massive individual-plan data
remains owner-only unless separately approved commercial display rights cover the audience.

## Preflight

1. Compare `.env.example` with `backend/.env`; never commit secrets.
2. Run `docker compose config --quiet`, `make qdrant-up`, `make response-cache-up`, and `make
   knowledge-validate`.
3. Start the backend and verify `/api/health/live` and `/api/health/ready` return HTTP 200.
4. Start the frontend and verify the credential-free sample journey before any optional live call.
5. For live providers run `make provider-live-check`; it uses only explicitly marked tests.
6. For a live model run `make model-live-check`; inspect the configured project and privacy flags.

## Request budgets and cache assumptions

- Application model budget: at most eight attempts per Run; the standard single-domain path uses a
  routing call plus one specialist call. A multi-agent path adds selected specialists and bounded
  synthesis within that ceiling.
- Provider smoke test ceiling: at most three requests to the selected market provider and one to
  Tavily.
- Application provider budgets: five market requests and three news requests per Run.
- Redis response cache: only public Finance/Tax RAG requests are eligible. `shadow` measures
  candidates without serving them; `serving` may return only an approved evidence/version-bound
  match at or above `0.92`. Portfolio, Market, News, Goal, multi-agent, context-bearing, and
  checkpoint-dependent requests bypass it.
- The demo script's credential-free alternative makes zero external model/provider requests.

Redis is intentionally configured without RDB/AOF persistence. A container restart normally
retains the running container's memory, while container recreation, volume-independent replacement,
or eviction clears entries. Cache loss is safe: it increases latency but does not remove source or
application records.

## Observability

`AIFA_OBSERVABILITY_MODE=disabled|in_memory|opentelemetry` controls the vendor-neutral adapter.
RunEvents stored by the application remain the Inspector authority in every mode.

- **Disabled:** no operational spans/metrics are emitted; RunEvents still exist.
- **In-memory:** tests and local inspection only.
- **OpenTelemetry:** set export false for local no-network instrumentation, or start the loopback
  Collector with `make observability-up` and deliberately set export true.

Only allow-listed bounded attributes are exported. Raw prompts, generated answers, credentials,
holdings, provider payloads, and unbounded Session/Run identifiers are excluded. Sampling and
retention after an external Collector are deployment-owned and must be reviewed before export.

LangSmith is optional for LangGraph/model traces. Set `AIFA_LANGSMITH_TRACING_ENABLED=true`,
`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` only after approving vendor
retention. Inputs and outputs remain hidden. `LANGSMITH_PROJECT` selects the destination; it does
not rename the product's root workflow span. If LangSmith or OTLP is unavailable, the Run continues
and telemetry is labeled unavailable rather than fabricated.

Troubleshoot by copying the visible trace correlation identifier, locating the RunEvents first,
then correlating backend logs, OpenTelemetry spans, and optional LangSmith traces. A missing external
span never overrides the recorded event timeline.

## Data lifecycle and rollback

Clearing an Active Session archives it. Permanent deletion is available only for an Archived
Session and cascades its defined artifacts/checkpoint. Portfolio deletion removes that Portfolio
and snapshots. Local retention settings run during startup.

For application rollback, stop the processes, restore the previous code and lockfiles, and restart;
the schema guard refuses a database newer than the configured expected version. Before a database
change, copy the SQLite file while the app is stopped. For knowledge rollback, use the M1 alias
rollback record/CLI so aliases move atomically to a compatible ready collection. For response-cache
rollback, set semantic mode to `shadow` or adapter to `disabled`; deleting cache data is not needed.

Never use a code rollback to imply database downgrade support. If the schema is incompatible,
restore a matching disposable-demo backup or move the old file aside and start a new local store.
