# M6 delivery report — React product experiences

Date: 2026-10-29  
Status: Complete for the production-oriented private local demonstration  
Scope: PR-003–PR-013; QR-001–QR-007 and QR-009–QR-015; ADR-007, ADR-009,
ADR-011, ADR-012, ADR-014, ADR-015, ADR-018, ADR-019, ADR-023, ADR-027

## Outcome

M6 replaces the M0 placeholders with four core responsive React experiences plus Session History,
all backed by the M5 interfaces. The Assistant creates and reloads authoritative Runs, supports context-free public
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
backend. The workspace can clear its Active Session through an explicit archive confirmation.
Success preserves the Session as read-only history, removes its active browser identifier and query
state, returns to the Assistant, and opens a new empty Active Session. The History experience lists
Archived Sessions, loads their saved conversation, and exposes separately confirmed permanent
deletion. Failed archive or deletion preserves the affected Session and reports a safe error. Pages
are code-split, responsive, keyboard navigable, and use table alternatives for every chart. The
Inspector is truthfully labeled as M7 work and does not render inferred or synthetic execution as
measured behavior.

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
  Session list/archive/deletion, safe failure mapping, and file-to-base64 transport.
- `frontend/src/hooks/useSession.ts`: opaque local Active Session restoration, confirmed archive,
  Session-scoped cache eviction, and fresh-Session creation.
- `frontend/src/features/history/`: Archived Session list, read-only conversation history, and
  separately confirmed permanent deletion.
- `frontend/src/lib/telemetry.ts`: first-party navigation, Web Vitals, API, and error-boundary
  telemetry with no arbitrary payload field.
- `backend/contracts/api.py` and `api/routes/v1.py`: bounded file-import transport and
  `POST /api/v1/telemetry/browser` collector.
- `contracts/frontend/backend-consumption.v1.json`: required M6 paths and frontend type names checked
  against FastAPI OpenAPI.
- `frontend/e2e/product-experiences.spec.ts`: deterministic desktop/mobile journeys, import correction, semantic
  accessibility, keyboard focus, CSP, provenance, and chart/table assertions.
- `examples/portfolios/`: import-ready synthetic JSON, CSV, and XLSX files for validating the
  review, save, and backend Snapshot workflow without live provider calls.

## Acceptance and evidence

| Gate | Result |
| --- | --- |
| Four core workflows complete without developer tools | Passed in Chrome Playwright journeys |
| Manual/JSON/CSV/XLSX share validation and require explicit approval | Passed by transport and browser tests |
| Committed example files import and produce complete dashboard Snapshots | Passed by importer, checksum, and deterministic Portfolio-analysis tests |
| No browser-side authoritative portfolio/goal calculation | Passed; charts and tables use returned resources |
| Provenance, freshness, coverage, assumptions, partial/failure labels | Implemented and contract-tested |
| Refresh/reconnect preserves Session intent and stable SSE cursor IDs | Passed by Session reload and SSE parser tests |
| Clearing archives the Active Session, opens a fresh Session, and exposes read-only History | Passed by success/failure component tests and Chrome journey |
| Permanent deletion is limited to confirmed Archived Session actions | Passed by API lifecycle, component, and Chrome journey tests |
| Keyboard, semantics, contrast, and narrow layout | Passed; zero critical/serious Axe findings in reviewed states |
| W3C and request correlation reaches FastAPI | Passed by browser-header and backend observability tests |
| Telemetry contains no product payload and can fail safely | Passed by redaction, error-boundary, and failed-transport tests |
| CSP and local CORS posture | Passed by browser CSP assertion and existing M5 CORS tests |

The evidence index is [docs/evidence/m6/README.md](evidence/m6/README.md). It includes the browser
report, accessibility review, screenshots, contract record, telemetry sample, and correlation
record.

## Verification record

- Full backend gate — passed: 117 files formatted, Ruff clean, 109 source files type-checked, 169
  tests passed, 1 opt-in Qdrant test skipped, 3 opt-in live tests deselected, and 87% total coverage.
- Full frontend gate — passed: Prettier, ESLint, TypeScript, 13 Vitest tests, and the Vite production
  build. Route-level code splitting keeps the entry chunk at 279.35 kB (87.93 kB gzip).
- Chrome Playwright gate — passed: 3 user-journey/responsive tests using Chrome 156 and Playwright
  1.64.1. Seven representative desktop states and one narrow state were captured.
