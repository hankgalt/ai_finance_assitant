# M8 local operational runbook

## Qualification

1. Use `.test.env`; do not point qualification at `backend/.env`.
2. Start Qdrant and Redis: `docker compose up -d qdrant redis-response-cache`.
3. Run `make m8-check`. The fixed runner strips application/model/provider tracing environment
   variables, then runs backend, frontend, browser, Qdrant, and Redis checks.
4. Read `backend/artifacts/m8/qualification-report.v1.json`. A nonzero command is expected while a
   critical check fails, evidence is missing, or human review remains pending.
5. Stop local dependencies when no longer needed: `docker compose stop qdrant redis-response-cache`.

## Failure triage

- **Qdrant unavailable/incompatible:** keep runtime retrieval unavailable; do not regenerate or
  activate collections at startup. Check container health, alias, payload schema, and pinned model
  metadata. Re-run the integration test before restoring the app.
- **Redis unavailable/corrupt:** response caching must bypass and the workflow must continue. Keep
  semantic mode `shadow` or disable the adapter. Purge the local index only through the configured
  administrative endpoint or by recreating the non-persistent local service.
- **SQLite migration/restart:** copy the local database before manual repair. A newer schema is a
  hard startup failure. Do not delete a Session except through archive then permanent deletion.
- **Provider quota/auth/malformed payload:** keep typed unavailable/partial behavior. Never switch
  silently to synthetic data. Select another approved adapter explicitly if permitted.
- **Collector/LangSmith outage:** product execution and RunEvent persistence continue. Use explicit
  trace-unavailable state; do not retry exporters on the critical request path.
- **Browser/API correlation gap:** use the returned execution and trace identifiers, then reconcile
  frontend request, FastAPI span, optional LangSmith root, and authoritative RunEvents. Do not infer
  missing events from the final answer.

## Purge and recovery

Administrative provider/response-cache purge requires the configured local admin token. Session
archive and permanent deletion purge the Session response-cache namespace and checkpoint state.
Original uploaded bytes are never retained by the import result. Knowledge collections and source
provenance are independent of user-data deletion.
