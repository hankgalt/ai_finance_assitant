# M0 delivery report

Date: 2026-10-27  
Status: Complete

## Scope and traceability

M0 implements the foundation described by PR-010 and PR-014; QR-005, QR-007, QR-012, QR-013, and QR-015; and ADR-007, ADR-011, ADR-013, ADR-014, ADR-015, ADR-016, and ADR-019.

It deliberately does not implement Qdrant ingestion/validation, LangGraph workflows, working agents, finance calculations, provider adapters, persistence, SSE, MCP, or live execution inspection.

## Delivered

- FastAPI application, health/readiness interfaces, configuration, request correlation, safe logging, and redaction.
- Pydantic contracts for six agent identifiers, AgentRequest/AgentResult, safe errors, provider provenance/Quote, portfolio identities, and RunEvent v1.
- React/TypeScript/Vite/Tailwind foundation with five navigation shells, health display, shadcn/ui-compatible tokens, and synthetic Inspector timeline.
- Backend/frontend tests, lint/typecheck/format/build commands, local run documentation, and credential-free configuration. pnpm is used for the frontend after npm 10.9.7 failed internally while resolving Vitest peer dependencies.

## Verification evidence

The repository-level verification command completed successfully:

~~~text
UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify
Backend: Ruff format/check, strict mypy, and pytest with coverage passed.
Frontend: Prettier, ESLint, TypeScript, Vitest, and Vite production build passed.
~~~

Detailed results:

- Backend: 10 tests passed; 96% statement coverage; 23 source files passed strict mypy; Ruff reported no formatting or lint errors.
- Frontend: 3 component tests passed; ESLint, TypeScript, and Prettier checks passed; Vite 8.3.5 built 66 modules successfully.
- Runtime: direct API and Vite-proxied `GET /api/health` returned HTTP 200 with `degraded`; `GET /api/health/ready` returned the intentional HTTP 503 `not_ready` state.
- Browser QA: all five destinations were exposed as accessible buttons; the Inspector rendered the labeled synthetic RunEvent v1 timeline; the health badge reported `API live · M0 not ready`.
- Contract fixture: the same versioned synthetic RunEvent JSON is imported by the frontend and validated by the backend test suite.

## Security and privacy

- Development hosts default to 127.0.0.1.
- No authentication or persistent user data exists; the UI labels local M0 limitations.
- Request logs contain method, path, status, duration, and correlation identifier only.
- Redaction protects credential, prompt, holding, and transaction keys; trace metadata uses an allow-list.
- Synthetic events contain no raw financial data, credentials, prompts, hidden reasoning, or measured provider/model usage.

## Deviations and limitations

- Qdrant readiness is intentionally not ready in M0. The backend reports the expected aliases and schema but performs no network connection or collection creation.
- React Flow and Recharts are dependency foundations only; no graph or financial chart is rendered.
- Playwright was not added because M0 browser behavior is covered by component tests and there is not yet an end-to-end product workflow.
- pnpm 11.25.0 is used for frontend installation because the available npm 10.9.7 client failed internally while resolving the dependency graph. The resulting pnpm lockfile is checked in.
- Production authentication, protected storage, retention enforcement, and public deployment controls remain unimplemented.

## Open decisions before M1

- Select Qdrant hosting mode for local development and evaluation.
- Select and version dense and sparse representation models.
- Approve the Qdrant payload schema, chunk policy, relevance gates, and fixed retrieval set.
- Approve source registry entries and permitted-use treatment for the initial Finance and Tax content.

## M1 entry recommendation

M0's executable foundation is ready. Begin M1 after the open Qdrant, representation-model, payload-schema, and source-registry decisions have owners or approved experiment plans.