- `make m6-check` — passed: all frontend gates, 109 backend files formatted, Ruff/mypy clean,
  12 focused M5/M6 API/contract tests, and 3 Chrome journeys.

No live provider, OpenAI, LangSmith, Qdrant, or external telemetry service was required or called.
The browser journey used deterministic API mocks; backend API/module correctness is independently
covered by the M5/M6 and full backend suites.

Post-completion response-contract maintenance confirms that the Assistant renders a complete
1,399-character saved narrative in both latest-response and history positions without inventing a
generation warning. No frontend clipping behavior was required or added: the correction is in the
authoritative backend contracts and prompt policy. The current full offline gate passes 175 backend
tests with 87% coverage, 15 frontend tests, and the production build. Historical saved Runs remain
immutable; the corrected behavior applies to newly executed Runs.

A subsequent Assistant presentation correction removes three redundant render paths without
changing saved Run data: the Workflow summary is not repeated above existing agent summaries,
chunk-level references with the same canonical URL render as one source, and agent warnings are not
repeated from the Workflow aggregate. The public-component regression reproduces and verifies all
three behaviors. Prettier, ESLint, TypeScript, all 15 Vitest tests, the Vite production build, and
14 focused backend M5/M6 contract tests pass. The Playwright rerun started successfully but its
Portfolio and Market lazy imports received Vite `504 Outdated Optimize Dep` responses for Recharts;
the independent archive/history journey passed. That development-cache failure is recorded as an
environmental limitation rather than a successful browser result.

Run cards now place the submitted question in bold before the answer and render model narratives as
GitHub-flavored Markdown, including semantic emphasis, lists, and responsive tables whose cells wrap
so every column remains visible inside the card.
The renderer keeps raw HTML disabled and uses its safe URL transformation, so model output does not
enter React through `dangerouslySetInnerHTML`. New Runs expose the migration-backed
`request_message`; pre-migration Runs truthfully omit the question rather than fabricating one.

Responsive maintenance now constrains the Conversation grid, Run card, Agent answer, and Markdown
narrative to the available inline size. A subsequent UX correction removes table-level horizontal
scrolling: Markdown tables use fixed in-card columns, and long cell content wraps to expand rows.
The 390 px browser regression verifies that the document, card, table, and every cell remain within
the viewport without internal overflow. Prettier, ESLint, TypeScript, all 15 Vitest tests, the
production build, and the focused Chrome regression pass. In the latest complete Playwright attempt,
the focused Run-card and archive/history journeys passed; the Portfolio and Market journeys again
reached the error boundary after the Vite development server invalidated lazy Recharts dependencies,
so that pre-existing development-cache limitation remains separate from the responsive fix.

Sidebar maintenance keeps the owner-only local note and Clear Active Session action available during
long conversations. On desktop, the sidebar is constrained to the viewport below the sticky top bar,
and the local note stays pinned to its bottom; the narrow layout retains its fixed drawer behavior.
The browser regression uses a saved conversation taller than two viewports and verifies that the
Clear action is visible before scrolling and remains at the same viewport position after page scroll.

Run-card visual-rhythm maintenance adds explicit separation between the response metadata and the
agent-section divider, and a larger separation between each agent's citation list and first
supplemental warning or error. A browser fixture covering a legacy Run without a saved request
message verifies both gaps at the rendered interface.

Portfolio Dashboard warning maintenance now groups equivalent Holding-scoped Snapshot warnings by
code and message at the presentation boundary. The authoritative backend warning array remains
unchanged; one notice reports the affected-Holding count and exposes the individual Holding
identifiers in an expandable list, while portfolio-wide warnings retain a separate scope. The
focused regression first reproduced two duplicate cards, then passed with one grouped notice.
Prettier, ESLint, TypeScript, all 16 Vitest tests, the production build, and all 6 Chrome Playwright
journeys pass. A subsequent visual-rhythm correction scopes compact typography to these grouped
Snapshot warnings below the chart and table without reducing the prominence of import, deletion,
or failure notices.

Portfolio workflow hierarchy maintenance removes the implied mandatory Step 1/Step 2 sequence. The
full-width saved Portfolio library is now the primary view, and the unchanged manual/file validation
workflow opens only from an Import Portfolio action in a modal dialog. The dialog uses native modal
focus containment, starts on an explicit close control, supports Escape dismissal with focus return,
and closes after a successful save. A public-component regression verifies the on-demand form, and
the Chrome journey verifies dialog semantics, focus behavior, import correction, save, and the
resulting library. Prettier, ESLint, TypeScript, all 17 Vitest tests, the production build, Axe, and
all 6 Chrome Playwright journeys pass.

