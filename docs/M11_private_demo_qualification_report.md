# M11 private-demo qualification report

Status: qualified owner-only credential-free private-demo MVP | 2026-11-12

## Scope and authority

This report records the final assembled private-demo qualification slice for M11 under PR-017;
QR-003, QR-005, QR-007, QR-010, QR-013, QR-014, and QR-015; EVAL-19 and EVAL-20;
accepted ADR-019, ADR-029, and ADR-030. It qualifies only the owner-operated deployment
at `https://apps.comfforts.com/finance_assistant` in `credential_free` provider and model modes.
It does not enable viewers, live providers, broader provider rights, or production-hardening claims.

## Implemented qualification boundary

- `contracts/deployment/private-demo-qualification.v1.json` defines the exact owner, target,
  provider boundary, prerequisite evidence, live product journeys, synthetic-data cleanup, deferred
  hardening work, and revision-scoped evidence path.
- `infrastructure/terraform/scripts/qualify-private-demo.sh` is the reviewed operator entry point.
  From clean merged `main`, it performs read-only checks of the deployed image digests, private Cloud
  Run origins, IAP-only invocation, owner-only edge admission, active certificate, and
  `credential_free` workload configuration. It makes no infrastructure, IAM, DNS, secret, or
  provider-mode change.
- `frontend/playwright.deployment.config.ts` runs one headed Chrome worker against the public HTTPS
  origin without a development web server. The operator completes Google/IAP authentication in the
  temporary browser context; the repository never receives a password, MFA code, cookie, token, or
  persistent authentication state. Playwright tracing is disabled to avoid retaining authenticated
  request metadata, and screenshots are disabled to avoid retaining identity or application data.
- `frontend/e2e/deployment/private-demo.spec.ts` verifies the owner IAP identity, managed readiness,
  active Finance/Tax aliases, Assistant execution and SSE replay, Portfolio import and Snapshot,
  credential-free Market provenance, Goal projection, History archive/view/delete, Inspector event
  reconciliation and reconnect, and serious/critical accessibility findings on critical views.
  It uses the repository's safe synthetic Portfolio fixture and deletes only Sessions created by the
  qualification before a passing result.
- The default Playwright suite excludes `e2e/deployment/`, so CI and local deterministic tests never
  contact the live deployment or wait for human authentication. `make qualify-private-demo` is the
  explicit live entry point.

## Evidence and acceptance semantics

The live run aggregates and hashes the already-qualified runtime lifecycle, application workload,
shared-knowledge release, Qdrant runtime-key rotation, and private-edge evidence. A successful run
writes only
`backend/artifacts/release/deployment/private-demo-<merged-main-revision>.v1.json`. The record
contains the deployed image references, result labels, limitations, and prerequisite evidence
hashes; it contains no application values, imported positions, prompts, responses, secret payloads,
tokens, cookies, or browser authentication state.

The operator ran `make qualify-private-demo` from clean merged `main` revision
`e66751dc36ed1cd342b0480248ce772c64896834`. The owner completed IAP authentication; every contracted
journey and final boundary readback passed; qualification-created Sessions were removed; and the
generated record contains no secret payload, browser authentication state, or application values.
EVAL-20's private-demo horizon is therefore qualified and ADR-030 is Accepted for this bounded MVP.

## Security, privacy, and limitations

The qualification rechecks the deployed boundary but does not replace the complete deterministic
two-Principal negative matrix in EVAL-19. That matrix remains prerequisite evidence because viewer
admission is intentionally disabled for this owner-only run. The live journey creates no provider
credential and calls no live OpenAI, market, or news provider. Backup/PITR, HA, disaster recovery,
load/soak, formal SLO/alert and incident rehearsals, full rollback qualification, viewer admission,
and authenticated public-member access remain deferred. Acceptance is not a production-readiness,
general-public-access, viewer-admission, or live-provider-rights claim.

## Artifact paths

- Machine contract: `contracts/deployment/private-demo-qualification.v1.json`
- Operator entry point: `infrastructure/terraform/scripts/qualify-private-demo.sh`
- Browser configuration: `frontend/playwright.deployment.config.ts`
- Browser journey: `frontend/e2e/deployment/private-demo.spec.ts`
- Contract tests: `backend/tests/test_private_demo_qualification.py`
- Qualified live evidence:
  `backend/artifacts/release/deployment/private-demo-e66751dc36ed1cd342b0480248ce772c64896834.v1.json`
