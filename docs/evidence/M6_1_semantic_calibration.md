# M6.1 semantic response-cache calibration

Status: Shadow evaluation complete; human review pending | 2026-10-31

## Configuration

- Dataset: `backend/data/response_cache/calibration.v1.json`
- Dataset version: `public-rag-calibration-v1`
- Eligible domains: standalone public Finance Q&A and U.S. Tax Education only
- Encoder: `BAAI/bge-small-en-v1.5`
- Encoder revision: `aa8f8b060edb00e03bfdd08813a2949946c8ba55`
- Encoder artifact: `sha256:51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431`
- Minimum cosine similarity: `0.92`
- Cache policy: `public-rag-evidence-bound-v2`
- Semantic mode: `shadow`

## Result

| Measure | Result |
|---|---:|
| Frozen cases | 23 |
| Route-eligible cases | 15 |
| Proposed non-exact semantic hits | 2 |
| Critical false hits | 0 |
| Proposed hits awaiting human review | 2 |
| Semantic serving gate | **Failed pending review** |

Only these candidates crossed the threshold:

| Case | Similarity | Expected | Human review |
|---|---:|---|---|
| `finance-paraphrase-funds-order` | 0.9975768651 | safe reuse | pending |
| `tax-paraphrase-pension-minor` | 0.9908107516 | safe reuse | pending |

The eligible Tax year-change case scored `0.932243` but could not be proposed because the exact tax-year filters differ. Personal portfolio choice, saved-Portfolio, individualized tax-liability/election, multi-agent, news, prompt-injection, and unrelated-weather cases were route-ineligible. Eligible semantic near misses remained below `0.92`.

## Decision

Keep `AIFA_RESPONSE_CACHE_SEMANTIC_MODE=shadow`. Exact qualified repeats may serve; semantic candidates are measured but cannot suppress a model call. Enabling `serving` requires recorded human approval of every proposed hit and a rerun with zero critical false hits. M8 independently repeats this qualification.

Reproduce with:

```bash
make response-cache-calibrate
```

