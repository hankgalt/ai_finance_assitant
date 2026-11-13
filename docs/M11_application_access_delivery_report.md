# M11 delivery report — Application access and isolation

Status: Slice 2 implemented and verified; staging foundation later provisioned; workload/edge deployment pending | 2026-11-10

## Scope and decisions

This slice implements the application-access portion of PR-017 under ADR-019, ADR-029, and proposed
ADR-030. It advances QR-001, QR-003–QR-007, QR-010–QR-011, and QR-014–QR-015 and records slice-level
EVAL-19 evidence with the applicable EVAL-13 and EVAL-18 regressions. It does not claim EVAL-20 or
complete M11 deployment qualification.

The approved initial owner admission email is `vtalwar.w@comfforts.com`. Owner and viewer
Principals may read and mutate only their own product resources; application administrative
operations require the owner role. A disabled Principal is rejected at the next HTTP request or SSE
reconnect. Edge-IAP revocation blocks at the edge when configured; neither revocation path cancels an
in-flight request, transfers ownership, nor deletes retained data.

The cloud application store starts empty. Existing local application data does not migrate to the
deployed owner, and current RAG collections remain a separate knowledge-release concern. Local
development uses the fixed loopback-only owner fixture documented by the deployment contract, and
local and deployed navigation both use `/finance_assistant`.

## Delivered implementation

- Signed Google IAP JWT validation for the configured issuer, audience, ES256 signature, expiry,
  issued-at time, subject, and email; anonymous, unsigned, invalid, unknown, and disabled identities
  fail closed.
- Immutable Application Principal IDs derived from verified issuer and subject. Email remains
  mutable admission/display metadata and is never a resource-ownership key.
- Persisted owner/viewer/disabled Principal policy and request-boundary authorization middleware.
  The liveness probe is the sole identity-middleware exception for later load-balancer health checks.
- Principal ownership and authorization across Sessions, checkpoints, Runs, RunEvents, SSE,
  Portfolios, Snapshots, Goals, History, Inspector, authorized agent context, idempotency, archive,
  deletion, and response-cache namespaces.
- SQLite application schema version 4. Existing local schema 1–3 rows and checkpoint threads migrate
  only to the explicit loopback-development Principal; this is not a cloud data migration. Runtime
  configuration rejects stale schema-version pins before identity services initialize.
- Owner-only application administration under IAP. Viewer live-provider operations remain denied
  until ADR-024–ADR-026 rights explicitly approve them; credential-free product use remains allowed.
- `/finance_assistant` Vite build, browser navigation, API/SSE URL, telemetry, contract, and test
  behavior. The frontend selects its stored active Session in a Principal-specific namespace.
- Versioned deployment access contract and updated public HTTP, frontend, and Inspector contracts.
  No OAuth library, credential, secret, infrastructure, DNS, or GCP resource was added.

## Verification record

| Command/check | Actual result |
|---|---|
| `backend/.venv/bin/ruff format --check src tests` | 150 files already formatted |
| `backend/.venv/bin/ruff check src tests` | passed |
| `backend/.venv/bin/mypy` | passed for 150 source/test files |
| `backend/.venv/bin/python -m pytest -q` | 353 passed, 1 skipped, 4 deselected in 6.07 s |
| Focused configuration/identity/persistence/cache/contract suite | 50 passed in 2.01 s |
| `backend/.venv/bin/python -m pytest -q tests/test_release_bundle.py` | 6 passed |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache uv lock --check --offline` | 131 packages resolved; lock current |
| `frontend/pnpm format:check` | passed |
| `frontend/pnpm lint` | passed with zero warnings |
| `frontend/pnpm typecheck` | passed |
| `frontend/pnpm test` | 14 files and 72 tests passed |
| `frontend/pnpm build` | production build passed |
| `frontend/pnpm test:e2e` | 10 Playwright tests passed in 31.2 s |
| `git diff --check` | passed |

The first Playwright attempt could not bind `127.0.0.1:4173` because the managed sandbox denied the
loopback listener. The same suite passed after granting the test process permission to bind that
loopback-only port. The backend skip and four deselections are the existing opt-in integration and
credential-gated live-provider/model tests, not application-access failures.
The first offline lock check could not initialize uv's user cache because the managed sandbox denied
that directory; the identical check passed with the existing writable temporary uv cache.

## Acceptance evidence

- Cryptographic negative tests cover missing assertions, wrong keys, invalid issuers, audiences,
  expiry, unknown emails, and disabled Principals. Changing an admitted identity's email while
  retaining issuer/subject preserves its Principal ID and ownership.
- The two-Principal matrix proves that owner and viewer can use identical resource and idempotency
  identifiers without collision and cannot enumerate, read, mutate, stream, continue, inspect,
  archive, or delete one another's product resources.
- Persistence and checkpoint tests prove Principal-scoped migration, restart, event, context,
  cache, and thread behavior. Cross-Principal lookups return non-disclosing not-found responses.
- Configuration tests reject loopback identity in production or on a non-loopback host and reject
  incomplete IAP configuration. Browser tests exercise the common base path and Principal-specific
  active-Session storage.
- Public machine contracts record the external base path, signed identity claim, role/revocation
  matrix, local fixture, empty-store decision, and identity endpoint.

## Security and privacy impact

Application ownership is now bound to a stable cryptographically verified external identity rather
than an email address, browser state, or opaque resource identifier. Authorization is repeated at
each request boundary and at repository lookups, including SSE reconnect and Inspector access.
Logs, events, prompts, and resource records do not use email as an ownership key. Shared knowledge
and existing provider policies are unchanged; viewer live-provider access is conservatively denied.
The fixed development identity is visibly synthetic, cannot be enabled in production, and requires a
loopback host.

## Limitations and unresolved work

- Proposed ADR-030 remains Proposed. No Google Cloud resource, IAP edge policy, load balancer,
  direct-origin denial, managed state, production Qdrant transfer, Redis topology, Secret Manager
  integration, Terraform, CI/CD, DNS, certificate, backup/restore, or rollback control is operational.
- Application disablement is persisted and enforced by the access layer, but an owner-facing role or
  revocation-management interface is not part of this slice. Operational admission/revocation
  tooling belongs with the selected managed-state and deployment design.
- Removing a viewer from static admission configuration does not mutate an already persisted
  Principal. Revocation uses the edge IAP grant and/or persisted `disabled` status.
- In-flight work is not force-cancelled. Revocation takes effect on the next request boundary or SSE
  reconnect, as approved.
- The liveness probe intentionally contains no product data and bypasses application identity so a
  future load balancer can health-check the workload. M11 infrastructure must still prove that no
  direct workload origin is internet-accessible.
- Viewer market/news live-provider rights remain unresolved under ADR-024–ADR-026. This slice does
  not broaden source, retention, or display rights.
- EVAL-20 and the remaining EVAL-19 edge/bypass and deployed penetration checks await the later M11
  managed-state, infrastructure, staging, and release-qualification slices.

## Artifacts

- [ADR-030](02_architecture_decision_records.md#adr-030-iap-protected-gcp-private-multi-user-deployment--accepted)
- [M11 implementation plan](04_implementation_plan.md#m11--iap-protected-gcp-private-multi-user-deployment)
- [`contracts/deployment/application-access.v1.json`](../contracts/deployment/application-access.v1.json)
- `backend/src/ai_finance_assistant/identity/`
- `backend/tests/test_identity_access.py`
- `backend/tests/test_deployment_access_contract.py`
- `frontend/src/lib/urls.ts`