Saved Portfolio lifecycle maintenance adds a separately confirmed Delete action to each library
entry. Confirmation identifies the Portfolio and states that its imported records and saved
Snapshots are permanently removed from the Active Session; Cancel performs no mutation. Successful
deletion uses the authoritative M5 API, refreshes the library, removes a displayed Snapshot owned by
that Portfolio, and reports completion, while failures retain the confirmation with a safe error.
API and component regressions plus the Chrome journey cover confirmation, cancellation, deletion,
empty state, and Snapshot removal. Prettier, ESLint, TypeScript, all 19 Vitest tests, the production
build, and all 6 Chrome Playwright journeys pass.

Portfolio save and delete confirmations are transient accessible status messages with a shared
four-second lifetime. A new Portfolio action replaces any earlier confirmation, and component
unmount cancels the pending timer. The Chrome journey verifies that each message is initially
visible and disappears within the five-second acceptance window without changing the saved
Portfolio state.

Assistant portfolio-context maintenance connects the saved Portfolio library to the graph's typed
context requirement. The composer has no default selector and does not load saved Portfolios for an
ordinary question. After the classifier selects Portfolio Analysis, the context gate returns a
Portfolio-selection response when context is missing; only that Run renders the labeled selector.
An explicitly quoted label now skips that round trip only when trusted backend code finds one exact,
unique saved Portfolio in the active Session. Unquoted, absent, duplicate, multi-label, and
cross-Session cases retain the selector, while multiple Portfolios also offer an explicit
separate-comparison scope. Continuing creates a linked Run and removes the selection control from
the resolved clarification. The Portfolio agent preserves every distinct authorized context,
produces separate deterministic Snapshot facts, and instructs the model to name and report each
Portfolio without blending totals. Component, API, and workflow regressions cover direct unique
label resolution, conditional single/multiple selection behavior, and linked results.

Portfolio conversation-continuity maintenance keeps the selector response-driven while removing
repeat selection for ordinary follow-ups. Once a Portfolio Run establishes active scope, the fixed
composer displays a compact `Portfolio context` label resolved from the authorized saved-Portfolio
list. `Change Portfolio` opens a native modal dialog for one saved Portfolio or an explicit separate
comparison, leaving the fixed composer at its compact height. Cancel, Escape, or the close control
does not change pending context; confirmation stages the chosen opaque references for the next
message, after which the backend re-authorizes them before replacing checkpoint scope. The control
is absent before Portfolio scope exists. Archived/new Sessions get distinct component and
checkpoint state, and unavailable or deleted scope returns to the existing clarification flow. The
browser does not infer scope from message text or send Portfolio data to unrelated routes. The
fixed composer is inset from the viewport bottom with matching conversation clearance instead of
touching the page boundary.

Empty Portfolio-context maintenance keeps the backend's typed clarification result while making
the browser state truthful to the authorized saved-Portfolio list. While the list is loading, the
Run shows bounded progress text. When it resolves empty, the generic “Select a saved Portfolio”
summary and selection fieldset are suppressed and one import-then-ask-again message is shown.
Existing one-Portfolio and explicit comparison selectors are unchanged.

Portfolio-selector spacing maintenance replaces the browser-positioned native chevron in the
required-input control with an equivalent CSS background chevron inset from the right edge. Extra
right padding keeps option text clear of the control while preserving native keyboard and screen
reader selection semantics.

The focused component regression first reproduced both misleading selection elements, then passed
with the empty-state presentation. Prettier, ESLint, TypeScript, all 35 Vitest tests, and the
production build passed. The focused desktop-Chrome journey also passed and asserts that the import
message is visible while the generic prompt, fieldset legend, and saved-Portfolio selector are
absent. No live backend, model, provider, Qdrant, LangSmith, or external telemetry call was made.

Portfolio-context modal and composer-inset maintenance is covered by the same 35-test frontend gate
plus a focused desktop-Chrome journey. The component regression proves that selection is rendered
inside the named dialog and that confirmation stages the explicit replacement sent with the next
question. The browser journey verifies close-button focus, absence of the selector from the
composer, the staged context label, and at least 15 pixels of measured viewport-bottom clearance.

