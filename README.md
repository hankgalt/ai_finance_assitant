# AI Finance Assistant

AI Finance Assistant is a U.S.-focused financial education and analysis product. The repository is currently at **M0: foundation and contracts**. It does not yet provide financial calculations, working agents, live market/news data, knowledge retrieval, persistent user data, or professional financial or tax advice.

Read [docs/README.md](docs/README.md) before implementation work. Repository-wide engineering instructions are in [AGENTS.md](AGENTS.md).

## M0 capabilities

- FastAPI application with aggregate health, separate liveness, and honest readiness responses.
- Versioned Pydantic contracts for six agent identifiers, safe errors, portfolio identities, provider provenance, quotes, and RunEvent v1.
- Local-safe configuration, request correlation, structured logs, allow-list trace metadata, and protected-field redaction.
- React/TypeScript/Vite application with five accessible navigation shells.
- Backend health indicator and an explicitly labeled synthetic Inspector timeline.
- Credential-free backend and frontend checks.

Qdrant ingestion, collection validation, LangGraph, real agents, financial modules, provider adapters, saved data, SSE, MCP, and real Inspector instrumentation belong to later milestones.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 or newer
- pnpm 11

Dependencies are local to backend/.venv and frontend/node_modules. The bundled
pnpm runtime is sufficient; no global package installation is required.

## Install

~~~bash
make backend-sync
make frontend-install
~~~

The generated lockfiles are the reproducibility authority and should be updated only
with intentional dependency changes.

## Run locally

Terminal 1:

~~~bash
make backend-dev
~~~

Terminal 2:

~~~bash
make frontend-dev
~~~

Open http://127.0.0.1:5173. Vite proxies /api to the backend at http://127.0.0.1:8000.

Health interfaces:

- GET /api/health — HTTP 200 aggregate; M0 is live but degraded.
- GET /api/health/live — HTTP 200 liveness.
- GET /api/health/ready — HTTP 503 until M1 implements and validates active Finance and Tax Qdrant collections.

That 503 response is intentional: configuration alone must not be reported as collection readiness.

## Verify

~~~bash
make verify
~~~

Individual suites:

~~~bash
make backend-check
make frontend-check
~~~

All M0 tests run without credentials, Qdrant, model providers, market/news providers, or paid services.

## Local security posture

M0 binds development servers to 127.0.0.1 and has no authentication or user-data persistence. This is a local foundation, not a public deployment. Do not expose it publicly. Logs exclude request bodies, query values, credentials, raw prompts, holdings, and transaction payloads.

Configuration examples are in [.env.example](.env.example). Store real secrets only outside version control in later milestones.
