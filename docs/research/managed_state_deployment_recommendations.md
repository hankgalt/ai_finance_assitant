# Managed-state deployment recommendations

Status: Research input; owner selection recorded separately; not deployment evidence | Reviewed: 2026-11-09

## Scope and authority

This record supports M11 slice 3 and PR-017; QR-001/003–007/010/011/014/015;
accepted ADR-003/011/012/016–019/024–029; and proposed ADR-030. Read it with
[M11's ordered slices and owner gates](../04_implementation_plan.md#m11--iap-protected-gcp-private-multi-user-deployment),
[the decision register](../02_architecture_decision_records.md), and
[system design §12](../03_system_design.md). It supplied decisions for review and is not an
amendment to accepted ADRs. The owner's selected outcome is the machine-readable
[managed-state contract](../../contracts/deployment/managed-state.v1.json); where an earlier
recommendation below differs, that contract controls. Managed-adapter implementation still requires
successful prototypes, and ADR-030 remains Proposed until integrated deployment qualification.

Inputs supplied for this research: project `comfforts-369117`, region `us-west1`, approximately
50 questions/day, few concurrent Runs, reasonable downtime, a single-region posture, Qdrant
Managed Cloud free tier on GCP, an empty deployed application store, secrets entered directly
in Secret Manager, and an IAP-protected private demonstration. Local development remains SQLite.
No local user records or owner-only provider-cache rows are transferred by this proposal.

The owner subsequently selected `db-f1-micro` with Cloud SQL's 10 GiB minimum SSD, seven daily
backups, three days of PITR logs, same-project staging with explicit weaker-isolation controls,
GitHub Pro on the public `hankgalt/ai_finance_assitant` repository, and `hankgalt` as the sole
deployment approver. The owner also created the one-node Qdrant Free cluster documented by the
managed-state contract in `us-central1`; its cross-region and no-SLA limitations remain explicit.
On 2026-11-10, the owner superseded only the managed-state lifecycle portion for the private-demo
MVP: use on-demand `db-g1-small`, start empty on every creation, intentionally discard deployed data
on destroy, and defer backup/PITR/RPO/RTO qualification. The earlier `db-f1-micro` and recovery
recommendations below are retained as decision history and post-MVP research; the current contract
and ADR-030 control implementation.

External factual claims below use only official Google Cloud and Qdrant sources. **Facts** describe
published capabilities as reviewed; **recommendations** and numerical operating targets are
engineering judgments requiring approval and measurement. No account console, price quote,
GitHub plan, cloud resource, restore, or adapter was inspected or executed in this research.

## Recommended decision set

Every entry in this table is a **recommendation**, not an operational claim.

| Decision | Proposed choice | Reason and remaining gate |
| --- | --- | --- |
| Application and checkpoint persistence | Cloud SQL for PostgreSQL, Enterprise edition, single zone in `us-west1`; initial `db-f1-micro`, 10 GiB SSD | One transactional relational service fits the existing application model. Treat the smaller shared-core tier as provisional: measure memory, connection use, and concurrency and upgrade if qualification fails. No HA or availability SLA is promised. |
| Checkpoint adapter | Prefer the official LangGraph PostgreSQL saver behind the existing application-owned checkpoint seam | Do not copy SQLite-specific SQL or deserialize arbitrary stored objects. Exact upstream package/API, strict deserialization, migrations, deletion, and compatibility remain implementation research/prototype gates. Google's distinct Cloud SQL saver is a possible comparison, not assumed interchangeable. |
| Historical provider cache | Separate versioned tables/schema in the same Cloud SQL instance, behind its existing persistence port | Preserve provider, instrument, interval, adjustment basis, currency, timestamps, rights, schema, and policy keys; keep it distinct from imported Portfolios and Snapshots. No extra always-on database service is justified initially. |
| Response cache | Disabled for deployed M11 initially; retain the qualified optional local Redis path | ADR-028 makes it optional. At this volume, qualify state and recovery first. A disabled cache must remain visible in configuration/telemetry and must not imply lost product correctness. |
| Workload implication | Stateless Cloud Run is the preferred runtime candidate; authoritative state remains external | This is a state-placement recommendation, not final load-balancer/IAP/network approval. Prove the existing REST/SSE and graph lifecycle across instance replacement before choosing final runtime settings. |
| Secrets and encryption | Regional Secret Manager in `us-west1`, workload identity, pinned secret versions, service-managed encryption at rest and TLS | No long-lived GCP service-account keys. Terraform manages secret metadata/IAM only; owner enters payloads directly. CMEK adds cost and recovery obligations without a stated requirement. |
| Recovery | Daily standard backups; retain 7 daily backups; explicitly enable PITR with 3-day transaction-log retention | Proposed database RPO ≤5 minutes and operator-led RTO ≤4 hours in a healthy selected region, subject to real rehearsal. No regional-disaster recovery bound is promised. |
| Staging | Same GCP project with separate Terraform state, identities, secrets, database role, and synthetic data; use an ephemeral instance for restore tests | Reduces administration, not blast radius. Project-level IAM, quota, billing, and regional failures remain shared and are an accepted private-demo limitation. |
| Approval | `hankgalt` is the sole production approver for the public GitHub Pro repository | Self-review remains allowed because there is no backup approver. This is a deliberate single-operator gate, not independent review. |

## Application, checkpoint, and provider stores

**Facts.** Cloud SQL Enterprise shared-core machine types are available in `us-west1`.
The `db-f1-micro` and `db-g1-small` types are excluded from the Cloud SQL SLA. Region and size
therefore do not themselves establish an availability guarantee.
[Region availability](https://docs.cloud.google.com/sql/docs/postgres/region-availability-overview),
[machine series](https://docs.cloud.google.com/sql/docs/postgres/machine-series-overview).

Google documents a `PostgresSaver` in its own `langchain-google-cloud-sql-pg` package for LangGraph
state snapshots. This establishes a supported PostgreSQL integration path, not compatibility of
that package with this repository's serializer or the upstream LangGraph PostgreSQL saver.
[Cloud SQL Python integration](https://docs.cloud.google.com/python/docs/reference/langchain-google-cloud-sql-pg/latest).

**Recommendation and inference.** Use one managed PostgreSQL instance for authoritative application
rows and checkpoints, with distinct application-owned tables and explicit checkpoint lifecycle
handling. Keep provider-cache tables independently purgeable. Separate roles should distinguish
runtime DML, migrations/DDL, and backup/restore administration. Prefer IAM database authentication
where the chosen driver/checkpointer can renew credentials correctly; otherwise store a narrowly
privileged database password in Secret Manager and qualify rotation. Do not grant the runtime
database-owner privileges merely to allow a saver to initialize its schema.

Choose PostgreSQL 17 as an initial prototype baseline, pin the selected supported major and
driver/checkpointer versions, and recheck support before provisioning. Google lists versions
including 16, 17, and 18; selecting a version is a project decision, not permission to follow
the service's changing default. [Instance settings](https://docs.cloud.google.com/sql/docs/postgres/instance-settings).

Application and saver writes may use different transactions even on the same instance. Do not
claim atomic whole-Run commits without a tested contract. Rehearse crashes after application writes,
after checkpoint writes, and before terminal Run persistence; preserve idempotency and truthful
interrupted/partial states. The deployed store starts empty and uses its own schema bootstrap;
the local schema-v4 upgrade and existing local checkpoints stay local. A new persistence decision
must amend ADR-003 and ADR-026's deployment boundaries without changing their qualified local mode.

Firestore could supply a managed document store, but switching the relational model and lifecycle
constraints is additional application work without a demonstrated benefit here. Its TTL deletion is
asynchronous and does not delete subcollections, so TTL alone would not satisfy Session cascade
deletion. [Firestore TTL](https://docs.cloud.google.com/firestore/native/docs/ttl).
The recommendation is not to introduce Firestore, AlloyDB, Spanner, or a VM-hosted SQLite service
for this small initial managed-state slice.

**Provider-rights boundary.** Carry forward ADR-024–026 unchanged. Start deployed provider modes
with deterministic adapters unless account-specific role/display/cache rights have been recorded.
The local owner-only unverified-retention exception is prohibited in the deployed environment.
Do not carry the 3,650-day local historical-cache maximum into a shared deployment as permission.
Only enable each provider/endpoint's deployed retention after its rights decision supplies an
explicit limit; no approval means no retained live rows and no viewer live-provider access.
Cloud storage, encryption, or ownership of a paid account creates no redistribution right.

## Runtime and response-cache implications

**Facts.** Cloud Run's writable container filesystem consumes instance memory and disappears when
the instance stops. It can process concurrent requests and scale to multiple instances. Therefore
a local database file or process memory cannot be treated as the deployment's durable shared state.
[Container contract](https://docs.cloud.google.com/run/docs/container-contract),
[concurrency](https://docs.cloud.google.com/run/docs/about-concurrency).

Cloud Run's Cloud SQL connection integration limits each container instance to 100 database
connections; application pools can impose a smaller bound. The Cloud SQL Auth Proxy encrypts its
server connection and authorizes connection establishment with IAM, but creates no new network
path and supplies no connection pooling.
[Cloud Run connection guidance](https://docs.cloud.google.com/sql/docs/postgres/connect-run),
[Auth Proxy](https://docs.cloud.google.com/sql/docs/postgres/sql-proxy).

**Recommendation.** Prototype Cloud Run at minimum instances 0, maximum 3, request concurrency 4,
one application worker per container, and at most 5 aggregate application/checkpoint database
connections per container with no unbounded overflow. Include rollout overlap, migration jobs,
retention jobs, and restore probes in the total connection budget. These are starting limits, not
measured capacity or a strict global spending cap. Keep transactions short; never hold a database
transaction while waiting on a model/provider call or streaming to a browser.

Prefer private-IP Cloud SQL through an explicit supported Cloud Run VPC path, plus an encrypted
connector/proxy path; qualify compatibility with the selected checkpoint driver. Network
reachability, database grants, and per-Principal application authorization are separate controls.
If compatibility requires another documented TLS connection path, review that concrete alternative
rather than disabling TLS.
Run retention as an independently invoked scheduled job, not an idle web-process timer. SSE
reconnect/replay must read durable events and tolerate instance replacement; an in-flight Python
graph task is not made durable simply by installing a checkpoint saver.

**Facts about an optional later cache.** Memorystore for Redis supports vector search on Redis 7.2.
Its documented vector index permits at most ten attributes. Basic tier is appropriate for
disposable cache state; RDB persistence may be enabled by default when created in the console.
[Supported versions](https://docs.cloud.google.com/memorystore/docs/redis/supported-versions),
[vector limitations](https://docs.cloud.google.com/memorystore/docs/redis/vector-search-limitations),
[tier capabilities](https://docs.cloud.google.com/memorystore/docs/redis/redis-tiers).

**Recommendation.** Do not assume Memorystore is a drop-in replacement for the pinned Redis 8 /
RedisVL local adapter. Its index limit must be reconciled with all required Session, evidence,
version, jurisdiction, and tax-year filters; no isolation filter may be dropped to make it fit.
Only revisit a 1 GiB Basic instance after a measured cache-disabled deployment benchmark justifies
its fixed cost and a real RedisVL compatibility/privacy test passes. Explicitly disable persistence,
use TLS/authentication, keep the maximum 24-hour TTL and archive/delete purge, and treat loss as a
measured bypass. A Redis sidecar would be per-instance disposable memory, with different purge and
coalescing behavior; it is not the selected managed topology. Do not move response entries into
the authoritative database or shared Qdrant collections merely to reuse an existing service.

## Qdrant constraints and knowledge recovery

**Facts.** A Qdrant free cluster has one node, 0.5 vCPU, 1 GB RAM, and 4 GB disk, with limited
provider/region choices, manual API snapshots/restores, and downtime during upgrades. Unused free
clusters suspend after one week and are deleted after four weeks if not reactivated.
[Free cluster limits](https://qdrant.tech/documentation/cloud/create-cluster/).
Free tier has no uptime SLA, and scheduled backups are unavailable.
[Managed tiers](https://qdrant.tech/documentation/cloud/),
[backup policy](https://qdrant.tech/documentation/cloud/backups/).

Qdrant encrypts Managed Cloud volumes at rest and protects transit with TLS. Its database keys can
be read-only and collection-restricted. Private network connectivity and customer-managed storage
keys require Premium; the free choice must not be described as private-network attached or CMEK
protected. [Cloud security](https://qdrant.tech/documentation/cloud-security/),
[encryption](https://qdrant.tech/documentation/cloud/encryption/),
[key scope and rotation](https://qdrant.tech/documentation/cloud/authentication/).

**Recommendation.** Preserve the owner's free-GCP selection for slice-3 prototype/staging
evidence. Its prototype/test positioning, single node, no SLA, manual snapshots, and inactivity
deletion make it a **cutover stop gate for M11 production acceptance**: upgrade to an appropriate
paid topology, or obtain an explicit requirements/ADR-gate change with the reduced posture and
recovery risk recorded. Successful prototype tests alone do not satisfy that production gate.
Record the actual free GCP region offered by the account before proceeding. Official reviewed
pages do not prove that free GCP `us-west1` is selectable. If unavailable, stop for the explicit
choice between a region exception and a paid same-region service; do not silently claim a
single-region topology. Measure cross-region latency/egress if an exception is approved.

Runtime gets a query-only key; the offline release identity alone gets collection/snapshot/alias
write privileges. Keep all user Portfolios, checkpoints, prompts, and response caches out of this
shared knowledge store. Before activation and before destructive changes, download and verify
collection snapshots plus manifests, model/schema versions, hashes, and alias mapping in an
access-controlled artifact bucket. Retain the active and previous qualified releases plus the
currently reviewed candidate; measure their combined storage/index/snapshot footprint against the
free limits before upload. Record the actual restore procedure: collection snapshots are not an
assumption that cloud account settings, keys, or aliases are recovered automatically.

Proposed knowledge RPO is **zero released collection versions lost** when every activation has a
verified externally retained release artifact. Proposed RTO is one working day for re-creating a
free cluster and restoring/requalifying it, conditional on free capacity and region availability.
This is not a vendor guarantee. Readiness must report suspended/missing collections honestly;
startup must never regenerate embeddings. Check availability before a scheduled demonstration and
document reactivation. Do not conceal inactivity deletion behind an invented availability SLO.

## Secret handling and encryption

**Facts.** Regional Secret Manager can constrain storage/access to a region, is offered in
`us-west1`, and encrypts secrets at rest and in transit. Google recommends least privilege,
separating environments, direct API access, pinning version numbers, and disabling old versions
before destruction. [Regional service](https://docs.cloud.google.com/secret-manager/regional-secrets/overview-rs),
[locations](https://docs.cloud.google.com/secret-manager/docs/locations),
[best practices](https://docs.cloud.google.com/secret-manager/docs/best-practices).
Cloud SQL uses Google-managed encryption by default, and Cloud SQL backups are encrypted.
[Instance encryption](https://docs.cloud.google.com/sql/docs/postgres/instance-settings),
[backup encryption](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/backups).

The global Secret Manager service defaults to automatic replication across unrestricted global
locations. User-managed replication selects payload locations and bills each location separately;
it is a different option from the regional service. Neither the global automatic default nor a
resource name alone establishes `us-west1` residency.
[Replication policies](https://docs.cloud.google.com/secret-manager/docs/choosing-replication).

**Recommendation.** Use regional Secret Manager API reads through the workload's service account,
pin version resource names in non-secret deployment configuration, and grant secret-level accessor
rights only to the workload that needs each value. Runtime must not access Qdrant management keys,
deployment identities, or unrelated providers. Keep staging versions separate. CI should need
resource identifiers, not secret payloads. No secret payload belongs in Terraform variables/state,
repository files, logs, reports, or client bundles. A Secret Manager API read is preferable to
expanding the process environment; any integration fallback needs equivalent redaction tests.

Rotate on suspected compromise and provider/account changes; begin with a reviewed 90-day rotation
review cadence rather than claiming provider keys rotate automatically. Keep one current and one
previous deployable version during a defined seven-day rollback window; disable superseded versions
and destroy after confirming no retained revision needs them. Immediate compromise revocation
overrides rollback convenience. Use service-managed keys initially; a future CMEK requirement needs
separate availability, key-deletion, billing, and restore tests.

## Retention, deletion, and recovery proposals

The table is a **proposed deployed policy**, not legal-policy approval or existing behavior.

| Artifact | Proposed bound and enforcement |
| --- | --- |
| Uploaded file bytes | Parse-scoped ephemeral storage; remove on success/failure; never include in database backups or logs. |
| Sessions, Runs, checkpoints, Session-owned contexts/idempotency | Preserve the existing 30-day Session expiry clock and cascade semantics. Do not extend expiry by archive or restore. Reject expired access immediately; scheduled deletion within 24 hours, with missed-job alerting. |
| Saved Portfolios and dependent Snapshots | At most the existing 365-day Portfolio expiry; earlier explicit deletion or owning-Session cascade wins. No orphaned enrichment, Snapshot, or context may outlive its owner. |
| RunEvents | At most 30 days, or earlier Session cascade; append-only while live, read-only history after archive. |
| Provider observations | Rights-approved endpoint-specific TTL only; deterministic fixtures may use bounded test policy. No deployed owner-only unverified retention. |
| Response entries | None in selected deployment; any later approval retains ADR-028's ≤24-hour TTL and archive/delete purge. |
| Application operational logs/traces | 30 days in a region-selected access-controlled bucket, with no raw user content. Cloud-required administrative audit retention is a separate disclosed exception. |
| Application backups/PITR | 14 retained daily backups, 7 days of PITR logs, explicitly located in `us-west1`; pre-migration on-demand backups removed within 14 days after validation. Final backups and retained backups must also have a reviewed bounded cleanup path. |
| Knowledge release artifacts | Active and previous qualified releases, plus bounded candidate; source-use policy governs provenance/source retention independently. Remove superseded artifacts after promotion/rollback review. |

**Facts.** Standard Cloud SQL on-demand backups can persist indefinitely until explicitly removed.
Enterprise PITR logs support 1–7 days; Google recommends retaining an extra daily backup beyond the
log-day count. PITR is off by default for Enterprise instances created through Terraform/API/CLI.
PITR creates a new instance; Google's typical RPO of five minutes or less is not a measured RPO
for this application. [Backup options and retention](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/backup-options),
[restore behavior](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restore).
Cloud Logging's `_Required` bucket has a fixed 400-day retention; project `_Default` and custom
buckets default to 30 days. [Logging retention](https://docs.cloud.google.com/logging/quotas).

**Recommendation.** Explicitly configure backup location, retained-backup/final-backup settings,
PITR, deletion protection, and monitoring in Terraform; defaults are not evidence. Rehearse restore
into an isolated database instance in the same region, verify application/checkpoint consistency,
apply expiry and deletion reconciliation, run the two-Principal negative suite, then switch the
connection reference under a maintenance window. A migration rollback may require a restored store
and old image together; rolling back only the application image does not undo schema writes.

Deletion from the live store cannot selectively erase an individual from existing full-instance
backups. Disclose the backup window and restore-only access restrictions. Preserve a minimal,
access-controlled deletion/disabled-Principal reconciliation record outside the restored database
for at least the recovery window, so restoring an old backup cannot resurrect deleted data or
re-enable an account. Its exact fields, expiry, and recovery authority require privacy review.
No restored instance serves traffic before reconciliation passes.

The proposed ≤5-minute database RPO and ≤4-hour RTO apply only after a timed successful rehearsal
in an available region with an operator able to respond. If PITR is unavailable, daily backups
alone imply approximately a day's potential data loss. Single-zone maintenance/failure and a whole
`us-west1` outage can interrupt service; this design has no cross-region failover or guaranteed
regional-disaster RTO. Cache state is disposable and has no recovery obligation.

## Capacity and cost decisions

**Published reference prices, not an account quote.** Google's pricing page as rendered for this
review exposes the default Iowa regional table; it lists `db-g1-small` at $0.035/hour,
`db-f1-micro` at $0.0105/hour, SSD at $0.000232877/GiB-hour, and used backup storage at
$0.000109589/GiB-hour. Re-select `us-west1` in the official calculator/SKU quote before approval.
At 730 hours, the reference arithmetic for `db-g1-small` plus 10 GiB SSD is **$27.25/month before
backups, networking, and other services**; it is not a verified Oregon total.
[Cloud SQL pricing](https://cloud.google.com/sql/pricing).

Secret Manager includes six active versions and 10,000 access operations/month in its free
allowance, with $0.03 per 10,000 additional accesses and about $0.06 per additional active
version/month. Account-level allowance may already be consumed elsewhere.
[Secret Manager pricing](https://cloud.google.com/secret-manager/pricing).

**Recommended limits for approval.** Propose $75/month for the whole demo environment and
$25/month for temporary staging, or $100/month combined, subject to an actual complete estimate.
These are owner review/alert thresholds, not proven sufficient budgets or automatic caps.
Load balancing, Cloud Run, logging, build/image storage, networking, Terraform state,
Qdrant changes, model/provider charges, taxes, and existing project workloads are not covered by
the $27.25 reference subtotal. No total ceiling has been approved by this document.

Begin with 10 GiB SSD, allow growth to 20 GiB, and alert at 60% and 80% utilization. Retain a
bounded connection pool and Run admission limit; measure 1, 2, and 4 concurrent Runs plus long-lived
SSE clients. Alert on database memory pressure, connection exhaustion, failed backups, missing
PITR recovery time, retention lag, and Qdrant storage/memory headroom. Cloud SQL may override
storage-auto-growth limits for critical maintenance, and filling the disk can stop the instance;
the setting is a guardrail, not a guaranteed billing ceiling.
[Storage settings](https://docs.cloud.google.com/sql/docs/postgres/instance-settings).

Configure project/service budget alerts at 50%, 80%, and 100% of an approved allowance and a
documented owner response. Alerts-only budgets do not cap spend. Any newer spend-cap feature
requires checking service eligibility and failure effects; it must not be assumed to cover the
whole stack. Enforce application model/provider request budgets independently, and respond to
excess cost by restricting new paid work without deleting authoritative state.
[Budget behavior](https://docs.cloud.google.com/billing/docs/how-to/budgets),
[spend-cap scope](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).

## Staging, approvers, and release gates

**Recommendation.** Use a separately billed/labelled staging project with synthetic records and
independent runtime, migration, and deployment identities. Google's secret guidance recommends
project separation to isolate environment IAM and quotas. If the owner insists on one project,
record that exception explicitly and use separate Cloud SQL instances, secrets, service accounts,
buckets/state, and Qdrant write scopes; naming prefixes or separate databases on one instance
are weaker isolation and share administrative/recovery blast radius.
[Environment separation guidance](https://docs.cloud.google.com/secret-manager/docs/best-practices).

Create no second Qdrant free cluster on an assumed free allowance. Confirm account entitlement
and region before choosing an independent staging cluster; otherwise restrict staging to
synthetic/local Qdrant until a paid or separately authorized topology is approved. Production
promotion must use a tested offline release identity and a qualified artifact, not a web-startup
ingestion path.

GitHub approvers are an owner decision that Google/Qdrant documentation cannot resolve. Proposed
policy: named owner approval for each demo apply/deploy/migration/restore, a named backup human
if available, separate staging/demo environments, and no silent protection bypass. Record the
actual GitHub handles, plan/repository support, whether self-approval is permitted, and the
emergency rollback authority in slice 4. If independent review is unavailable, disclose that
limitation rather than describe a one-person process as two-person control. This research makes
no claim that GitHub environment protections are configured or available on the repository's plan.

Before implementation/provisioning, obtain explicit selections for database/saver, size/major,
network path, response-cache disabled mode, retention/recovery objectives, encryption posture,
staging/project separation, actual Qdrant region/limits, billing ceilings, and approver identities.
Before slice 3 passes, record real-adapter migration/restart, concurrent ownership denial,
idempotency/crash reconciliation, strict-deserialization, expiry/deletion/restore, provider/cache
outage, TLS/secrets/redaction, and timed backup/PITR restore results. CI stays credential-free;
real-service qualification is explicit and separately budgeted.

Evidence belongs under persistence, identity/access, knowledge, quality, or release deployment
ownership as defined by [repository layout](../repository_layout.md), with exact commands,
versions, timings, errors/skips, artifact paths, privacy/security findings, and remaining decisions.
This documentation-only research ran no application tests, cloud provisioning, recovery exercise,
provider calls, or paid benchmark. Its unresolved region, rights, compatibility, pricing, and owner
approval gates must not be reported as operational controls or passed milestone acceptance.
