# M1 delivery report — Persistent Qdrant and offline knowledge ingestion

Status: Complete

Completed: 2026-10-27

Maintenance updates: 2026-10-29 (SEP-IRA and ETF/mutual-fund coverage); 2026-10-31 (governed corpus breadth, Publication 505 rollover, direct home-sale and pension/annuity coverage, and requested IRS publication closure)

Scope: PR-007, PR-008; QR-005, QR-007, QR-008, QR-012, QR-014, QR-015; ADR-011, ADR-012, ADR-016, ADR-017

## Outcome

M1 delivers an explicit offline ingestion application, persistent versioned Qdrant collections, dense/sparse/hybrid retrieval evaluation, read-only runtime readiness, atomic activation, restart persistence, and rollback. It does not implement LangGraph, working agents, generation, user financial data, or production Qdrant hardening.

Active aliases at completion:

| Logical KB | Active physical collection | Documents | Points | Covered tax years |
| --- | --- | ---: | ---: | --- |
| Finance Education | `finance_education_v1_755be30b6a2d` | 18 | 106 | n/a |
| Tax Education | `tax_education_v1_9b31ab2354ea` | 31 | 6,295 | 2022–2026 |

The 6,401 total records are structure/page-bounded source chunks produced by the documented chunk policy. No records were added to inflate a coursework count. CA-04 counts substantive records, not source URLs; the expansion was accepted for topic breadth and retrieval quality rather than to manufacture a document count.

The 2026-10-31 maintenance added twelve individually reviewed SEC/Investor.gov sources and twenty-two pinned or edition-checked IRS sources across its successive slices. It also registered fourteen Bogleheads Wiki candidates as disabled `pending_review` records after first-party license statements proved ambiguous. Publication 505 (2025) now uses its immutable prior-year PDF, while the mutable current URL is represented separately as Publication 505 (2026). The explicit publication-closure slice verifies and indexes the requested 2025 editions of Publications 501, 523, 525, 544, 551, 554, 575, 721, 915, 925, 936, 970, and revision-dated Publication 1212; Publications 523, 551, and 575 were already active, so ten documents were newly added.

## Delivered interfaces and artifacts

- `backend/src/ai_finance_assistant/knowledge/`: versioned source/chunk/collection/evaluation contracts, bounded source acquisition and cache, HTML/PDF normalization, deterministic chunking, local FastEmbed representations, in-memory and Qdrant stores, retrieval, evaluation, and CLI orchestration.
- `backend/data/knowledge/source-registry.v1.json`: permitted-use, reviewer, source status, jurisdiction, tax-year, and ingestion decisions.
- `backend/data/knowledge/finance-education/retrieval-cases.v1.json` and
  `backend/data/knowledge/tax-education/retrieval-cases.v1.json`: fixed M1 retrieval cases.
- `compose.yaml`: Qdrant 1.20.0 bound to loopback with persistent storage and a health check.
- FastAPI readiness: validates aliases, named vector configuration, model revisions/hashes, chunk/schema versions, payload indexes, ready state, collection status, and nonempty points. It performs no writes or embedding.
- `backend/artifacts/knowledge/`: source/document manifests, evaluation reports, activation records, unchanged-rerun evidence, and rollback transcripts. See its `README.md` for current versus retained generations.

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

