# M1 evidence bundle

Current active collections after the 2026-10-31 governed corpus-breadth, direct-source coverage, and requested IRS publication closure updates:

- Finance: `finance_education_v1_755be30b6a2d` (18 documents / 106 chunks)
- Tax: `tax_education_v1_9b31ab2354ea` (31 documents / 6,295 chunks)

For each collection, `.manifest.json` records source/document versions and the ready collection contract, `.evaluation.json` records the dense/sparse/hybrid comparison, and `.run.json` records initial candidate creation. Timestamped `.run-*.json` files record unchanged evaluations and activation; unchanged runs must show `created: false` and `points_written: 0`.

The timestamped activation records for the current collections preserve `finance_education_v1_fcecb8c15493` and `tax_education_v1_f2fef46b0f88` as their immediate rollback targets. The `rollback-tax_education-20261027T224905Z.json` and `rollback-tax_education-20261027T224906Z.json` files remain the retained exercised rollback-and-restore transcript. Earlier collection generations and rollback files are retained as development and recovery evidence; they are not active release candidates.
