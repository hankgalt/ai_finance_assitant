# App Platform engineering instructions

These instructions govern work under `apps-platform/`. While this project is colocated, the parent
repository's security, source-control, and destructive-action guardrails also apply.

## Before modifying the platform

1. Read [docs/README.md](docs/README.md) completely and follow its task-specific reading order.
2. Read [product requirements](docs/01_product_requirements.md) and
   [accepted architecture decisions](docs/02_architecture_decision_records.md). Map every planned
   behavior to their identifiers and constraints.
3. Read [GLOSSARY.md](GLOSSARY.md) for canonical platform terms and
   [docs/repository_layout.md](docs/repository_layout.md) before placing files.
4. Inspect `git status` and preserve unrelated changes.
5. State the platform slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, plan, and evaluation identifier
   that owns the change. Treat an absent downstream authority as unresolved rather than inferred.
6. Stop for direction when an authority is absent or the requested work would change an active
   application, cloud resource, DNS record, credential, or Terraform state outside the approved
   slice.

## Authority boundary

- App Platform documentation is authoritative only for this project.
- Parent Finance Assistant specifications do not define platform behavior.
- Application integration drafts are inactive inputs until the consuming application adopts them
  through its own requirements and release process.
- Keep canonical platform implementation, contracts, tests, prompts, and evidence inside this
  subtree so repository extraction preserves them.

## Branch and review workflow

- Start each approved slice from an updated, clean `main` on a dedicated feature branch.
- Keep one bounded slice per pull request. Merge it before starting the next documented slice.
- Use small coherent commits that remain independently reviewable. When the owner requests
  commit-by-commit review, leave each change uncommitted until approval.
- Keep later-slice implementation out of the current branch even when its directories or interfaces
  are already reserved.
- Run `make check` before handoff and report the actual result. A merged pull request records
  repository progress; it does not by itself qualify runtime or cloud behavior.
- Follow the completed/next sequence in [docs/README.md](docs/README.md); do not infer a new sequence
  from branch names or discussion history.

## Verification

- Run `make check` from this directory or `make -C apps-platform check` from the parent repository.
- Keep `check` credential-free, deterministic, and non-mutating. Cloud plans, applies, DNS changes,
  identity changes, and live qualification require separate explicit operator targets.
- Store no credentials, Terraform state, saved plans, authenticated browser state, or unredacted
  external payloads in Git.
- Update each public contract and all of its consumers together. Record unimplemented behavior as
  planned rather than operational.
