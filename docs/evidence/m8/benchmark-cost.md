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

Selected-model p50/p95, tokens, monetary-cost availability/method, and the current model-backed
routing/synthesis path require a newly approved external-call budget. EVAL-17 therefore remains
`review_required`, semantic mode remains `shadow`, and these deterministic numbers are not used to
open the private-demo release gate.
