# M8 latency and cost report

## Credential-free release-candidate measurement

The frozen M6.1 workflow benchmark used 20 samples per path on this development host, the active
Finance retrieval seam, and a deterministic 10 ms model delay:

| Path | p50 | p95 | Routing calls | Generation calls | Equivalent answer/citations |
|---|---:|---:|---:|---:|---|
| Cache disabled | 33.32 ms | 34.03 ms | 20 | 20 | yes |
| Exact hit | 8.23 ms | 9.10 ms | 0 | 0 | yes |
| Qualified semantic hit | 21.55 ms | 22.68 ms | 20 | 0 | yes |
| Semantic near miss | 34.73 ms | 34.99 ms | 20 | 20 | yes |

This demonstrates the implementation's relative call/latency behavior and was re-covered by M8's
backend plus real-Redis suites. It is not an OpenAI latency/cost claim. Monetary cost is unavailable
because no versioned provider price calculator is approved; token availability/method remains
explicit in RunEvents.

## Selected-model review

The approved M8 run used `gpt-6.1-sol`, active Finance/Tax collections, the pinned local encoder,
and a dedicated Redis index. Five cold Runs measured p50 **7,866.71 ms** and p95 **14,539.40 ms**.
Four privacy-hidden LangSmith exact-hit traces measured p50 **19.45 ms** and p95 **21.37 ms**;
the full local set contained ten exact hits with p50 **23.69 ms** and zero model calls. The
active-collection sequence recorded 19,512 input and 2,724 output tokens. Monetary cost remains
unavailable because no approved versioned price calculator is configured.

The live paraphrase safely missed because current retrieved evidence fingerprints differed. The
frozen calibration reports two owner-approved equivalent paraphrases, zero critical false hits,
zero unreviewed proposed hits, and a passing serving gate. The owner approved EVAL-17. Details are in
[the selected-model review packet](live-model-review.md).