Goal Projection warning-presentation maintenance keeps the authoritative M2 result unchanged while
normalizing equivalent warning text at the React presentation boundary. Distinct limitations render
once in a compact, labeled list after the chart and its accessible table instead of as repeated
full-width notices before the visualization. The component regression covers case/whitespace
deduplication and document order. The focused desktop-Chrome journey verifies the rendered count,
chart-relative placement, compact font size, and Axe accessibility; frontend formatting, lint,
TypeScript, all 36 Vitest tests, and the production build also pass. No live service was called.

The same classifier maintenance rejects unrelated general knowledge such as weather or current
political-office questions with a bounded finance-scope response and no specialist Agent result.
The semantic decision remains in the structured model prompt; deterministic code validates the
closed decision schema, enforces context authorization, and selects graph edges without maintaining
a substring table.

Unique Portfolio-label and complete-coverage maintenance verification on 2026-10-31:

- `uv run pytest -q tests/test_workflow.py tests/test_agents.py tests/test_http_api.py
  tests/test_persistence.py` — 52 passed.
- `make backend-check` — formatting, Ruff, strict mypy, and coverage passed; 215 tests passed,
  1 opt-in Qdrant test skipped, 3 live tests deselected, and total measured coverage was 88%.
- `make frontend-check` — Prettier, ESLint, TypeScript, 32 Vitest tests, and the production build
  passed.
- The non-browser portion of `make m6-check` passed, including 19 focused M5/M6 contract and API
  tests. The local Playwright run passed 5 of 7 journeys; the two Portfolio/Market lazy-route
  journeys reached the existing Vite development error boundary before their headings rendered.
  A focused rerun reproduced those two unrelated lazy-module failures. No frontend implementation
  changed in this maintenance slice; the new user-visible routing behavior is covered through the
  real FastAPI/SQLite integration test rather than a mocked browser response.
- No live model, market-data, news, Qdrant, LangSmith, or external telemetry call was made.

Portfolio conversation-continuity verification on 2026-10-31:

- Full backend formatting, Ruff, strict mypy, and coverage gates passed: 220 tests passed, 1
  opt-in Qdrant test skipped, 3 live tests deselected, and total measured coverage was 88%.
- The focused Workflow/API/contract suite passed 38 tests, including checkpoint reuse, explicit
  replacement, replacement persistence, cross-Session isolation, invalid-reference fail-closed
  behavior, and non-disclosure to an unrelated specialist.
- Frontend Prettier, ESLint, TypeScript, all 34 Vitest tests, and the production build passed.
- The focused desktop-Chrome M6 product journey passed and verifies that active Portfolio scope is
  visible only after selection and that Change Portfolio opens its on-demand selector.
- No live model, provider, Qdrant, LangSmith, or external telemetry call was made.

## Security and privacy impact

- Files remain untrusted: the browser only encodes bytes; backend size, type, schema, formula, and
  content checks remain authoritative. Validation findings are displayed without silent repair.
- The browser stores only an opaque local Session identifier. It ships no OpenAI, provider,
  LangSmith, Collector, or other secret and never sends a prompt or financial payload to telemetry.
- Portfolio context remains an authorized, Session-scoped server lookup and is transported to the
  specialist as an opaque identifier. An explicitly quoted label is only a lookup hint: trusted
  backend code requires one exact unique match, never exposes or accepts the label as authorization,
  and fails closed to explicit selection for ambiguity or another Session.
- The browser resolves checkpoint-returned opaque identifiers through the authorized Portfolio
  list only for display. Explicit replacement identifiers are re-authorized server-side and are
  removed from non-Portfolio specialist requests.
- Confirmed Session clearing uses the authoritative M5 archive endpoint. It preserves Session-owned
  artifacts and checkpoint history as read-only, and failure retains the browser identifier and
  active UI state. Permanent deletion is a separate History action and uses the guarded M5 cascade.
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
- Archived Sessions remain subject to configured local retention; History is not an indefinite
  archive or a backup/export feature.
- CSP is supplied as a document policy for the local Vite/static artifact. A production deployment
  must set and validate equivalent HTTP response headers and choose its final asset/CDN policy.
- Telemetry is a bounded first-party ingestion seam and local/backend signal path, not an approved
  production monitoring vendor, sampling policy, retention schedule, dashboard, or alerting setup.
- The Agent Execution Inspector remains M7. M6 does not claim a dynamic graph, measured timeline,
  or external trace viewer.

M6 satisfies its acceptance gate. M7 is the next permitted milestone.
