# M9 signed completion checklist

Release: `private-demo-2026-10-31`

- [x] M8 owner-approved report passes EVAL-01 through EVAL-18 with no critical failure/incomplete.
- [x] PR-001 through PR-015 and CA-01 through CA-13 map to existing evidence paths.
- [x] User, developer, operator, demo, source/license, version, release-note, and limitation pages exist.
- [x] Credential-free demo path uses synthetic data and zero external calls.
- [x] Live path has readiness checks, explicit provider selection, and request ceilings.
- [x] Four MCP tools are protocol-tested from in-memory and external stdio clients and are read-only.
- [x] Active collection, schema, policy, prompt, model, and container identifiers are recorded.
- [x] Observability disabled/export/LangSmith/privacy/retention/correlation guidance is documented.
- [x] Rollback boundaries and public-production blockers are documented.
- [x] Sample portfolio checksums and walkthrough are validated.
- [x] Backend/frontend coverage is measured without overstating the 90% target.
- [x] Final locked clean-start and `make m9-check` commands pass.

Implementation verification: Codex, 2026-10-31 — all listed technical checks passed.  
Product release authority: repository owner — M8 owner approval recorded 2026-10-31; scope remains
the same owner-only private demonstration.  
Public-production approval: **not granted**.
