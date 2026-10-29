# M1 delivery report — Persistent Qdrant and offline knowledge ingestion

Status: Complete

Completed: 2026-10-27

Maintenance update: 2026-10-29 (Publication 560 / SEP-IRA coverage)

Scope: PR-007, PR-008; QR-005, QR-007, QR-008, QR-012, QR-014, QR-015; ADR-011, ADR-012, ADR-016, ADR-017

## Outcome

M1 delivers an explicit offline ingestion application, persistent versioned Qdrant collections, dense/sparse/hybrid retrieval evaluation, read-only runtime readiness, atomic activation, restart persistence, and rollback. It does not implement LangGraph, working agents, generation, user financial data, or production Qdrant hardening.

Active aliases at completion:

| Logical KB | Active physical collection | Documents | Points | Covered tax years |
| --- | --- | ---: | ---: | --- |
| Finance Education | `finance_education_v1_2fdf182ee6ab` | 5 | 20 | n/a |
| Tax Education | `tax_education_v1_4cf0dfd5f870` | 9 | 3,549 | 2022–2025 |

The 3,569 total records are structure/page-bounded source chunks produced by the documented chunk policy. No records were added to inflate a coursework count.

## Delivered interfaces and artifacts

- `backend/src/ai_finance_assistant/knowledge/`: versioned source/chunk/collection/evaluation contracts, bounded source acquisition and cache, HTML/PDF normalization, deterministic chunking, local FastEmbed representations, in-memory and Qdrant stores, retrieval, evaluation, and CLI orchestration.
- `backend/data/knowledge/source_registry.v1.json`: permitted-use, reviewer, source status, jurisdiction, tax-year, and ingestion decisions.
- `backend/data/knowledge/qrels.finance.v1.json` and `qrels.tax.v1.json`: fixed M1 retrieval cases.
- `compose.yaml`: Qdrant 1.20.0 bound to loopback with persistent storage and a health check.
- FastAPI readiness: validates aliases, named vector configuration, model revisions/hashes, chunk/schema versions, payload indexes, ready state, collection status, and nonempty points. It performs no writes or embedding.
- `backend/artifacts/m1/`: source/document manifests, evaluation reports, activation records, unchanged-rerun evidence, and rollback transcripts. See its `README.md` for current versus retained generations.

## Frozen local experiment

| Component | Version or artifact |
| --- | --- |
| Qdrant server | `qdrant/qdrant:v1.20.0` |
| Container digest | `sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2` |
| qdrant-client | 1.20.0 |
| FastEmbed | 0.9.1 |
| Dense | `BAAI/bge-small-en-v1.5`, 384 dimensions, cosine |
| Dense revision | `aa8f8b060edb00e03bfdd08813a2949946c8ba55` |
| Dense ONNX SHA-256 | `51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431` |
| Sparse | `Qdrant/bm25`, Qdrant IDF modifier |
| Sparse revision | `22b8d2af71a76161e18dd432d2cee0eefa66e412` |
| Sparse English artifact SHA-256 | `019f104ba2ed07436d05f9cdd3383034ad66014edc27fc651f837e1a038b6451` |
| Chunk policy | `structural-v1`: 1,600 max characters, 160 overlap, 80 minimum |

Changing an enabled source definition, source content, chunk policy, model identity/revision/artifact, or schema changes the candidate checksum and therefore the immutable physical collection name.

## Source-use decisions

- Enabled Finance sources are individually reviewed SEC/Investor.gov educational pages. SEC marks, art, linked third-party content, and endorsement implications are excluded.
- Enabled Tax sources are IRS-authored current publications, including Publication 560 for small-business retirement plans and SEP education, plus historical Publication 550 versions for 2022–2024. Tax year and federal jurisdiction remain explicit filters.
- Three CFPB entries are quarantined: the reviewed use policy was acceptable, but the bounded fetcher received HTTP 403 on 2026-10-27. M1 did not bypass that access control.
- FINRA is `pending_review` and disabled because its general terms do not provide the required RAG storage/vectorization/redistribution permission.
- Raw fetched bodies live only in ignored `backend/.cache/knowledge-sources/`; committed artifacts contain URLs, versions, hashes, and aggregate evidence rather than copied source bodies.

The supporting primary-source research is [M1_qdrant_models_sources.md](research/M1_qdrant_models_sources.md). This engineering review is not legal advice.

## Retrieval evaluation

The same fixed qrels, filters, collection, top-k of 5, and RRF configuration were used for all strategies.

| KB/strategy | Recall@5 | Precision@5 | MRR | Gate result |
| --- | ---: | ---: | ---: | --- |
| Finance dense | 0.875 | 0.55 | 1.00 | comparison |
| Finance sparse | 1.00 | 0.60 | 0.875 | comparison |
| Finance hybrid/RRF | 0.875 | 0.60 | 1.00 | pass |
| Tax dense | 1.00 | 0.7778 | 0.8889 | comparison |
| Tax sparse | 1.00 | 0.8667 | 0.8889 | comparison |
| Tax hybrid/RRF | 1.00 | 0.8444 | 0.8704 | pass |

