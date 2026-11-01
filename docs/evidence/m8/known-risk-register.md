# M8 known-risk and production-hardening register

| ID | Risk / missing control | Impact and mitigation for private demo | Owner | Expiry / revisit |
|---|---|---|---|---|
| M8-R01 | No public identity provider or multi-user authorization | Blocks public/shared deployment; bind to loopback and restrict host access | Product owner | Before any shared/public deployment |
| M8-R02 | SQLite and local Qdrant lack managed encryption, backup, restore, HA, and tamper controls | Accept only disposable private-demo data; keep manual backups out of the repo | Product owner | 2026-11-30 |
| M8-R03 | External telemetry sampling/retention is deployment-owned, not enforced by app | Keep export optional and privacy-filtered; inspect vendor settings before enabling | Operator | Before enabling external export outside owner demo |
| M8-R04 | Provider display/retention rights are conditional or unverified | Use credential-free mode for reproducibility; do not represent live data as publicly redistributable | Product owner | Before shared demo or public release |
| M8-R05 | Semantic response-cache human false-hit review is incomplete | Keep `AIFA_RESPONSE_CACHE_SEMANTIC_MODE=shadow`; exact cache remains evidence/version scoped | Product owner | Before semantic serving |
| M8-R06 | Live-model citation, groundedness, and financial-safety M8 sample is pending | Blocks M8 release recommendation; credential-free tests remain regression evidence only | Product owner/reviewer | 2026-11-07 |
| M8-R07 | Frontend has no measured line/branch coverage report | Browser/component/build gates still run; add Vitest coverage before coursework packaging | Frontend owner | M9 packaging |
| M8-R08 | Soak scale is bounded local concurrency, not public load capacity | Stay within owner-demo scale; add public SLO/load model with managed infrastructure | Platform owner | Before public deployment |

No item in this table waives a critical M8 release gate. Critical pending reviews block the release
recommendation; public-production gaps block public deployment even after a private-demo decision.
