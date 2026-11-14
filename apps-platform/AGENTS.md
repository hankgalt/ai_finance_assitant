# App Platform engineering instructions

These instructions govern work under `apps-platform/`. While this project is colocated, the parent
repository's security, source-control, and destructive-action guardrails also apply.

## Before modifying the platform

1. Read [docs/README.md](docs/README.md) completely and follow its task-specific reading order.
2. Read [GLOSSARY.md](GLOSSARY.md) for canonical platform terms and
   [docs/repository_layout.md](docs/repository_layout.md) before placing files.
3. Inspect `git status` and preserve unrelated changes.
4. State the platform slice and requirement, decision, and evaluation identifiers that own the
   change once those authorities exist. During the governance foundation, state that no product
   capability or live resource is being implemented.
5. Stop for direction when an authority is absent or the requested work would change an active
   application, cloud resource, DNS record, credential, or Terraform state outside the approved
   slice.

## Authority boundary

- App Platform documentation is authoritative only for this project.
- Parent Finance Assistant specifications do not define platform behavior.
- Application integration drafts are inactive inputs until the consuming application adopts them
  through its own requirements and release process.
- Keep canonical platform implementation, contracts, tests, prompts, and evidence inside this
  subtree so repository extraction preserves them.

## Verification

- Run `make check` from this directory or `make -C apps-platform check` from the parent repository.
- Keep `check` credential-free, deterministic, and non-mutating. Cloud plans, applies, DNS changes,
  identity changes, and live qualification require separate explicit operator targets.
- Store no credentials, Terraform state, saved plans, authenticated browser state, or unredacted
  external payloads in Git.
- Update each public contract and all of its consumers together. Record unimplemented behavior as
  planned rather than operational.