Both hybrid candidates exceeded the EVAL-07 Recall@5 threshold of 0.85. Citation identifiers and critical year/jurisdiction filters passed exactly. Machine-readable reports are:

- `backend/artifacts/m1/finance_education_v1_2fdf182ee6ab.evaluation.json`
- `backend/artifacts/m1/tax_education_v1_4cf0dfd5f870.evaluation.json`

## Acceptance evidence

| Acceptance statement | Result and evidence |
| --- | --- |
| Startup validates without fetching or embedding | FastAPI `/api/health/ready` returned 200 after restart using read-only alias/config/metadata calls. Missing or unavailable Qdrant remains 503 in tests. |
| Unchanged rerun creates no duplicates | Timestamped final run artifacts for both active collections record `created: false` and `points_written: 0`. |
| Changed document creates a new version | Fixture tests prove a content change changes document and collection versions. A separate regression proves enabled permitted-use changes create a new candidate while unchanged content keeps its document version. |
| Incompatible collection is not ready | Unit tests cover unavailable/mismatched readiness; the live integration test validates full schema/index/vector compatibility. |
| Candidate activates only after gates | Store and integration tests reject unready activation. CLI calls `mark_ready` and alias activation only after the evaluation report passes. |
| Rollback restores the prior alias | `rollback-tax_education-20261027T224905Z.json` switches to the retained prior compatible collection; `...224906Z.json` restores the final candidate. Both states passed validation. |
| Restart preserves state | Qdrant was restarted through Compose; both aliases subsequently passed compatibility and FastAPI readiness returned HTTP 200. |

The initial Tax upsert also exercised recovery: Qdrant rejected a 41.7 MB request above its 32 MB limit. The adapter now writes deterministic IDs in 128-point batches, detects incomplete candidates, resumes safely, and verifies the exact point count after the write. No incomplete collection was activated.

## Verification record

Commands used during final qualification:

~~~bash
UV_CACHE_DIR=/private/tmp/aifa-uv-cache make verify
AIFA_TEST_QDRANT_URL=http://127.0.0.1:6333 uv run pytest -q tests/test_qdrant_integration.py
uv run python -m ai_finance_assistant.knowledge.cli validate --kb finance_education
uv run python -m ai_finance_assistant.knowledge.cli validate --kb tax_education
docker compose restart qdrant
~~~

Observed results after the 2026-10-29 maintenance qualification:

- Backend formatting, Ruff, and strict mypy: pass.
- Backend credential-free suite: 167 passed, 1 live-Qdrant test skipped by configuration, and 3 opt-in live tests deselected; total coverage rounds to 87%.
- Live-Qdrant integration: 1 passed.
- Frontend formatting, lint, typecheck, 9 tests, and production build: pass.
- Both final aliases: compatible.
- Exact commands are reproducible through `make verify`, `make qdrant-check`, and `make knowledge-validate`.

## Security, privacy, and observability impact

- The Compose service publishes only on `127.0.0.1`; it is unauthenticated and must not be exposed publicly.
- Offline fetching accepts only reviewed registry URLs, requires HTTPS, limits content type/size/time, and rejects redirects to unreviewed hosts.
- User files, portfolios, prompts, and credentials are not part of M1 data or evidence.
- Payload provenance includes document/chunk/content versions, publisher, canonical URL, fetch/review time, use basis, jurisdiction, and tax year.
- M1 artifacts are operational/evaluation evidence, not user-facing RunEvents. OpenTelemetry and optional LangSmith remain M4+ work under the approved observability plan.

## Limitations and unresolved decisions

- Finance qrels contain 4 cases and Tax qrels contain 9, including SEP-IRA retrieval against Publication 560. They are sufficient for the M1 gate, not a statistically broad release evaluation; M8 must expand and freeze independent holdouts.
- Only BGE-small plus BM25 were activated. MiniLM and SPLADE remain optional comparators if a later measured regression or hardware budget justifies them.
- CFPB remains quarantined and FINRA remains excluded until an approved access/rights decision changes their registry status.
- Retained-collection deletion count/age is not yet fixed. M1 keeps compatible prior generations and performs no automatic deletion.
- Query latency, ingestion peak memory, and production capacity are not claimed. M8 owns benchmark and reliability qualification.
- Local Qdrant lacks authentication, TLS, backup automation, replication, and production network isolation.

No unresolved item blocks M1 completion. The next permitted implementation work is M2 deterministic financial modules or M3 provider contracts; M4 agent/observability implementation still depends on M1–M3.