- Enabled Finance sources are eighteen individually reviewed SEC/Investor.gov educational pages. The twelve-source breadth update covers goals, diversification, risk tolerance, accounts, stocks, bonds, annuities, and pooled-fund types. The April 29, 2025 Investor Bulletin remains included for direct ETF/mutual-fund comparison while preserving its staff-view/no-legal-force limitation. SEC marks, art, linked third-party content, and endorsement implications are excluded.
- Enabled Tax sources are thirty-one IRS-authored publications and form instructions. The breadth updates cover filing/dependent/standard-deduction rules, taxable income, home sales, property dispositions and basis, senior filing, pension and civil-service annuities, Social Security, passive activities, mortgage interest, education benefits, original-issue discount, foreign-tax credit, interest/dividend and capital-gain reporting, nondeductible IRA basis, additional retirement-account taxes, and net-investment-income tax. Tax year and federal jurisdiction remain explicit filters; Publication 550 retains historical editions for 2022–2024.
- Fourteen Bogleheads Wiki pages are registered as `pending_review` and disabled. The first-party copyright page states CC BY-SA 4.0 while the general disclaimer states noncommercial use, and the current evidence contract cannot propagate all revision/license/change/ShareAlike fields. No Bogleheads page was fetched, embedded, added to qrels, or activated.
- Three additional IRS candidates remain disabled pending a demonstrated qrel gap or source-specific extraction review. Publication 571 still requires an exact applicability and source decision; Forms 4952 and 8815 remain unnecessary without exact-form qrel gaps.
- Three CFPB entries are quarantined: the reviewed use policy was acceptable, but the bounded fetcher received HTTP 403 on 2026-10-27. M1 did not bypass that access control.
- FINRA is `pending_review` and disabled because its general terms do not provide the required RAG storage/vectorization/redistribution permission.
- Raw fetched bodies live only in ignored `backend/.cache/knowledge-sources/`; committed artifacts contain URLs, versions, hashes, and aggregate evidence rather than copied source bodies.

Supporting primary-source research is [M1_qdrant_models_sources.md](research/M1_qdrant_models_sources.md), [M1_corpus_expansion_sources.md](research/M1_corpus_expansion_sources.md), and [M1_irs_publication_expansion_2025.md](research/M1_irs_publication_expansion_2025.md). This engineering review is not legal advice.

## Retrieval evaluation

The same fixed qrels, filters, collection, top-k of 5, and RRF configuration were used for all strategies.

| KB/strategy | Recall@5 | Precision@5 | MRR | Gate result |
| --- | ---: | ---: | ---: | --- |
| Finance dense | 1.00 | 0.5294 | 0.9314 | comparison |
| Finance sparse | 1.00 | 0.4235 | 0.8235 | comparison |
| Finance hybrid/RRF | 1.00 | 0.4941 | 0.9706 | pass |
| Tax dense | 0.9063 | 0.5438 | 0.6703 | comparison |
| Tax sparse | 1.00 | 0.6125 | 0.8396 | comparison |
| Tax hybrid/RRF | 1.00 | 0.6313 | 0.7208 | pass |

Both hybrid candidates exceeded the EVAL-07 Recall@5 threshold of 0.85. Citation identifiers and critical year/jurisdiction filters passed exactly. Machine-readable reports are:

- `backend/artifacts/knowledge/finance-education/finance_education_v1_755be30b6a2d.evaluation.json`
- `backend/artifacts/knowledge/tax-education/tax_education_v1_9b31ab2354ea.evaluation.json`

## Acceptance evidence

| Acceptance statement | Result and evidence |
| --- | --- |
| Startup validates without fetching or embedding | FastAPI `/api/health/ready` returned 200 after restart using read-only alias/config/metadata calls. Missing or unavailable Qdrant remains 503 in tests. |
| Unchanged rerun creates no duplicates | Timestamped final run artifacts for both active collections record `created: false` and `points_written: 0`. |
| Changed document creates a new version | Fixture tests prove a content change changes document and collection versions. Regressions prove enabled permitted-use changes create a new candidate and a reviewed URL change invalidates the local source cache instead of reusing a body fetched from the old URL. |
| Incompatible collection is not ready | Unit tests cover unavailable/mismatched readiness; the live integration test validates full schema/index/vector compatibility. |
| Candidate activates only after gates | Store and integration tests reject unready activation. CLI calls `mark_ready` and alias activation only after the evaluation report passes. |
| Rollback restores the prior alias | The 2026-10-31 activation records preserve `finance_education_v1_fcecb8c15493` and `tax_education_v1_f2fef46b0f88` as the immediate rollback targets. The retained 2026-10-27 rollback-and-restore transcript proves the same atomic alias path in both directions. |
| Restart preserves state | Qdrant was restarted through Compose after the 2026-10-31 activation; the service returned healthy and both aliases subsequently passed the complete compatibility check. |

