# M11 private-edge implementation report

Status: repository qualified; reviewed live cutover pending | 2026-11-12

## Scope and authority

This report records the private-edge implementation slice for M11 under PR-017; QR-003, QR-005,
QR-007, QR-010, QR-014, and QR-015; EVAL-19 and EVAL-20; accepted ADR-019 and ADR-029; and proposed
ADR-030. It does not claim that a live load balancer, certificate, OAuth client, IAP policy, or DNS
record exists. Provider mode remains `credential_free`; this slice grants no provider usage,
display, caching, or redistribution rights.

## Implemented boundary

- `infrastructure/terraform/modules/private_edge/` defines two serverless network endpoint groups,
  separate IAP-enabled frontend and backend services, exact `/finance_assistant` and API routes, a
  global external managed HTTPS load balancer, Google-managed certificate, HTTP redirect, static
  IPv4 address, owner-only IAP bindings, and IAP-service-agent-only Cloud Run invocation. The API
  rules remove only the public `/finance_assistant` prefix so the origin retains its `/api` route;
  frontend routes are not rewritten.
- `infrastructure/terraform/environments/staging-edge/` owns only the staging edge state. Its
  backend service's generated numeric ID is exported as the FastAPI signed-IAP audience.
- The staging workload root accepts only a numeric backend-service audience or the documented
  pre-edge sentinel. The sentinel is intentionally invalid and therefore fail-closed.
- The persistent shared root owns only the regional OAuth secret container and grants the staging
  deploy identity secret-version access. The edge root consumes a positive numeric version through
  Terraform's ephemeral secret-version data and write-only IAP field. No secret payload is an
  ordinary input or durable Terraform value.
- `.github/workflows/terraform.yml` validates the edge root and produces an edge plan only when the
  non-secret OAuth client ID and numeric secret version are configured in the protected staging
  environment. It never applies infrastructure and never accepts the OAuth secret payload.
- `configure-private-edge.sh`, with `private-edge-up.sh` and `private-edge-down.sh` entry points,
  provides the reviewed operator boundary for the human-only OAuth and Squarespace steps. Up applies
  the edge before DNS, derives and propagates the audience, and verifies the assembled boundary.
  Down removes DNS first, restores the fail-closed audience, and destroys only the edge state.

## Repository qualification

The capability-owned tests assert exact routes and API prefix translation, TLS redirect, disabled CDN, owner-only IAP policy,
IAP-only invocation, generated audience propagation, secret-safe Terraform and workflow behavior,
edge-before-DNS order, direct-origin checks, and edge-only teardown. Terraform formatting and
validation cover the new module/root and the changed shared/workload roots. Shell syntax and, when
available, ShellCheck cover all three operator entry points. Exact commands and results are reported
with the change handoff rather than copied here as timeless claims.

## Security and privacy impact

The design removes browser-to-workload access: Cloud Run keeps internal-and-load-balancer ingress,
disabled default URLs, no anonymous invoker, and only the IAP service agent as invoker. IAP provides
edge admission, while FastAPI still validates the signed assertion and authorizes every resource by
immutable Application Principal. Email remains admission/display metadata, never ownership. The
only initial IAP member is `vtalwar.w@comfforts.com`; viewer admission stays disabled. The OAuth
secret and all credentials are excluded from repository files, saved plans, state, workflows, and
qualification evidence.

## Live acceptance still required

The first reviewed live apply created only the dependency-safe subset of edge resources before
Google rejected both backend services because the configuration set `timeoutSec` on serverless NEG
backends. It stopped before the workload audience or DNS changed. The correction removes only that
unsupported backend-service field; Google supplies the non-configurable serverless timeout. The
existing OAuth client, enabled Secret Manager version, partial Terraform state, private workloads,
and fail-closed application audience are retained so a corrected rerun can reconcile in place.

The owner must run the reviewed up procedure from clean merged `main`, create the external OAuth
client, enter its secret directly in Google Secret Manager, approve the displayed Terraform plans,
and add the exact A record only after the address exists. Acceptance then requires:

1. the Google-managed certificate to become active and HTTP to redirect to HTTPS;
2. anonymous access, unsigned identity, wrong audience, and direct Cloud Run origin access to fail;
3. the owner to complete IAP login and the application to report the expected Principal and role;
4. unmatched paths to fail closed and exact frontend/API base paths to route correctly;
5. applied edge and workload plans to be drift-free; and
6. EVAL-19/EVAL-20 deployed identity-isolation and feature-parity journeys to pass.

Only after those checks may ADR-030 be considered for acceptance and the protected URL be described
as an operational private-demo MVP. Viewer enablement, live providers, backup/recovery, HA,
capacity/soak, formal SLOs, incident response, and production readiness remain outside this slice.

## Artifact paths

- Machine contract: `contracts/deployment/private-edge.v1.json`
- Infrastructure policy: `contracts/deployment/infrastructure-policy.v1.json`
- Terraform root: `infrastructure/terraform/environments/staging-edge/`
- Terraform module: `infrastructure/terraform/modules/private_edge/`
- Operator procedures: `infrastructure/terraform/scripts/private-edge-up.sh`,
  `infrastructure/terraform/scripts/private-edge-down.sh`, and
  `infrastructure/terraform/scripts/configure-private-edge.sh`
- Tests: `backend/tests/test_private_edge.py` and
  `backend/tests/test_staging_infrastructure.py`
- Future live evidence: `backend/artifacts/release/deployment/private-edge-<revision>.v1.json`
