# M9.1 product-oriented repository layout delivery report

Status: **complete**  
Completed: 2026-11-02  
Implements: PR-014, QR-015, ADR-029

## Outcome

Durable machine assets are now owned by product capabilities and interfaces rather than delivery
milestones. The authoritative ownership map is
[repository_layout.md](repository_layout.md).

- Committed backend inputs now live under capability directories such as `knowledge/`,
  `calculations/`, `providers/`, `assistant/`, `response-cache/`, and `qualification/`.
- Backend evidence now lives under capability directories plus the cross-product `quality/` and
  `release/` owners. Knowledge artifacts are further separated by Finance and Tax knowledge base.
- Machine contracts are grouped by the consuming interface under `contracts/api/`,
  `contracts/frontend/`, `contracts/inspector/`, and `contracts/fixtures/`.
- Backend test filenames describe behavior or capability. The release-bundle suite rejects a return
  of milestone-owned backend data, artifact, contract, or test paths.
- CLI defaults, Make targets, fixture manifests, qualification inputs, checksums, delivery reports,
  and release evidence now resolve to the capability paths. Existing milestone Make targets remain
  compatibility aliases for the capability-named targets.
- Workflow, LangSmith-project, and OpenTelemetry-service identities now come from distinct
  environment settings. API Run creation, checkpoint cleanup, benchmark requests, backend tests,
  and frontend test fixtures consume those settings instead of embedding the release identity.
  Production frontend code contains no workflow-identity literal; it continues to render the
  backend contract value.

No active Qdrant collection identity, runtime database location, financial calculation, public API,
provider policy, or release scope changed. Path metadata in retained evidence was updated so it
continues to resolve from its single current location.

## Verification

The following commands were run from the repository root unless noted:

- `backend/.venv/bin/pytest -q backend/tests/test_portfolio_import.py
  backend/tests/test_portfolio_analysis.py backend/tests/test_goal_projection.py
  backend/tests/test_provider_adapters.py backend/tests/test_public_http_contract.py
  backend/tests/test_frontend_contract.py backend/tests/test_inspector_contract.py
  backend/tests/test_release_bundle.py backend/tests/test_release_qualification.py
  backend/tests/test_knowledge_pipeline.py` — **104 passed**.
- `UV_CACHE_DIR=/private/tmp/aifa-uv-cache make backend-check` — formatting, lint, and strict typing
  passed; **275 passed, 1 Qdrant test skipped because the ordinary suite omits the opt-in URL, and 4
  live/Redis tests deselected**; measured backend coverage was 87%.
- `make frontend-check` — formatting, lint, type checking, **36 tests**, and production build passed.
- `UV_CACHE_DIR=/private/tmp/aifa-uv-cache make release-check` with approved local service/port
  access — frontend line coverage **80.11%**; **275 backend tests passed, 1 ordinary-suite skip, 4
  ordinary-suite deselections; 36 frontend tests; 9 Playwright journeys; 1 Qdrant integration; 1
  Redis integration; 8 MCP/release-bundle tests**. All EVAL-01 through EVAL-18 dimensions passed,
  with zero critical failures or incomplete dimensions.
- JSON parsing for every file below `backend/data/`, `backend/artifacts/`, and `contracts/`, plus
  `git diff --check`, passed.

The environment-owned identity follow-up was verified with:

- Focused backend tests for configuration, observability, workflow, cache, persistence, agents, and
  qualification — **74 passed**; Ruff and strict mypy also passed.
- Full credential-free backend suite — **277 passed, 1 Qdrant integration skipped, and 4 explicit
  live/Redis tests deselected**; the deterministic response-cache benchmark completed with all four
  scenarios.
- Frontend type checking, linting, **36 unit tests**, production build, and **9 Playwright
  journeys** — all passed.
- Exact-literal audits over `backend/src`, `backend/tests`, `frontend/src`, and `frontend/e2e`, plus
  `git diff --check` — passed with no embedded release workflow ID, LangSmith project default, or
  OpenTelemetry service-name default in implementation or test fixtures.

The first unqualified `make backend-check` attempt could not write the sandboxed default uv cache;
the recorded rerun used the repository-standard temporary cache path. The first coverage attempt
reported 79.52% after the preceding Goals UI changes; a focused Goal form behavior assertion raised
measured coverage to 80.11%. A sandboxed full-qualification attempt also correctly failed local
socket and port access; the final approved local-service run above passed.

## Security, privacy, and operational impact

- No credentials, prompts, user financial records, raw provider payloads, or new runtime state were
  added or moved.
- Runtime SQLite, Redis, and Qdrant behavior is unchanged. Redis remains an optional response-cache
  accelerator, and Qdrant retains the existing active collection aliases and versions.
- Moving evidence does not broaden source-use rights, provider entitlements, retention, or public
  deployment authorization.
- Historical milestone reports remain under `docs/` because they are delivery evidence, not current
  machine-asset ownership boundaries.

## Limitations and unresolved decisions

This maintenance deliberately does not redesign Python package modules, rename historical delivery
documents or frontend coursework E2E specifications, migrate ignored local databases, or implement
M10. Future assets must follow ADR-029 and the repository-layout map; a new cross-product asset
without a clear owner still requires an explicit architecture decision.
