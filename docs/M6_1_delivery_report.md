# M6.1 delivery report — Evidence-bound response cache

Status: Implementation complete; semantic serving remains review-gated | 2026-10-31

## Scope and decisions

This slice implements ADR-028 for QR-001, QR-004, QR-006, QR-007, QR-010, QR-012, QR-014, and QR-015. Per the approved scope change, eligibility covers both standalone public Finance Q&A and U.S. Tax Education. Portfolio, Market, News, Goals, multi-agent, context-bearing, checkpoint-dependent, personalized, unsuccessful, and unqualified requests bypass the response cache.

Tax reuse requires an exact resolved tax year and U.S. federal jurisdiction. Both RAG agents perform current retrieval before generation lookup, and a hit requires the current evidence fingerprint. Exact route reuse is possible only after a prior classifier result explicitly marked that same single-agent request `public_rag`; semantic matching never bypasses the classifier.

## Delivered implementation

- Deep application-owned `ModelResponseCache` seam with disabled, unavailable/fail-open, deterministic in-memory, and Redis 8/RedisVL adapters.
- Versioned cache policy `public-rag-evidence-bound-v2`, schema `1`, maximum 24-hour TTL, and configurable minimum cosine similarity `0.92`.
- Opaque SHA-256 Session scope; normalized query; exact agent/provider/model/prompt/workflow/schema/policy/locale/jurisdiction/tax-year/evidence filters.
- Evidence fingerprint over active collection versions and ordered chunk identifiers, document/content versions, hashes, and rank. Citations always come from current retrieval, never from the cached payload.
- Exact route and generation reuse, shadow/serving semantic modes, schema revalidation, corruption/outage bypass, and process-local keyed coalescing.
- Loopback-only non-persistent Redis Compose service pinned by tag and digest, with 256 MiB memory bound and LRU eviction.
- Session archive, permanent deletion, expiry, and token-protected administrative purge integration.
- Privacy-filtered `model_response_cache` RunEvents and OpenTelemetry measurements. Hits suppress model lifecycle events only for the provider work actually avoided.
- Frozen Finance-and-Tax calibration set, deterministic workflow benchmark, opt-in Redis integration suite, and safe test defaults in `.test.env`.

## Verification results

| Command/check | Actual result |
|---|---|
| `.venv/bin/ruff format --check src tests` | 128 files formatted |
| `.venv/bin/ruff check src tests` | passed |
| `.venv/bin/mypy` | passed for 128 source/test files |
| `.venv/bin/pytest -q` | 256 passed, 1 skipped, 4 deselected in 2.93 s |
| `UV_CACHE_DIR=/tmp/aifa-uv-cache UV_NO_SYNC=1 make m6-1-check` | static gates passed; 59 tests passed in 1.74 s |
| Real RedisVL integration test with `AIFA_TEST_REDIS_URL` | 1 passed in 0.26 s |
| `uv pip check --python .venv/bin/python` | 112 packages compatible |
| Redis runtime configuration inspection | `save` empty; `appendonly no`; 256 MiB; `allkeys-lru`; loopback-published port |
| FastEmbed calibration at `0.92` | 23 cases; 15 eligible; 2 proposed hits; 0 critical false hits; 2 awaiting review; serving gate false |
| Deterministic full-workflow benchmark | exact p50/p95 8.23/9.10 ms; semantic 21.55/22.68 ms; disabled 33.32/34.03 ms; near miss 34.73/34.99 ms |

The first `make m6-1-check` attempt could not initialize uv's user cache because the managed sandbox denied `/Users/tvishal/.cache/uv`; an isolated empty cache then could not reach PyPI. This was an environment permission/network failure, not a quality-gate failure. The target passed with the existing synchronized environment, `UV_NO_SYNC=1`, and a writable temporary cache. The ordinary suite's one skip and four deselections are the intended opt-in external integration/live markers; the Redis-marked test passed separately.

## Acceptance evidence

- Finance and Tax workflow tests prove that a second exact qualified request creates a new Run, repeats current retrieval, preserves evidence/citations, and makes no routing or generation model call.
- Cross-Session, context, checkpoint, multi-agent, Portfolio, Market, News, Goal, Tax-year, jurisdiction, evidence, provider/model/prompt/workflow/policy/schema/encoder, and instruction changes cannot reuse an entry.
- Below-cutoff candidates miss. Shadow hits expose no payload and do not suppress generation.
- Malformed payload and unavailable-adapter tests return bounded cache errors while the workflow retains its normal model path.
- Concurrent identical same-scope misses are coalesced in the documented process boundary.
- Archive/delete/admin/TTL tests remove the applicable namespace.
- Event tests reconcile cache hit status, current retrieval, and the absence of fabricated model-start/model-complete events.
- The benchmark shows equivalent deterministic summaries and current citations across disabled, exact, semantic, and near-miss paths, with model-call counts matching the expected work.

## Security and privacy impact

The cache adds a short-lived copy of a normalized public education query and schema-validated model output. It does not store raw Session/Run identifiers, prompts, context references, portfolio/provider payloads, retrieved evidence, or citations. Session scope is one-way and cross-Session reuse is prohibited. Redis is local, non-persistent, bounded, purgeable, and optional; its failure cannot alter financial results. Cache contents and retrieved/model text remain untrusted and are validated outside prompts.

## Limitations and unresolved release work

- Semantic serving is intentionally **not enabled**. Two expected paraphrases crossed `0.92` and still require recorded human approval. The safe example configuration uses `shadow`; exact qualified reuse can operate in that mode.
- The benchmark uses deterministic model latency and test vectors. M8 must repeat it with the selected live model, active collections, representative hardware, and cost methodology.
- LangSmith correlation was not exercised with credentials in this slice. RunEvent and in-memory OpenTelemetry behavior are covered; M8 owns correlated live evidence.
- Coalescing is process-local. A multi-worker/public deployment would need an approved distributed strategy.
- Redis is not an authentication or durable record system. Public/managed hosting and production retention remain undecided.
- A container/dependency vulnerability scanner was unavailable; M8 must scan the pinned artifacts before release qualification.

## Artifacts

- [ADR-028](02_architecture_decision_records.md#adr-028-evidence-bound-redis-response-cache--accepted)
- [Dependency and infrastructure record](research/M6_1_response_cache_dependencies.md)
- [Semantic calibration report](evidence/M6_1_semantic_calibration.md)
- [Deterministic workflow benchmark](evidence/M6_1_response_cache_benchmark.md)
- `backend/data/response-cache/semantic-calibration.v1.json`
- `backend/src/ai_finance_assistant/response_cache/`
- `backend/tests/test_response_cache*.py`
- `.env.example`, `backend/.test.env`, `compose.yaml`, and `Makefile`

