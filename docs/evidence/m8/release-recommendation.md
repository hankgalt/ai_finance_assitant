# M8 release recommendation

Status: **not yet recommended**

The automated candidate has no critical automated defect: backend, frontend, browser, Qdrant,
Redis, redaction/cardinality, and dependency gates pass. The private-demo release recommendation
nevertheless remains blocked by six explicit review dimensions: current live-model routing,
conditional multi-agent synthesis, claim/citation support, groundedness, financial safety, and
selected-model latency/cost.

Semantic cache serving also remains blocked until both proposed semantic hits receive human
approval and the selected-model qualification is recorded; keep semantic mode `shadow`. This is
not a public-production decision. The production-hardening register independently blocks public
deployment even after a future private-demo recommendation.
