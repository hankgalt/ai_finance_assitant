# M8 delivery report — evaluation, security, observability, and reliability

Date: 2026-10-31  
Status: Automated qualification complete; private-demo release review pending  
Scope: QR-001 through QR-015; EVAL-01 through EVAL-18; ADR-011, ADR-012, ADR-019,
ADR-028

## Outcome

M8 adds a strict, versioned qualification manifest and fixed command runner covering every
evaluation dimension. The runner accepts no commands from data, rejects repository path traversal,
strips live provider/model/tracing environment variables, uses `.test.env`, captures bounded
redacted output, and produces a machine-readable report. Core and full profiles distinguish
credential-free checks from browser and local Qdrant/Redis integrations.

The full automated candidate passes with zero critical automated failures: 264 backend tests,
35 frontend tests, nine Chrome journeys, one real-Qdrant test, and one real-Redis/RedisVL test.
Backend coverage is 87.39%. Production dependency scans are clean after updating the locked
`pypdf` from 6.21.3 to 6.21.4 to remediate three denial-of-service advisories.

M8 also closes an observability defect found during review: response-cache RunEvents and metrics
were creating bounded outcome/policy/match fields that the central allow-lists then dropped. The
allow-lists now retain only the intended bounded cache dimensions; raw query, Session/Run
identifiers, cached answers, and unbounded reasons remain excluded. New tests cover 128 concurrent
RunEvents, 128 unique synthetic Sessions collapsing to one metric dimension set, and a sensitive
telemetry canary.

The automated run does not constitute final M8 acceptance. Six dimensions intentionally remain
`review_required`: live semantic routing, live conditional synthesis, sampled claim/citation
support, groundedness, financial safety, and selected-model latency/cost. The current live
routing/synthesis operation was added after historical M4.1 qualification and needs a new explicit
external-call budget. No external model/provider call was made during M8, and historical approval
was not reused. Semantic response-cache mode remains `shadow` because the two proposed semantic
hits also await human review.

## Delivered artifacts

- `backend/data/evaluation/m8_cases.v1.json`: EVAL-01–EVAL-18 case/check/evidence manifest.
- `backend/data/evaluation/security_cases.v1.json`: prompt-injection, safe-file, isolation,
  redaction, cardinality, and outage vectors.
- `ai_finance_assistant.evaluation`: strict models, fixed runner, safe test environment, dimension
  reconciliation, and release-gate report.
- `backend/artifacts/m8/`: JUnit, coverage, environment, dependency, core, and full reports.
- `docs/evidence/m8/`: threat model, observability flow, signal inventory, operational runbook,
  coverage, benchmark/cost, dependency, correlation/redaction/exporter, review worksheet,
  known-risk register, qualification summary, and release recommendation.
- `make m8-check`: repeatable full-profile entry point.

## Verification record

The final full runner executed:

```text
backend/.venv/bin/python -m ai_finance_assistant.evaluation.runner \
  --manifest backend/data/evaluation/m8_cases.v1.json \
  --repo-root . \
  --output backend/artifacts/m8/qualification-report.v1.json \
  --profile full
```

Automated check results in the final reconciled report:

- Ruff format/check: passed; strict mypy: 132 source files passed.
- Backend: 264 passed, 1 skipped, 4 deselected in 15.24 seconds.
- Backend coverage: 6,501/7,439 statements, 87.39%.
- Frontend: 8 files/35 Vitest tests passed; Prettier, ESLint, TypeScript, build passed.
- Playwright Chrome: 9 passed in 25.0 seconds.
- Qdrant integration: 1 passed; Redis integration: 1 passed.
- Critical automated failures: zero.

Reconciliation reports no automated failures and six critical incomplete/review dimensions until
review approval is recorded. The runner exits nonzero by design while any critical review remains
open.

The M8 browser run initially failed because Playwright reused a separate long-running Vite server
on port 5173 with stale optimized Recharts dependencies (`504 Outdated Optimize Dep`). A minimized
two-journey loop reproduced the error. Playwright now owns strict port 4173, does not reuse a
developer server, and starts Vite with `--force`; the loop passed 2/2 and the full suite passed 9/9.

Dependency commands and results:

- `pnpm audit --prod --json` — 165 production/optional dependencies, zero findings.
- exact-pin `pip-audit` — initially three pypdf findings; `uv lock --upgrade-package pypdf` updated
  6.21.3 → 6.21.4; repeat scan reported no known vulnerabilities.

## Security, privacy, and observability impact

No credential, prompt, response, financial record, raw provider payload, or live cache value is
stored in M8 artifacts. The runner removes `AIFA_*`, `OPENAI_*`, `LANGCHAIN_*`, and `LANGSMITH_*`
variables before subprocesses and uses only explicit local integration URLs for Qdrant and Redis.
RunEvent persistence stays authoritative. Collector/LangSmith failure remains isolated from product
state, and missing telemetry is represented as unavailable rather than inferred.

The threat review remains scoped to the owner-only private demo. It does not add public identity,
multi-user authorization, managed encryption/backup, audited external retention, distributed
quotas, WAF, or approved public provider rights.

## Limitations and next decision

The owner must explicitly approve a new live-model request budget and then adjudicate the worksheet
before M8 can recommend the private-demo release. One all-six path can require eight calls (router,
six specialists, synthesis); a defensible review sample may require a separately agreed budget.
The review must record model/prompt/collection versions, claims/citations, safety decisions,
latency, token availability, and cost method. Until then:

- M8 is not marked complete;
- semantic response-cache mode stays `shadow`;
- the private-demo release is not recommended;
- public deployment remains blocked by the production-hardening register.
