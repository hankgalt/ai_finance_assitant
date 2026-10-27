# M1 Qdrant, representation-model, and source-use research

Status: M1 decision input, not an accepted ADR

Researched: 2026-10-27

Scope: PR-007/PR-008, QR-005/QR-007/QR-008/QR-012/QR-014/QR-015, ADR-005/ADR-012/ADR-016/ADR-017

This note records primary-source findings needed to begin M1. It does not claim that a model, source, threshold, or hosting choice has passed the M1 acceptance gates. The implementation must still produce the source manifest, use-rights review, fixed qrels, comparative retrieval report, activation record, and rollback transcript required by [the implementation plan](../04_implementation_plan.md#m1--persistent-qdrant-and-offline-knowledge-ingestion).

## Recommended M1 experiment plan

Use a single-node, standalone Qdrant container for local development and evaluation. Start the compatibility experiment with exact pins for the current official releases: `qdrant/qdrant:v1.20.0`, `qdrant-client==1.20.0`, and `fastembed==0.9.1`; record the resolved container digest and Python lockfile. Qdrant publishes Docker as the recommended development/test path, and the current release pages identify Qdrant and qdrant-client 1.20.0; PyPI and Qdrant's model registry identify FastEmbed 0.9.1. These are experiment pins, not approval to upgrade without rerunning M1 gates. ([Qdrant installation](https://qdrant.tech/documentation/install/), [Qdrant 1.20.0 release](https://github.com/qdrant/qdrant/releases/tag/v1.20.0), [qdrant-client releases](https://github.com/qdrant/qdrant-client/releases), [FastEmbed package](https://pypi.org/project/fastembed/), [FastEmbed registry](https://qdrant.tech/documentation/embeddings/fastembed/))

Bind REST and, only if needed, gRPC to loopback and use a persistent named volume. A self-hosted Qdrant instance is unauthenticated and open to all network interfaces by default; Qdrant explicitly directs local development to bind to `127.0.0.1`. Do not represent this local mode as production-ready. ([Qdrant security](https://qdrant.tech/documentation/security/), [local quickstart](https://qdrant.tech/documentation/quickstart/))

Use two logical aliases, `finance_education_active` and `tax_education_active`, pointing to immutable physical collections such as `finance_education__v<manifest-id>`. Candidate ingestion never writes through an active alias. Activation and rollback use one atomic `update_collection_aliases` request that deletes the old mapping and creates the new mapping. Qdrant documents alias changes as atomic and specifically recommends this pattern for background model/collection replacement. ([Qdrant collections and aliases](https://qdrant.tech/documentation/manage-data/collections/))

For representation experiments, use this bounded shortlist:

1. Dense baseline: `BAAI/bge-small-en-v1.5`.
2. Dense comparator: `sentence-transformers/all-MiniLM-L6-v2`.
3. Sparse baseline: `Qdrant/bm25` with Qdrant's IDF modifier.
4. Sparse neural comparator, only if CPU time and memory remain acceptable: `prithivida/Splade_PP_en_v1`, without the Qdrant IDF modifier.

Run dense-only, sparse-only, and dense+sparse RRF on the same frozen Finance and Tax qrels. Choose per logical KB and query class under EVAL-07; do not enable hybrid globally merely because the database supports it. Record index/build time, peak resident memory, corpus size, query p50/p95, Recall@5, MRR/nDCG, and exact-filter/citation results.

For the initial source corpus, prefer curated, page-level-approved IRS, SEC/Investor.gov, and CFPB material. Keep FINRA material out of the embedded corpus until a human records explicit permission or a source-specific license that covers copying, local storage, vectorization, and application delivery.

## Qdrant contract for M1

### Hosting and persistence

Qdrant's Docker examples mount `/qdrant/storage`, expose REST on 6333 and optionally gRPC on 6334, and persist data outside application runtime. Docker is recommended for development/testing. Production guidance adds authentication, network isolation, TLS, audit logging, backups, and resilience; those controls are outside M1 except that the local-only boundary must be truthful. ([installation](https://qdrant.tech/documentation/install/), [security](https://qdrant.tech/documentation/security/))

M1 should therefore provide a pinned Compose service, a persistent volume, a health check, and loopback-only published ports. Application startup may inspect collections but must not create a collection, fetch sources, download models, or generate embeddings.

### Named dense and sparse vectors

Qdrant allows several named vectors on one point, with independent size and distance settings, and a separate sparse-vector configuration. The current Python client shape is:

- `create_collection(..., vectors_config={"dense": models.VectorParams(...)}, sparse_vectors_config={"sparse": models.SparseVectorParams(...)}, metadata={...})`;
- `upload_points`/`upsert` with a point `vector` mapping containing the named dense vector and `models.SparseVector`;
- `query_points(..., using="dense")` or `query_points(..., using="sparse")` for individual strategies.

The official examples use `sparse_vectors_config` for collection creation and dictionaries of named vectors for points. Sparse fields do not declare a fixed dimension; the dense field must match the selected model's documented dimension and distance behavior. ([vectors](https://qdrant.tech/documentation/manage-data/vectors/), [points](https://qdrant.tech/documentation/manage-data/points/), [collections](https://qdrant.tech/documentation/manage-data/collections/))

Use stable names `dense` and `sparse` for the first candidate. Do not encode model names in vector field names; model identity belongs in immutable collection metadata and the collection manifest. A model change creates a new physical collection under ADR-017.

For `Qdrant/bm25`, configure `models.SparseVectorParams(modifier=models.Modifier.IDF)`. Qdrant warns that BM25 and miniCOIL require the IDF modifier, while SPLADE already carries learned corpus-level term weighting and must not receive the modifier a second time. ([Qdrant sparse tuning prerequisites](https://qdrant.tech/documentation/search-tuning/before-tuning-a-qdrant-collection/), [sparse indexing](https://qdrant.tech/documentation/manage-data/indexing/))

### Payload indexes

Create indexes only for fields used in filters or deterministic lookup; Qdrant notes that payload indexes improve filter planning but consume compute and memory. The M1 minimum is:

| Payload field | Qdrant index | M1 purpose |
| --- | --- | --- |
| `logical_kb`, `status`, `publisher`, `source_type`, `jurisdiction` | keyword | scope and provenance filters |
| `document_id`, `document_version`, `chunk_id`, `content_hash` | keyword | deterministic identity, change detection, and citation lookup |
| `tax_year` | integer | exact historical Tax filtering |
| `effective_from`, `effective_to`, `fetched_at`, `reviewed_at` | datetime | currency and review filters when queried |

Do not index `title`, `canonical_url`, `section_path`, or unrestricted text until a measured query/filter requires it. Use `create_payload_index(collection_name, field_name, field_schema)` and verify returned `payload_schema` from `get_collection`. Qdrant supports keyword, integer, float, bool, geo, datetime, text, and UUID payload indexes. ([indexing](https://qdrant.tech/documentation/manage-data/indexing/), [Python client API](https://python-client.qdrant.tech/qdrant_client.async_client_base))

### Collection metadata and readiness

Qdrant supports custom collection metadata at creation and update, returns it through collection info, and merges updates by key. Store at least:

- payload schema version and collection manifest hash;
- dense model name, immutable artifact/revision identifier, dimension, and distance;
- sparse model name, immutable artifact/revision identifier, and modifier policy;
- FastEmbed, qdrant-client, and Qdrant server versions;
- chunk-policy and ingestion-code versions;
- source-manifest hash and qrels/evaluation version;
- candidate/validated state, validation timestamp, and activation-record identifier.

Custom collection metadata is available from Qdrant 1.16.0. ([collection metadata](https://qdrant.tech/documentation/manage-data/collections/))

Runtime readiness should resolve each active alias, call `get_collection`, and reject the collection unless all of these are true:

1. the alias exists and resolves to one physical collection;
2. required named dense/sparse fields and their configuration match application expectations;
3. required payload indexes and metadata keys match the expected schema/model/chunk versions;
4. the application-owned state says the candidate passed schema, filter, citation, and retrieval gates;
5. Qdrant reports no unrecoverable status and indexing has settled for the collection's configured thresholds.

`green` means Qdrant is ready and `yellow` means optimization is running, but `green` alone is not the product activation gate. Qdrant also cautions that `points_count` and `indexed_vectors_count` are approximate, that named vectors can make vector counts exceed point counts, and that small collections may correctly keep `indexed_vectors_count == 0` because HNSW is not built below the threshold. Readiness must use configuration-aware checks rather than strict count equality. ([collection info](https://qdrant.tech/documentation/manage-data/collections/), [bulk-ingestion completion](https://qdrant.tech/documentation/production-operations/bulk-data-import/), [pre-tuning checks](https://qdrant.tech/documentation/search-tuning/before-tuning-a-qdrant-collection/))

### Hybrid/RRF queries

The Query API supports multi-stage search from Qdrant 1.10. Its `prefetch` list runs dense and sparse candidate searches, after which the main query fuses rankings. In Python, use `query_points` with two `models.Prefetch` entries and `models.RrfQuery(rrf=models.Rrf())`; each prefetch must request enough candidates for the final `limit + offset`. Qdrant also supports DBSF, but ADR-005 and the M1 test plan specifically require RRF comparison, so DBSF is not part of the initial matrix. ([hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/))

Freeze and report prefetch limits, final top-k, RRF parameters, filters, and any relevance threshold. The same candidate collection and qrels must be used for dense, sparse, and hybrid comparisons.

### Local FastEmbed integration

FastEmbed uses ONNX Runtime, is designed as a lightweight local embedding library, and runs models inside the Python application. `qdrant-client[fastembed]` can embed `models.Document` objects locally; direct FastEmbed APIs expose `TextEmbedding` and `SparseTextEmbedding`. ([FastEmbed overview](https://qdrant.tech/documentation/fastembed/), [FastEmbed package quickstart](https://pypi.org/project/fastembed/), [Qdrant local inference](https://qdrant.tech/documentation/embeddings/fastembed/))

For M1, prefer direct FastEmbed generation inside the offline ingestion application, then upload explicit named vectors. This keeps model download, batching, failure handling, and artifact hashing outside runtime and makes the collection manifest reproducible. The application service should not call `set_model`, pass `models.Document` for implicit embedding, or enable cloud inference. Qdrant documents that `cloud_inference=True` switches to its hosted inference service, while the Python client's default inference path is local FastEmbed. ([Qdrant Cloud inference](https://qdrant.tech/documentation/embeddings/qdrant-cloud-inference/))

## Candidate representation models

Qdrant's current FastEmbed 0.9.1 registry is the authoritative support list used here. It says the installed FastEmbed version controls model availability and publishes dimensions/licenses from that release's model registry. ([supported models](https://qdrant.tech/documentation/embeddings/fastembed/))

| Candidate | Kind | Dimension | Registry license | M1 role and caveat |
| --- | --- | ---: | --- | --- |
| `BAAI/bge-small-en-v1.5` | dense | 384 | MIT | Default dense baseline. It is FastEmbed's documented quickstart default and has a small 384-d vector. Benchmark CPU/RAM and confirm query/document preprocessing and distance from the installed registry/model card. |
| `sentence-transformers/all-MiniLM-L6-v2` | dense | 384 | Apache-2.0 | Comparator with the same vector width and a permissive registry license. Do not assume equal quality merely from equal dimensions. |
| `ibm-granite/granite-embedding-small-english-r2` | dense | 384 | Apache-2.0 | Reserve comparator only if the first two are tied or fail a query class; adding every supported model would expand M1 without evidence. |
| `Qdrant/bm25` | sparse lexical | variable/no declared dense dimension | Apache-2.0 | Default sparse baseline for form numbers, tax terms, and identifiers. Requires Qdrant IDF modifier and measured tokenizer/average-length configuration. |
| `prithivida/Splade_PP_en_v1` | sparse neural | variable/no declared dense dimension | Apache-2.0 | Optional neural sparse comparator. Do not add Qdrant IDF. Include only if local CPU/memory and indexing time fit the M1 budget. |

“CPU-friendly” is a hypothesis to measure, not a documented acceptance fact. FastEmbed's ONNX implementation and the 384-dimensional dense candidates make these reasonable local candidates, but the repository still needs measurements on the supported developer/CI hardware. Before activation, pin the package versions plus immutable model artifacts or revisions and hashes; a model name alone is not a reproducible version. Recheck the upstream model card and distributed artifacts even when the FastEmbed registry lists a permissive license.

Avoid non-commercial model licenses for the baseline. For example, the same registry lists `jinaai/jina-embeddings-v3` as CC-BY-NC-4.0; it is not in the shortlist.

## Source/use policy findings

This is engineering research, not legal advice. “Public domain” addresses copyright but does not waive trademarks, endorsement restrictions, privacy obligations, access controls, or third-party rights. Every SourceRegistry entry still needs a named reviewer, review date, canonical URL, content owner, use notes, and a decision covering local storage, transformation/vectorization, excerpts/citations, redistribution in responses, and model/evaluation fixtures.

| Candidate authority | Official policy finding | M1 disposition |
| --- | --- | --- |
| IRS | IRS says content created or maintained by federal employees in their duties is not copyrighted and may be freely copied; credit is requested. Copyrighted material on or linked from the site requires consulting the copyright holder. Treasury/IRS names, seals, and symbols cannot be used to imply endorsement. IRS internal publishing guidance separately confirms that employee-created official publications without copyrighted inclusions are not subject to copyright. ([IRS.gov content policy](https://www.irs.gov/about-irs/use-of-content-from-irsgov), [IRM 1.17.8](https://www.irs.gov/irm/part1/irm_01-017-008)) | Preferred Tax corpus. Curate current and historical IRS-authored publications/instructions, preserve tax year/effective status and attribution, exclude seals and third-party inserts. Human page/document review remains required before registry approval. |
| SEC / Investor.gov | SEC says information on sec.gov is public information that may be copied or further distributed; government-created content and EDGAR public filing content are free to access and reuse. Exceptions include some stock art. SEC marks/logos may not be used without a license. SEC also limits automated access to at most 10 requests/second and asks scripts to download only what they need. Investor.gov identifies itself as SEC investor education and warns its material is educational, not a legal interpretation or SEC policy. ([SEC dissemination policy](https://www.sec.gov/files/privacy.htm), [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions), [SEC automated-access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data), [Investor.gov disclaimer](https://www.investor.gov/disclaimer)) | Preferred Finance corpus for curated SEC/Investor.gov educational pages. Attribute, preserve the educational disclaimer, exclude artwork/logos and any page-level copyrighted content. Use a bounded fetcher with a descriptive user agent and a rate far below 10 requests/second. EDGAR filings are not needed for M1 education and would add provenance/privacy/volume complexity. |
| CFPB | CFPB says information it creates is public domain and may be reproduced, published, or otherwise used without permission, with citation requested. Materials created outside CFPB may remain protected; CFPB names/logo are registered trademarks. ([CFPB website policy](https://www.consumerfinance.gov/privacy/website-privacy-policy/)) | Preferred Finance corpus for CFPB-authored financial-fundamentals material. Approve individual pages/documents, cite CFPB, exclude third-party inclusions and trademarks, and record the page's revision/review date. |
| FINRA | FINRA is not a federal agency and its general website terms describe copyrighted/proprietary material, prohibit bulk data mining/copying, and require express permission for copying, redistribution, publication, or commercial exploitation except where law allows. Its API terms grant only specific licensed uses and prohibit scraping or using licensed material beyond written permission; source-specific terms can add restrictions. ([FINRA website terms reproduced in its official entitlement statement](https://www.finra.org/sites/default/files/Entitlement_Program_Privacy_Statement.pdf), [FINRA API terms](https://developer.finra.org/finra-api-terms-service)) | Do not ingest FINRA page text into M1 by default. A human must obtain/record permission or a source-specific license that expressly covers the planned RAG uses. Until then, FINRA may be kept only as a proposed source with `permitted_use=pending`, not fetched, embedded, or used in qrels. |
| General federal-work rule | U.S. Copyright Office guidance explains that works prepared by federal officers/employees as part of official duties are not protected by U.S. copyright under 17 U.S.C. §105, while the government can hold copyrights transferred to it and a federal-hosted item is not necessarily a government work. ([17 U.S.C. §105](https://www.copyright.gov/title17/92chap1.html#105), [Copyright Office Compendium §313.6(C)](https://www.copyright.gov/comp3/chap300/ch300-copyrightable-authorship.pdf)) | Supports the IRS/SEC/CFPB analysis but is not a blanket approval. Record authorship and third-party notices per document. |

### Proposed initial source slices

Keep the first corpus small enough for manual review and fixed qrels:

- Tax Education: current and selected historical versions of IRS-authored Publication 17 (general individual tax), Publication 505 (withholding/estimated tax), Publication 550 (investment income/expenses), and Publications 590-A/590-B (IRAs), limited to sections that map to approved M1 questions. Each tax-year edition is a distinct document version; “current” never overwrites history.
- Finance Education: selected SEC/Investor.gov pages covering saving/investing basics, diversification/asset allocation, fees, fund/product fundamentals, fraud red flags, and the limits of educational information; selected CFPB-authored pages/toolkit sections covering budgeting, credit, debt, and emergency savings where relevant to product requirements.
- Deferred: FINRA articles, third-party images/videos, jointly authored materials whose ownership is unclear, interactive calculators, user comments, linked external pages, EDGAR filings, and any page without a completed permitted-use record.

The source registry should distinguish `approved`, `pending_review`, `rejected`, `withdrawn`, and `quarantined`. Discovery can register a pending URL, but fetch/embedding must require `approved`. Removal or changed rights should deactivate affected documents and trigger a new candidate collection; it must not silently mutate the active collection.

## Decisions still requiring evidence or approval

1. **Hosting pin acceptance.** Run the M1 compatibility/security smoke test for Qdrant server/client 1.20.0 and FastEmbed 0.9.1, then record the exact container digest and lockfile. If the newly released set is unstable, select a tested older patch set explicitly rather than using `latest`.
2. **Model artifact pinning.** Confirm how the ingestion build will resolve immutable Hugging Face/model artifacts offline and record their hashes. Package pinning alone does not freeze weights/tokenizers.
3. **Dense preprocessing and distance.** Confirm query/document prefixing, normalization, maximum input length, truncation, and distance metric from the exact installed model registry/model artifact; test these as collection compatibility fields.
4. **BM25 token statistics.** Measure tokenizer output and average document length on each logical KB. Qdrant warns that raw-word estimates can materially misconfigure BM25.
5. **Hardware budget.** Define supported CPU/RAM and maximum acceptable ingestion and query latency before choosing SPLADE or a second dense model for activation.
6. **Chunking and ranking parameters.** Freeze structure-aware chunk policy, overlap, prefetch limits, top-k, RRF configuration, and relevance thresholds only after the fixed qrels exist.
7. **Permitted-use sign-off.** Name the person authorized to approve SourceRegistry entries. Complete per-document review for IRS, SEC/Investor.gov, and CFPB, and obtain explicit permission before any FINRA ingestion.
8. **Fetch etiquette.** Store per-domain user agent, request rate, retry/backoff, conditional-request, robots/terms review, and maximum scope. SEC's published 10 requests/second is a ceiling, not a target.
9. **Rollback retention.** Set the bounded period/count for retaining the previous physical collection and the evidence that permits its eventual deletion.
10. **Activation tolerances.** Define the approved no-regression tolerance and resource/latency budgets in addition to the existing Recall@5 and critical filter/citation gates.

Until these items are resolved, M1 can implement the ingestion seams, manifests, candidate lifecycle, and experiments, but it must not describe a model/source set as approved or move an active alias.
