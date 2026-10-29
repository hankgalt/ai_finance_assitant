# M6 delivery report — React product experiences

Date: 2026-10-29  
Status: Complete for the production-oriented private local demonstration  
Scope: PR-003–PR-011; QR-001–QR-007 and QR-009–QR-015; ADR-007, ADR-009,
ADR-011, ADR-012, ADR-014, ADR-015, ADR-018, ADR-019, ADR-023

## Outcome

M6 replaces the M0 placeholders with four responsive React experiences backed by the M5
interfaces. The Assistant creates and reloads authoritative Runs, supports context-free public
ticker-news questions through the News specialist's bounded default, distinguishes the latest
response from earlier Run history, and renders each selected agent's typed result, citations, warnings,
evidence time, and saved-stream recovery status. The Portfolio
Dashboard accepts manual, JSON, CSV, and XLSX input through one API contract, requires validation
review and explicit save approval, and renders backend Portfolio Snapshots. Market Overview shows
quote/history status, provider, cache coverage, freshness, stale or synthetic state, and matching
Recharts plus table values. Goal Planning submits editable scenarios to the deterministic M2
module and renders nominal and inflation-adjusted backend results with their assumptions.

TanStack Query owns server state and refresh. A locally persisted opaque Session identifier
restores the intended private-demo Session after refresh; authoritative product data remains in the
backend. Pages are code-split, responsive, keyboard navigable, and use table alternatives for every
chart. The Inspector is truthfully labeled as M7 work and does not render inferred or synthetic
execution as measured behavior.

The privacy-safe browser telemetry module reports navigation, Web Vitals, error-boundary state,
and API latency/failure categories to the first-party FastAPI collector. Product calls and their
telemetry signal share W3C trace identity and request correlation headers. The collector exports
only bounded page, route, status, category, metric-name, and rating attributes; prompts, portfolio
content, provider payloads, error text, and credentials have no telemetry fields. Transport failure
is swallowed and cannot change a product result. LangSmith and provider credentials remain
backend-only.

## Delivered interfaces

- `frontend/src/features/`: Assistant, Portfolio, Market, Goal, health, and explicit M7 Inspector
  boundary components.
- `frontend/src/lib/api.ts`: typed `/api/v1` client, W3C/request correlation, SSE recovery parser,
  safe failure mapping, and file-to-base64 transport.
- `frontend/src/lib/telemetry.ts`: first-party navigation, Web Vitals, API, and error-boundary
  telemetry with no arbitrary payload field.
- `backend/contracts/api.py` and `api/routes/v1.py`: bounded file-import transport and
  `POST /api/v1/telemetry/browser` collector.
- `contracts/m6-frontend-contract.v1.json`: required M6 paths and frontend type names checked
  against FastAPI OpenAPI.
- `frontend/e2e/m6.spec.ts`: deterministic desktop/mobile journeys, import correction, semantic
  accessibility, keyboard focus, CSP, provenance, and chart/table assertions.

## Acceptance and evidence

| Gate | Result |
| --- | --- |
| Four core workflows complete without developer tools | Passed in Chrome Playwright journeys |
| Manual/JSON/CSV/XLSX share validation and require explicit approval | Passed by transport and browser tests |
| No browser-side authoritative portfolio/goal calculation | Passed; charts and tables use returned resources |
| Provenance, freshness, coverage, assumptions, partial/failure labels | Implemented and contract-tested |
| Refresh/reconnect preserves Session intent and stable SSE cursor IDs | Passed by Session reload and SSE parser tests |
| Keyboard, semantics, contrast, and narrow layout | Passed; zero critical/serious Axe findings in reviewed states |
| W3C and request correlation reaches FastAPI | Passed by browser-header and backend observability tests |
| Telemetry contains no product payload and can fail safely | Passed by redaction, error-boundary, and failed-transport tests |
| CSP and local CORS posture | Passed by browser CSP assertion and existing M5 CORS tests |

The evidence index is [docs/evidence/m6/README.md](evidence/m6/README.md). It includes the browser
report, accessibility review, screenshots, contract record, telemetry sample, and correlation
record.

## Verification record

- Full backend gate — passed: 117 files formatted, Ruff clean, 109 source files type-checked, 167
  tests passed, 1 opt-in Qdrant test skipped, 3 opt-in live tests deselected, and 87% total coverage.
- Full frontend gate — passed: Prettier, ESLint, TypeScript, 9 Vitest tests, and the Vite production
  build. Route-level code splitting keeps the entry chunk at 274.16 kB (86.59 kB gzip).
- Chrome Playwright gate — passed: 2 user-journey/responsive tests using Chrome 156 and Playwright
  1.64.1. Four representative desktop states and one narrow state were captured.
- `make m6-check` — passed: all frontend gates, 109 backend files formatted, Ruff/mypy clean,
  12 focused M5/M6 API/contract tests, and 2 Chrome journeys.

No live provider, OpenAI, LangSmith, Qdrant, or external telemetry service was required or called.
The browser journey used deterministic API mocks; backend API/module correctness is independently
covered by the M5/M6 and full backend suites.

## Security and privacy impact

- Files remain untrusted: the browser only encodes bytes; backend size, type, schema, formula, and
  content checks remain authoritative. Validation findings are displayed without silent repair.
- The browser stores only an opaque local Session identifier. It ships no OpenAI, provider,
  LangSmith, Collector, or other secret and never sends a prompt or financial payload to telemetry.
- The CSP limits scripts, images, objects, base URLs, and connections to first-party loopback
  development endpoints. FastAPI retains its no-credentials, explicit-origin CORS policy.
- External links use a new browsing context without opener access. User-safe backend errors are
  rendered; raw exceptions are not.

## Limitations and unresolved decisions

- The private demo remains unauthenticated and loopback-only. Browser Session persistence is
  convenience, not identity, access control, encryption, or public multi-user readiness.
- Browser journeys use deterministic API mocks for repeatability. Full-stack browser-to-live-local
  API qualification, broader performance budgets, and adversarial UI evaluation remain M8 gates.
- Saved Portfolio and Run resources reload from FastAPI, with the latest response labeled separately
  from earlier Run history. Saved Goal Projection and market-query history resources are not M5
  persistence contracts.
- CSP is supplied as a document policy for the local Vite/static artifact. A production deployment
  must set and validate equivalent HTTP response headers and choose its final asset/CDN policy.
- Telemetry is a bounded first-party ingestion seam and local/backend signal path, not an approved
  production monitoring vendor, sampling policy, retention schedule, dashboard, or alerting setup.
- The Agent Execution Inspector remains M7. M6 does not claim a dynamic graph, measured timeline,
  or external trace viewer.

M6 satisfies its acceptance gate. M7 is the next permitted milestone.
