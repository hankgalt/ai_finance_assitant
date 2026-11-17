# Repository extraction runbook

Status: approved preparation procedure; no extraction, push, repository-setting change, authority
cutover, or parent-tree removal has occurred

This runbook moves the separately governed App Platform tree into its dedicated GitHub repository
without flattening its history, importing Finance Assistant authority, or creating two active
platform authorities. It implements the extraction boundary in AP-PR-008, AP-PR-009, AP-QR-003,
AP-QR-004, AP-QR-006, ADR-004, ADR-007, AP-TM-010, AP-TM-011, and AP-TM-014.

## Fixed repository identities

| Role | Repository |
| --- | --- |
| Current containing repository | `https://github.com/hankgalt/ai_finance_assitant.git` |
| Dedicated target repository | `https://github.com/comfforts/apps-platform.git` |
| Target visibility | Public |
| Target default branch | `main` |
| Extracted source prefix | `apps-platform/` |

The target owner and repository name are future Workload Identity Federation inputs. Renaming or
transferring the target after federation exists requires a separately reviewed identity change.

## Authority and mutation checkpoints

The Platform Owner must approve these checkpoints separately:

1. the source revision and dry-run extraction;
2. the exact initial push to the still-empty target repository;
3. dedicated-repository settings and required checks;
4. the dedicated-repository reconciliation pull request and canonical-authority cutover; and
5. any later removal or replacement of the colocated tree and containing-repository CI wrapper.

Approval of one checkpoint does not authorize the next. This runbook never authorizes a force push,
history replacement, target deletion, parent-tree deletion, cloud credential, Workload Identity
Federation binding, Terraform operation, DNS change, deployment, or Application Adoption.

## Preconditions

Before selecting the source revision, verify all of the following:

- the extraction-preparation pull request is merged to the containing repository's `main`;
- local `main` is clean and equals `origin/main`;
- the target repository exists, has the fixed identity above, and `git ls-remote` reports no branch,
  tag, or other ref;
- the App Platform owns a root-relative `.github/workflows/check.yml` inside `apps-platform/` so it
  becomes the dedicated repository's workflow without copying the containing wrapper;
- `uv.lock` is unchanged by `uv lock --check`, and `make -C apps-platform check` passes from the
  containing repository;
- the operator records the Git, uv, and Python versions used for extraction; and
- no credential value, credential-bearing URL, state, plan, browser artifact, or provider response
  is written to a command, log, runbook, commit, or evidence record.

If the target contains any ref or the source is not clean and current, stop. Do not merge histories,
pull the target into the source, overwrite the target, or infer that an existing target commit is
safe.

## Dry-run history-preserving split

Run the dry run in a new disposable directory, never in the owner's working clone. Use the exact
merged source revision rather than a moving branch name. The setup action may synchronize the frozen
Python environment; the default verification command remains credential-free and network-free.

The operator substitutes the reviewed 40-character source revision for `<source-revision>`:

```bash
extraction_workspace="$(mktemp -d)"
git clone --no-local https://github.com/hankgalt/ai_finance_assitant.git \
  "$extraction_workspace/source"
git -C "$extraction_workspace/source" checkout --detach <source-revision>
split_revision="$(git -C "$extraction_workspace/source" subtree split \
  --prefix=apps-platform <source-revision>)"
git -C "$extraction_workspace/source" branch apps-platform-extracted "$split_revision"
git clone --no-local --single-branch --branch apps-platform-extracted \
  "$extraction_workspace/source" "$extraction_workspace/extracted"
```

Record `source_revision` and `split_revision`. A split commit has a rewritten identifier by design;
its root tree must be byte-identical to the source revision's `apps-platform/` tree:

```bash
source_tree="$(git -C "$extraction_workspace/source" \
  rev-parse '<source-revision>:apps-platform')"
split_tree="$(git -C "$extraction_workspace/source" \
  rev-parse "$split_revision^{tree}")"
test "$source_tree" = "$split_tree"
repeat_split="$(git -C "$extraction_workspace/source" subtree split \
  --prefix=apps-platform <source-revision>)"
test "$repeat_split" = "$split_revision"
```

The extracted root must contain `AGENTS.md`, `README.md`, `Makefile`, `uv.lock`, `.github/workflows/`
and the canonical `contracts/`, `fixtures/`, `edge/`, `docs/`, `prompts/`, `tests/`, and inactive
`integrations/` packages. It must not contain an `apps-platform/` wrapper directory, Finance
Assistant implementation, containing-repository workflow, Terraform state, saved plan, credential,
or authenticated artifact.

