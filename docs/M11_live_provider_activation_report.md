# M11 live-provider activation report

## Scope and authority

This report records the owner-only live-provider implementation slice for M11 under PR-004,
PR-006, PR-014, and PR-017; QR-005, QR-007, QR-010–QR-012, QR-014, and QR-015; EVAL-17 and
EVAL-20; and accepted ADR-023–ADR-026 and ADR-030. It does not broaden IAP admission, viewer rights,
Massive redistribution rights, or public availability. The already-qualified deployment remains in
`credential_free` mode until the merged-main activation operator succeeds.

## Approved account and runtime boundary

- OpenAI uses the existing `openai_live` adapter with `gpt-6.1-sol`. The owner approved real
  application prompts, retrieved Finance/Tax context, and authorized Portfolio/Goal facts under the
  selected API project's current data-control and retention posture. Requests remain stateless with
  `store=False`; no vendor tool is enabled. The Run budget is ten model calls and the deadline is
  180 seconds.
- Massive uses Stocks Basic for the subscribing owner's personal use only. Viewer display,
  redistribution, and durable deployed provider caching are disabled. The selected application
  limits are five requests per operation and five requests per minute.
- Tavily uses Researcher with pay-as-you-go disabled. Only minimized public finance-news queries may
  leave the backend; personal Portfolio, Goal, transaction, tax, or raw prompt context is forbidden.
  The plan currently includes 1,000 credits per month; the application budget is five requests per
  Run and ten requests per minute. Only attributed links and bounded snippets are displayed, and no
  durable Tavily cache is enabled.
- The OpenAI API project must have a USD 20 monthly hard limit. This is an owner-attested provider-
  account control. The existing USD 100 GCP budget is separate, and the application has no approved
  monetary-cost calculator.
- Viewer admission and viewer live-provider use remain disabled. Credential-free mode remains the
  Terraform default and explicit rollback target.

The machine authority is `contracts/providers/live-mode.v1.json`. It intentionally introduces no
new application `AIFA_*` setting name and preserves the current OpenAI routing, specialist
generation, synthesis, and measured RunEvent token-usage behavior.

## Implementation

- `infrastructure/terraform/environments/staging/` conditionally owns three user-managed,
  `us-west1` Secret Manager resources and grants only the runtime service account access. Terraform
  never owns a provider-key payload.
- `infrastructure/terraform/environments/staging-workloads/` selects the complete live bundle,
  exact rights labels and budgets, and enabled positive numeric secret versions. Credential-free is
  the default, and no Alpha Vantage secret is deployed.
- `infrastructure/terraform/scripts/configure-live-providers.sh` is the reviewed human-in-the-loop
  activation/rollback wizard. The activation path confirms provider rights and the OpenAI spend
  control, creates metadata, sends the owner to Secret Manager for payload entry, applies the
  workload, rechecks private-origin and configuration controls, guides browser qualification, sets
  non-secret GitHub plan selectors, and writes secret-free evidence. The rollback path first moves
  the workload to credential-free mode, then removes the now-unused provider secrets.
- `make live-providers-staging-up` and `make live-providers-staging-down` are the operator entry
  points. Activation also requires both GitHub image selectors to resolve to the current merged-main
  SHA in Artifact Registry. The Terraform GitHub workflow consumes the same non-secret mode and
  numeric-version selectors, so later plans reproduce the active posture.
- Readiness now includes the model provider and fails when `openai_live` lacks a credential, terms
  approval, or request budget. It does not call the external provider from a health endpoint.

## Verification and evidence state

Repository verification covers Terraform formatting/validation, credential-free defaults,
conditional secret metadata and runtime-only access, numeric version pinning, exact live settings,
operator payload non-readback, rollback ordering, health behavior, and existing infrastructure
controls. Deterministic CI still uses fake adapters and requires no paid credential.

The implementation verification run completed with:

- `terraform fmt -check -recursive infrastructure/terraform` — passed;
- `terraform validate` in `bootstrap`, `shared`, `environments/staging`,
  `environments/staging-workloads`, and `environments/staging-edge` — all five passed;
- `bash -n infrastructure/terraform/scripts/*.sh` — passed;
- `cd backend && .venv/bin/ruff format --check . && .venv/bin/ruff check . &&
  .venv/bin/mypy` — 181 files formatted, lint passed, and 169 source files passed mypy;
- `cd backend && .venv/bin/pytest -q` — 467 passed, 8 skipped, and 4 deliberately deselected.

`shellcheck` was unavailable locally, so Bash syntax plus repository contract tests are the local
shell gates; the pinned GitHub workflows remain the authoritative remote security/CI qualification.

The live gate remains pending. A passing merged-main run must confirm the account usage tier and
provider-side USD 20 control, inject three keys through Secret Manager, pass readiness, observe
measured OpenAI usage, Massive live provenance, Tavily attribution, and direct-origin denial, and
write `backend/artifacts/providers/deployment/live-mode-<revision>.v1.json`. That record may contain
numeric secret versions and result labels, but no key, prompt, provider response, Portfolio value,
or browser authentication state.

## Security, privacy, and limitations

The change adds no credential to GitHub, Terraform variables/state, repository files, or ordinary
operator output. Provider secrets are disposable with the demo runtime and must be entered again
after clean recreation. The selected Massive plan is not evidence of Business, viewer-display, or
redistribution rights. OpenAI provider-side spend enforcement may not equal application-observed
token cost, and monetary cost remains unavailable in RunEvents. Live behavior, latency, quota, data
quality, and account entitlement are not qualified until the separate live run passes.