The initial Tax upsert also exercised recovery: Qdrant rejected a 41.7 MB request above its 32 MB limit. The adapter now writes deterministic IDs in 128-point batches, detects incomplete candidates, resumes safely, and verifies the exact point count after the write. No incomplete collection was activated.

## Verification record

Commands used during final qualification:

~~~bash
UV_CACHE_DIR=/private/tmp/aifa-uv-cache make m1-check
UV_CACHE_DIR=/private/tmp/aifa-uv-cache AIFA_TEST_QDRANT_URL=http://127.0.0.1:6333 uv run pytest -q tests/test_qdrant_integration.py
UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run python -m ai_finance_assistant.knowledge.cli run --kb finance_education --qrels data/knowledge/finance-education/retrieval-cases.v1.json --activate
UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run python -m ai_finance_assistant.knowledge.cli run --kb tax_education --qrels data/knowledge/tax-education/retrieval-cases.v1.json --activate
docker compose restart qdrant
UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run python -m ai_finance_assistant.knowledge.cli validate --kb finance_education
UV_CACHE_DIR=/private/tmp/aifa-uv-cache uv run python -m ai_finance_assistant.knowledge.cli validate --kb tax_education
~~~

Observed results after the 2026-10-31 maintenance qualification:

- Backend formatting, Ruff, and strict mypy: pass.
- Backend credential-free suite: 205 passed, 1 live-Qdrant test skipped by configuration, and 3 opt-in live tests deselected; measured repository coverage rounds to 88%.
- Focused local-Qdrant integration: 1 passed.
- Finance: 18 documents, 106 chunks, 17 qrels, hybrid Recall@5 1.00, exact filter and citation gates pass.
- Tax: 31 documents, 6,295 chunks, 32 qrels, hybrid Recall@5 1.00, exact filter and citation gates pass. All ten newly added requested publications are represented by fixed natural-language retrieval cases; the reported home-sale and pension/annuity questions retrieve Publications 523 and 575 respectively.
- Both activation reruns wrote zero points and recorded their previous collections; both aliases remained compatible after Qdrant restart.
- Unchanged frontend gate: formatting, lint, typecheck, 30 tests, and production build pass.

## Security, privacy, and observability impact

- The Compose service publishes only on `127.0.0.1`; it is unauthenticated and must not be exposed publicly.
- Offline fetching accepts only reviewed registry URLs, requires HTTPS, limits content type/size/time, and rejects redirects to unreviewed hosts.
- Cached bodies are bound to the reviewed requested URL, so a registry URL rollover forces a new bounded fetch. HTML/PDF normalization redacts exact missing-child notice text and rejects residual noisy-column chunks carrying NCMEC, phone, caption, or index markers; all 6,295 activated payloads were scanned with zero governed-photo matches.
- User files, portfolios, prompts, and credentials are not part of M1 data or evidence.
- Payload provenance includes document/chunk/content versions, publisher, canonical URL, fetch/review time, use basis, jurisdiction, and tax year.
- M1 artifacts are operational/evaluation evidence, not user-facing RunEvents. OpenTelemetry and optional LangSmith remain M4+ work under the approved observability plan.

## Limitations and unresolved decisions

- Finance qrels contain 17 cases and Tax qrels contain 32, including exact-term, semantic, direct comparison, publication-closure, form-number, SEP-IRA, and 2022–2026 year-filter cases. They are sufficient for the M1 activation gate, not a statistically broad independent release evaluation; M8 must freeze separate holdouts.
- Only BGE-small plus BM25 were activated. MiniLM and SPLADE remain optional comparators if a later measured regression or hardware budget justifies them.
- Bogleheads and FINRA remain excluded until an approved rights decision changes their registry status. CFPB remains quarantined until an approved access method is documented.
- Retained-collection deletion count/age is not yet fixed. M1 keeps compatible prior generations and performs no automatic deletion.
- Query latency, ingestion peak memory, and production capacity are not claimed. M8 owns benchmark and reliability qualification.
- Local Qdrant lacks authentication, TLS, backup automation, replication, and production network isolation.

No unresolved item blocks this M1 maintenance activation. The Bogleheads license conflict blocks only those disabled candidates, not the approved SEC/IRS collections.
