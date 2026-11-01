# M8 known-risk and production-hardening register

| ID | Risk / missing control | Impact and mitigation for private demo | Owner | Expiry / revisit |
|---|---|---|---|---|
| M8-R01 | No public identity provider or multi-user authorization | Blocks public/shared deployment; bind to loopback and restrict host access | Product owner | Before any shared/public deployment |
| M8-R02 | SQLite and local Qdrant lack managed encryption, backup, restore, HA, and tamper controls | Accept only disposable private-demo data; keep manual backups out of the repo | Product owner | 2026-11-30 |
| M8-R03 | External telemetry sampling/retention is deployment-owned, not enforced by app | Keep export optional and privacy-filtered; inspect vendor settings before enabling | Operator | Before enabling external export outside owner demo |
| M8-R04 | Provider display/retention rights are conditional or unverified | Use credential-free mode for reproducibility; do not represent live data as publicly redistributable | Product owner | Before shared demo or public release |
| M8-R05 | Closed 2026-10-31: two frozen semantic-cache candidates were owner-approved | Serving remains evidence/version scoped and may be disabled independently | Product owner | Revisit on encoder/policy/dataset change |
| M8-R06 | Closed 2026-10-31: live-model review was owner-approved | Requalify on model/prompt/collection or safety-policy change | Product owner/reviewer | Version-change trigger |
| M8-R07 | Closed 2026-10-31: M9 added Vitest/V8 coverage | 80.25% lines meets only the transcribed fallback; statements/branches/functions remain lower and are reported separately | Frontend owner | Revisit before seeking the 90% tier |
| M8-R08 | Soak scale is bounded local concurrency, not public load capacity | Stay within owner-demo scale; add public SLO/load model with managed infrastructure | Platform owner | Before public deployment |

No item in this table waives a critical M8 release gate. The final M8 gate passes for the private
demo; public-production gaps continue to block public deployment.
