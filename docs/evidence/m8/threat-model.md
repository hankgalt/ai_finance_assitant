# M8 privacy and security threat review

Date: 2026-10-31 | Scope: private, owner-only demonstration release

## Protected assets and boundaries

Protected assets are credentials, hidden prompts, uploaded financial data, normalized holdings,
conversation/checkpoint state, saved Portfolios, RunEvents, trace correlation identifiers, and
provider entitlements. Trust boundaries are browser → FastAPI, FastAPI → SQLite/Qdrant/Redis,
workflow → model/provider adapters, and OpenTelemetry/LangSmith export. User text, files,
retrieved passages, news, and provider payloads are untrusted data and never grant authority.

## Material threats and enforced controls

| Threat | Control seam | Verification |
|---|---|---|
| Prompt or retrieved-content instruction injection | Structured router/model outputs, typed evidence, fixed six-agent graph, tool allow-list | Frozen security cases plus agent/workflow/provider tests |
| CSV formula or XLSX active content | Byte/row/column limits, formula rejection, safe ZIP member policy, no uploaded bytes persisted | Portfolio-import adversarial suite |
| Guessed Session/Run/Portfolio identifier | Every read/write is scoped by owning Session; local mode is not represented as public authentication | API and persistence isolation tests |
| Cross-Session response reuse | Opaque server-derived Session cache scope; no raw Session identifier stored | in-memory and real-Redis cache tests |
| Credential or financial-data telemetry leak | Explicit metadata allow-lists, text redaction, hidden LangSmith inputs/outputs | synthetic sensitive-field canaries and redaction tests |
| Cache false hit or stale-evidence reuse | Finance/Tax-only eligibility, exact evidence/version signature, Tax partition, semantic cutoff, shadow default | frozen exact/paraphrase/near-miss/adversarial calibration |
| Provider payload confusion or stale-as-live result | Schema validation, provider/policy-scoped persistence, provenance/freshness in contracts | provider fixture and durable-cache tests |
| Exporter/Collector outage corrupts product state | failure-isolating observability wrapper; RunEvent persistence is authoritative | failing-exporter workflow test |
| Resource exhaustion | import limits, bounded deadlines/hops/retries, SSE replay bound, provider/model request budgets | configuration validation and bounded concurrency tests |

## Residual deployment risks

There is no public identity provider, multi-user authorization layer, encrypted managed database,
central secret manager, audited backup/restore, WAF, distributed quota coordination, or approved
public retention policy. These are production-hardening requirements, not features of the private
demo. Provider retention/display rights remain conditional as recorded in the provider policy.
See the known-risk register for owners and expiry dates.
