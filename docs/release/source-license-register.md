# Source and license register

## Educational corpus

The machine-readable authority is
[`source_registry.v1.json`](../../backend/data/knowledge/source_registry.v1.json). At this release it
contains 70 reviewed entries: 49 approved and ingestion-enabled (18 Finance, 31 Tax) and 21 disabled
or pending entries. Enabled publishers are the U.S. Securities and Exchange Commission's
Investor.gov and the Internal Revenue Service.

Each entry records canonical URL, publisher, jurisdiction, tax years, status, AI-processing and
redistribution decisions, attribution requirement, restrictions, reviewer, and review timestamp.
The ingestion command processes only approved enabled entries. CFPB remains quarantined and FINRA,
Bogleheads, and commercial financial-institution content remain excluded unless a later approved
rights decision changes their registry status. Source count is not permission.

Active corpus manifests and exact model/source hashes are listed in the [version
register](version-register.md). Retrieved content is untrusted data and citations do not imply SEC
or IRS endorsement.

## Sample and provider data

- Portfolio examples are repository-authored synthetic data under the repository's own project
  distribution terms; their manifest records checksums and intended use.
- Provider fixtures are hand-authored synthetic data and are always labeled synthetic.
- Alpha Vantage, Massive, Tavily, OpenAI, and LangSmith content/services remain governed by the
  exact operator account and current provider terms. Configuration does not grant display,
  retention, redistribution, or public-demo rights. See the [operator runbook](operator-runbook.md)
  and [M3 provider policy](../M3_provider_policy.md).

## Software dependencies

`backend/uv.lock` and `frontend/pnpm-lock.yaml` are the exact dependency inventories. The M8
production dependency scans were clean at qualification time. The MCP adapter uses the official
Python MCP SDK, whose upstream repository declares the MIT license. Dependency license/terms can
change across upgrades; re-run security/license review when either lockfile changes. This register
is an engineering inventory, not legal advice or an exhaustive legal opinion.
