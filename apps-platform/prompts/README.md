# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [Provider-runtime handoff](starting_prompt.md) starts a new chat from updated `main` after AP-M5
  merges. It loads the approved Contract, Fixture, and infrastructure-planning boundaries before
  proposing AP-M6 runtime authority and its remaining owner decisions.

The handoff prompt authorizes an AP-M6 proposal only. It requires owner approval before runtime
editing and does not authorize Terraform, a cloud or DNS mutation, identity configuration,
deployment, Application Adoption, or Live qualification.
