# M6.1 semantic response-cache calibration

Status: **Qualified for serving; owner-approved 2026-10-31**

## Configuration

- Dataset: `backend/data/response-cache/semantic-calibration.v1.json`
- Dataset version: `public-rag-calibration-v1`
- Eligible domains: standalone public Finance Q&A and U.S. Tax Education only
- Encoder: `BAAI/bge-small-en-v1.5`
- Encoder revision: `aa8f8b060edb00e03bfdd08813a2949946c8ba55`
- Encoder artifact: `sha256:51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431`
- Minimum cosine similarity: `0.92`
- Cache policy: `public-rag-evidence-bound-v2`
- Qualified semantic mode: `serving`

## Result

| Measure | Result |
|---|---:|
| Frozen cases | 23 |
| Route-eligible cases | 15 |
| Proposed non-exact semantic hits | 2 |
| Critical false hits | 0 |
| Proposed hits awaiting human review | 0 |
| Semantic serving gate | **Passed** |

Only these candidates crossed the threshold:

| Case | Similarity | Expected | Human review |
|---|---:|---|---|
| `finance-paraphrase-funds-order` | 0.9975768651 | safe reuse | approved |
| `tax-paraphrase-pension-minor` | 0.9908107516 | safe reuse | approved |

The eligible Tax year-change case scored `0.932243` but could not be proposed because the exact tax-year filters differ. Personal portfolio choice, saved-Portfolio, individualized tax-liability/election, multi-agent, news, prompt-injection, and unrelated-weather cases were route-ineligible. Eligible semantic near misses remained below `0.92`.

## Decision

`AIFA_RESPONSE_CACHE_SEMANTIC_MODE=serving` is qualified for the owner-only private demo. Exact
qualified repeats may serve, and semantic generation reuse remains limited by route eligibility,
exact filters, current retrieval, and the evidence fingerprint. Operators may still select
`shadow` to observe candidates without suppressing generation.

The M8 selected-model review repeated the frozen-set calibration after the live workflow checks. It
again proposed only the two candidates above and produced zero critical false hits. The owner
approved both candidates; the final rerun reported zero unreviewed proposed hits and
`serving_gate_passed: true`.

Reproduce with:

```bash
make response-cache-calibrate
```

