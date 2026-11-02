# M8 selected-model review packet

Status: **owner-approved 2026-10-31**  
Model: `gpt-6.1-sol` | Approved/consumed requests: **24/24** | Retries: disabled

## Agent recommendation

The agent recommended approving EVAL-01, EVAL-03, EVAL-08, EVAL-10, EVAL-12, and EVAL-17 for
the private demonstration release. The product owner explicitly accepted that recommendation and
both semantic candidates on 2026-10-31.

## What was exercised

- One synthetic all-six Run selected all six agents and completed bounded specialist execution plus
  synthesis using credential-free market/news fixtures.
- Active-Qdrant Finance, Tax, and Finance+Tax Runs used
  `finance_education_v1_755be30b6a2d` and `tax_education_v1_9b31ab2354ea`.
- Finance answers cited SEC Investor.gov evidence. The 2025 home-sale answer cited IRS Publication
  523 and declined to decide the user's exclusion election or exact filing obligation.
- The guarantee case stated that no investment guarantees high returns without risk.
- The cross-domain case refused to select an ETF or create a personalized tax-minimization plan.
- No fabricated citation or unsupported critical claim was observed in the reviewed synthetic
  outputs; the owner accepted this adjudication.

## Routing defect found and fixed

The first all-six route selected the correct agents but stopped at Portfolio clarification. The
context gate was incorrectly comparing all typed context identifiers with only the Portfolio
subset. It now accepts authorized mixed Portfolio/Market/Goal/News references, retains only the
Portfolio subset as active Portfolio scope, and still rejects unknown or cross-Session identifiers.
A deterministic workflow regression test went red before the fix and passes after it.

## Latency, call, and cost observations

The active-collection sequence used 19,512 input tokens and 2,724 output tokens. Monetary cost is
unavailable because the repository has no approved, versioned price calculator; the usage method
is `openai_reported_v1`.

| Path | Samples | p50 | p95 | Model calls |
|---|---:|---:|---:|---:|
| Cold selected-model Runs | 5 | 7,866.71 ms | 14,539.40 ms | 12 across the sequence |
| Exact evidence-bound hits (LangSmith subset) | 4 | 19.45 ms | 21.37 ms | 0 |
| Exact evidence-bound hits (local full set) | 10 | 23.69 ms | unavailable from retained local aggregate | 0 |
| Semantic probe | 1 | 7,299.34 ms | unavailable for one sample | 2 |

The semantic probe safely missed: the paraphrase retrieved a different current evidence
fingerprint, so the model executed instead of reusing a stale/different answer. The frozen
calibration still has two proposed candidates above `0.92` and zero critical false hits:

- `finance-paraphrase-funds-order` (`0.9975768651`), whose two questions differ only in noun order;
- `tax-paraphrase-pension-minor` (`0.9908107516`), whose two 2025 questions differ only by
  “and” versus “or” and word order.

The owner approved both candidates. The frozen rerun has zero critical false hits, zero unreviewed
proposed hits, and a passing semantic-serving gate.

## Observability reconciliation

LangSmith recorded privacy-hidden root and child Runs (`privacy_mode=inputs_outputs_hidden`). Four
exact-hit roots retained sufficient timing metadata for p50/p95. The short-lived one-shot harness
reported background-export threads at interpreter shutdown, so not every repeated exact-hit trace
was exported; all first-party workflow results and RunEvents completed and product state was not
affected. This is consistent with the optional-exporter failure contract, while the long-lived app
remains the supported operating mode.

The machine-readable, response-free record is
`backend/artifacts/release/live-model-review.v1.json`. It contains identifiers, counts, timings, source
titles/publishers, and decisions, but no credential, system prompt, full generated answer, or user
financial record.
