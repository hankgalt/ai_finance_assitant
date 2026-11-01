# M8 qualification evidence

This directory is the human-readable evidence index for M8. The immutable case map is
`backend/data/evaluation/m8_cases.v1.json`; generated machine reports belong under
`backend/artifacts/m8/` and are intentionally reproducible rather than hand-edited.

- [Qualification summary](qualification-summary.md)
- [Threat model](threat-model.md)
- [Observability data flow](observability-data-flow.md)
- [Signal inventory](signal-inventory.md)
- [Human review worksheet](human-review.md)
- [Operational runbook](operational-runbook.md)
- [Known-risk register](known-risk-register.md)
- [Dependency scan](dependency-scan.md)
- [Coverage report](coverage.md)
- [Benchmark and cost report](benchmark-cost.md)
- [Correlation, redaction, and exporter-failure report](correlation-redaction-exporter.md)
- [Release recommendation](release-recommendation.md)

The report must remain explicit about failed, unavailable, skipped, and human-review-required
evidence. Historical milestone reports are inputs, not substitutes for an M8 rerun.
