# M6.1 deterministic workflow benchmark

Measured 2026-10-31 on the development host with 20 samples per path. The benchmark crosses the complete credential-free LangGraph workflow, performs current Finance retrieval, uses a deterministic 10 ms delay for each structured model request, and creates a distinct Run for every sample. It is comparative implementation evidence, not a live OpenAI latency or capacity claim.

| Path | p50 | p95 | Routing calls | Generation calls | Answer/citations equivalent |
|---|---:|---:|---:|---:|---|
| Cache disabled | 33.32 ms | 34.03 ms | 20 | 20 | yes |
| Exact hit | 8.23 ms | 9.10 ms | 0 | 0 | yes |
| Qualified semantic hit | 21.55 ms | 22.68 ms | 20 | 0 | yes |
| Semantic near miss | 34.73 ms | 34.99 ms | 20 | 20 | yes |

Configuration: workflow `1`, policy `public-rag-evidence-bound-v2`, minimum similarity `0.92`, deterministic fixture usage method, monetary cost unavailable. The semantic-hit path used an approved test vector mapping solely to verify the serving mechanism; production configuration remains `shadow` pending the human review in [the calibration report](M6_1_semantic_calibration.md).

Reproduce with:

```bash
make response-cache-benchmark
```

M8 must repeat the benchmark with the release candidate, actual selected model/provider, active Qdrant collections, representative hardware, and cost methodology.

