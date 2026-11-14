# App Platform repository layout

Status: authoritative; requirements-and-decisions slice complete

The project is organized as an extractable repository root. Canonical platform files remain under
`apps-platform/` while colocated so a later history-preserving subtree extraction can make this
directory the new repository root.

## Current layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | Platform engineering workflow and authority routing |
| `README.md` | Project overview, operational status, and local entry points |
| `GLOSSARY.md` | Canonical platform vocabulary |
| `docs/` | Platform design authority and future runbooks/evidence indexes |
| `prompts/` | Bounded task entry points that link to authoritative documents |
| `tests/` | Behavior-named deterministic platform checks |
| `Makefile` | Portable project-local developer and verification interface |
| `.gitignore` | Platform-local generated, secret, state, and build exclusions |

## Reserved capability locations

These locations may be created only by their approved slice:

| Path | Intended owner |
| --- | --- |
| `contracts/` | Versioned platform, registration, admission, catalogue, and migration interfaces |
| `infrastructure/terraform/` | Independent platform state roots and reusable infrastructure modules |
| `catalog/` | Root application catalogue implementation |
| `fixtures/` | Deterministic Registered Applications and app-owned test state used for qualification |
| `integrations/` | Inactive application-adoption inputs that cannot modify a consuming application |
| `artifacts/` | Secret-free generated or reviewed platform evidence |

The reservation is not authorization to scaffold empty modules or imply later capabilities.

## Colocation exceptions

The containing repository may have only temporary integration files outside this subtree:

- short authority-boundary notes in the parent `AGENTS.md`, `README.md`, documentation index, and
  repository-layout document; and
- a path-scoped GitHub Actions wrapper that delegates to `make -C apps-platform check`.

Those files are not App Platform authority and will not be included by subtree extraction. The
dedicated repository must recreate its own root workflow and repository settings.

## Extraction rules

- Do not create a nested `.git` directory while colocated.
- Keep canonical code, contracts, documentation, tests, prompts, and evidence inside this subtree.
- Use project-relative paths so `make check` works before and after extraction.
- Keep Terraform state, credentials, saved plans, caches, and authenticated artifacts outside Git.
- Record future root-wrapper and Workload Identity Federation recreation steps in the extraction
  runbook before migration to a dedicated repository.
- A path move is complete only when every contract consumer, test, command, document, and workflow
  resolves to the new location.
