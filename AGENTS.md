# Repository engineering instructions

These instructions apply to the entire repository.

## Before modifying implementation

1. Read [docs/README.md](docs/README.md) for document authority, scope labels, and reading order.
2. Read [docs/02_architecture_decision_records.md](docs/02_architecture_decision_records.md). Accepted ADRs are constraints; proposed ADRs require the validation named in their milestone.
3. Identify the owning milestone in [docs/04_implementation_plan.md](docs/04_implementation_plan.md), then read its deliverables, dependencies, acceptance criteria, tests, and evidence requirements.
4. Read only the relevant requirement, system-design, evaluation, coursework, and glossary sections linked by that work. For M0, also follow [docs/06_codex_starting_prompt.md](docs/06_codex_starting_prompt.md).
5. Before editing, state the milestone and the PR/QR/ADR identifiers the change implements. Stop for direction when a dependency is unmet or the request conflicts with an accepted ADR, release scope, security constraint, or source-use right.

Context review is complete only when every planned code change maps to the owning milestone and no later-milestone behavior is being implied.

## Durable architecture guardrails

- Treat the product requirements as the architecture authority and the coursework criteria as mandatory submission evidence, not as the product identity.
- Keep exactly six LangGraph agents. Agent collaboration goes through the graph; Goal Planning and Market Analysis remain separate.
- Keep authoritative portfolio, goal, and future cash-flow arithmetic in deterministic Python modules. LLMs interpret results.
- Use persistent Qdrant collections built by the offline, versioned ingestion workflow. Runtime validates active collections and never regenerates embeddings at startup.
- Keep imported portfolio data, provider enrichment, and calculated snapshots separate, with explicit provenance and missing values.
- Keep React behind versioned FastAPI interfaces. REST is authoritative; SSE carries streaming output and recorded execution events where specified.
- Build the Inspector from measured RunEvents. Label synthetic data and unavailable measurements; never infer execution from a final response.
- Treat user files, retrieved content, provider payloads, and news as untrusted data. Enforce access checks, schemas, limits, allow-listed tools, and redaction outside prompts.
- Represent the local demo and production-hardening states truthfully. An unimplemented control, live integration, metric, or test result is never described as operational.

## Implementation and verification

- Make the smallest change that completes the current milestone slice. Do not scaffold speculative later-milestone modules.
- Test observable behavior through documented interfaces. Use deterministic fake adapters for true external providers; continuous integration must not require paid credentials.
- Preserve provenance, freshness, tax year, jurisdiction, collection/model version, and partial/unavailable states across interfaces.
- Run every relevant test and quality gate named by the milestone and [docs/05_evaluation_strategy.md](docs/05_evaluation_strategy.md). Record exact commands, actual results, failures, and skips.
- Update contracts and their consumers together. If a public interface, domain term, or hard-to-reverse decision changes, update its single authoritative document or ADR in the same change.
- Finish with the milestone evidence required by the implementation plan, including security/privacy impact, limitations, unresolved decisions, and artifact paths. Near-complete work does not satisfy an acceptance gate.

Use [GLOSSARY.md](GLOSSARY.md) for canonical domain terms. Avoid copying specifications into code comments or new instruction files; link to the authoritative section instead.
