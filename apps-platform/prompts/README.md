# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [Terraform-and-workflow handoff](starting_prompt.md) starts a new chat from updated `main` after
  AP-M6 merges. It loads the approved Contract, Fixture, planning, and local-runtime boundaries
  before proposing detailed AP-M7 implementation and evaluation authority.

The handoff prompt authorizes an AP-M7 proposal only. It requires owner approval and complete AP-M7
plan and evaluation authority before Terraform or workflow editing. It does not authorize backend
initialization, an authenticated plan or apply, a cloud or DNS mutation, identity configuration,
repository-setting changes, deployment, Application Adoption, or Live qualification.
