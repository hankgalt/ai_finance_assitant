# AI Finance Assistant

AI Finance Assistant is a U.S.-focused financial education and analysis product. The repository is at **M1: persistent Qdrant and offline knowledge ingestion**. It has a working foundation, versioned Finance and Tax knowledge collections, and read-only collection readiness. It does not yet provide financial calculations, working LangGraph agents, live market/news data, saved user data, or professional financial or tax advice.

Read [docs/README.md](docs/README.md) before implementation work. Repository-wide engineering instructions are in [AGENTS.md](AGENTS.md). M1 evidence and limitations are in [docs/M1_delivery_report.md](docs/M1_delivery_report.md).

## Current capabilities

- FastAPI liveness/readiness and React application shell from M0.
- Reviewed SourceRegistry with permitted-use, status, provenance, and tax-year fields.
- Explicit offline HTML/PDF ingestion with integrity-checked source caching, deterministic normalization/chunking, source/content hashing, and resumable batched writes.
- Persistent Qdrant 1.20.0 collections with named dense and sparse vectors, filter indexes, immutable manifests, atomic active aliases, and rollback.
- Locally generated BGE-small dense and Qdrant BM25 sparse representations with exact model revisions and artifact hashes.
- Dense, sparse, and hybrid/RRF evaluation against fixed Finance and Tax qrels.
- Runtime readiness that validates active aliases, schema, vector configuration, model artifacts, payload indexes, ready state, and nonempty collections without fetching or embedding.

LangGraph, the six working agents, deterministic financial modules, provider adapters, SSE, saved user data, MCP, and real Inspector instrumentation belong to later milestones.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose v2
- Node.js 22 or newer
- pnpm 11

Dependencies are local to `backend/.venv` and `frontend/node_modules`. Qdrant data is held in the Compose-managed `qdrant-storage` volume.

## Install and configure

~~~bash
make backend-sync
make frontend-install
cp .env.example backend/.env
~~~

The generated lockfiles are the reproducibility authority. The example configuration enables only the loopback Qdrant service and requires no credentials.

## Run locally

~~~bash
make qdrant-up
make backend-dev
~~~

In another terminal:

~~~bash
make frontend-dev
~~~

Open http://127.0.0.1:5173. Vite proxies `/api` to the backend at http://127.0.0.1:8000.

Health interfaces:

- `GET /api/health` — aggregate service status.
- `GET /api/health/live` — process liveness.
- `GET /api/health/ready` — HTTP 200 only when both active Qdrant collections match the expected M1 contract; otherwise HTTP 503.

Application startup and health checks never fetch sources, download models, create collections, or generate embeddings.

## Offline knowledge maintenance

These commands intentionally run outside application startup. They fetch only enabled, approved registry entries, build an immutable candidate, evaluate it, and activate it only after the gate passes:

~~~bash
make knowledge-finance
make knowledge-tax
make knowledge-validate
~~~

Raw source responses are cached under ignored `backend/.cache/knowledge-sources/`. Use the CLI `--refresh-sources` option only for a deliberate source refresh. Manifests and evaluation evidence are written under `backend/artifacts/m1/`.

Stop Qdrant without deleting its volume:

~~~bash
make qdrant-stop
~~~

## Verify

~~~bash
make verify
make qdrant-check
make knowledge-validate
~~~

`make verify` is credential-free and skips the live-Qdrant integration test. `make qdrant-check` explicitly exercises candidate creation, compatibility validation, atomic activation, rollback, and cleanup against the loopback service.

## Local security posture

The development services bind to `127.0.0.1`. Local Qdrant has no authentication and is not a production deployment. Do not expose it publicly. Only reviewed public educational sources are enabled, raw source caches are ignored, and no user financial data is part of M1. Logs continue to exclude request bodies, query values, credentials, raw prompts, holdings, and transaction payloads.
