# App Platform repository layout

Status: authoritative; AP-M6 runtime, repository-extraction procedure, and extraction-owned root
check recorded; no extraction, provider operation, or infrastructure implemented

The project is organized as an extractable repository root. Canonical platform files remain under
`apps-platform/` while colocated so a later history-preserving subtree extraction can make this
directory the new repository root.

## Current layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | Platform engineering workflow and authority routing |
| `.github/workflows/` | Credential-free dedicated-root checks; inert as workflows while this project remains a subtree |
| `README.md` | Project overview, operational status, and local entry points |
| `GLOSSARY.md` | Canonical platform vocabulary |
| `docs/` | Platform design authority and future runbooks/evidence indexes |
| `docs/runbooks/` | Subordinate operator procedures requiring their own explicit approvals |
| `prompts/` | Bounded task entry points that link to authoritative documents |
| `integrations/` | Inactive application-adoption inputs with no consuming-app authority |
| `contracts/` | Version 1 schemas, deterministic reference compiler, reviewed contract vectors, and bounded runtime JSON loading |
| `fixtures/` | In-process reference edge, synthetic identity, three independent Fixture Applications with app-owned test state, and reviewed registration generations |
| `edge/` | AP-M6 Shared Edge interface, immutable-generation source adapter, catalogue/routing, Google OIDC/sessions, admission, ES256 assertion/JWKS adapters, independent application verification, strict Cloud Run attachment resolution, bounded HTTP/SSE/WebSocket proxying, read-only status, minimized completion events, and accepted runtime behavior only |
| `tests/` | Behavior-named governance, contract, Fixture, and runtime checks plus explicitly synthetic fixed test material |
| `pyproject.toml` and `uv.lock` | Direct runtime dependencies and complete frozen transitive resolution |
| `Makefile` | Portable project-local developer and verification interface |
| `.gitignore` | Platform-local generated, secret, state, and build exclusions |

## Reserved capability locations

These locations may be created only by their approved slice:

| Path | Intended owner |
| --- | --- |
| `registrations/` | Future reviewed Live Registration Sets; Fixture registrations remain under `fixtures/` |
| `infrastructure/terraform/bootstrap/` | Future backend-bootstrap root only |
| `infrastructure/terraform/platform/` | Future Shared Edge Platform State root only |
| `infrastructure/terraform/fixtures/<application-id>/` | Future independently owned Fixture Application State root |
| `infrastructure/terraform/modules/` | Future reusable modules with no environment or state ownership of their own |
| `catalog/` | Root application catalogue implementation |
| `artifacts/` | Secret-free reviewed evidence indexes and digests, never raw Live evidence bundles |

The reservation is not authorization to scaffold empty modules or imply later capabilities. AP-M6
may extend only `edge/` and implementation-owned registration test inputs through its ordered work
packages. AP-M7 may create only the planned Terraform and workflow paths after AP-M6 merges. Live
evidence bundles remain in the private provider evidence store rather than the repository.

## Colocation exceptions

The containing repository may have only temporary integration files outside this subtree:

- short authority-boundary notes in the parent `AGENTS.md`, `README.md`, documentation index, and
  repository-layout document; and
- a path-scoped GitHub Actions wrapper that delegates to `make -C apps-platform check`.

Those files are not App Platform authority and will not be included by subtree extraction. The
canonical root workflow is stored inside this subtree and becomes active only when extraction makes
it repository-root `.github/workflows/check.yml`. Repository settings remain explicit operator
actions after the initial push.

## Extraction rules

- Do not create a nested `.git` directory while colocated.
- Keep canonical code, contracts, documentation, tests, prompts, and evidence inside this subtree.
- Use project-relative paths so `make check` works before and after extraction.
- Keep Terraform state, credentials, saved plans, caches, and authenticated artifacts outside Git.
- Follow the reviewed [repository extraction runbook](runbooks/repository_extraction.md) before any
  split, push, repository-setting change, authority cutover, or parent-tree removal.
- A path move is complete only when every contract consumer, test, command, document, and workflow
  resolves to the new location.