Verify the frozen environment and complete gate from the extracted root:

```bash
uv sync --project "$extraction_workspace/extracted" --frozen --python 3.12
uv --project "$extraction_workspace/extracted" lock --check
make -C "$extraction_workspace/extracted" check
git -C "$extraction_workspace/extracted" status --porcelain
```

The gate must report zero failures, errors, unexpected warnings, or mandatory skips, and the final
status command must produce no output. Review the extracted log for the governance, requirements,
system-design/contracts, Fixture, infrastructure-planning, provider-runtime, and extraction-
preparation commits. Missing history, a tree mismatch, a changed lock, a dirty tree, or any failed
check stops the procedure before a push.

## Initial push

The initial push is an external repository mutation and requires a new explicit owner approval after
the dry-run evidence is reviewed. Immediately before pushing, verify again that the target has no
refs. Add it only in the disposable clone and push the exact recorded split commit without force:

```bash
git -C "$extraction_workspace/source" remote add extraction-target \
  https://github.com/comfforts/apps-platform.git
git -C "$extraction_workspace/source" ls-remote extraction-target
git -C "$extraction_workspace/source" push extraction-target \
  "$split_revision:refs/heads/main"
git -C "$extraction_workspace/source" ls-remote extraction-target refs/heads/main
```

The first `ls-remote` must be empty. The final remote `main` identifier must equal `split_revision`.
Do not push another branch or tag, and do not use `--force`, `--mirror`, or a wildcard refspec.

Clone the public target into a second disposable directory, synchronize only the frozen environment,
run `make check` from its root, confirm a clean tree, and require the root GitHub Actions check and
security scan to pass. A successful push alone is not extraction acceptance.

## Repository settings and reconciliation

Repository settings are a separate external mutation. After approval, configure the target so:

- `main` is the default branch and cannot be force-pushed or deleted;
- pull requests and the root deterministic check are required for normal changes;
- default workflow permissions are read-only;
- secret scanning, push protection, dependency review, and code scanning are enabled where the
  public-repository plan supports them; and
- no Actions secret, cloud credential, OIDC trust, Workload Identity Federation binding, protected
  deployment environment, or apply authority is created during extraction.

The first dedicated-repository pull request reconciles colocated wording, records the source and
split revisions, and verifies root commands and links. It must not begin AP-M7 or add Terraform.
Only after that pull request and its required checks pass may the Platform Owner declare
`comfforts/apps-platform` canonical.

During transition, platform changes stop in both repositories. The containing copy remains
canonical until the explicit cutover declaration; afterward it becomes historical and receives no
platform changes. Removing or replacing that copy and its CI wrapper is a separate, recoverable
containing-repository pull request. Extraction never changes Finance Assistant requirements, code,
infrastructure, state, DNS, identity, deployment, or access.

## Evidence and failure handling

The secret-free handoff records:

- source repository, source revision, source subtree identifier, split revision, and split tree;
- target repository and observed initial and final target refs;
- Git, uv, and Python versions;
- exact setup and verification commands, working directories, durations, and test totals;
- failures, errors, warnings, skips, limitations, and required-check results; and
- the approvals for initial push, settings, reconciliation, cutover, and later parent cleanup.

Console output and revision identifiers are sufficient. Do not commit clone credentials, remote URLs
containing credentials, raw GitHub API responses, screenshots, environment dumps, browser state, or
security-scan payloads.

Any mismatch or partial failure stops for inspection. Before canonical cutover, the containing
repository remains authoritative and the target must not receive platform changes. After cutover,
repair uses reviewed forward commits in the dedicated repository; do not overwrite its history or
silently resume authority in the containing copy.

## Acceptance boundary

Extraction is accepted only when the recorded source subtree and split root trees match, the split
is reproducible, history and inactive integration inputs are retained, the target and root workflow
pass the complete gate, repository settings are reviewed, the dedicated-repository reconciliation
is merged, and the owner explicitly declares the target canonical.

Acceptance proves repository continuity only. It proves no Terraform, provider, cloud, DNS,
identity, deployment, Live, or Application Adoption behavior and does not authorize AP-M7 edits
until their separate proposal is approved.
