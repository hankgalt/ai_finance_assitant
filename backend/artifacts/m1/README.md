# M1 evidence bundle

Current active collections at M1 completion:

- Finance: `finance_education_v1_2fdf182ee6ab`
- Tax: `tax_education_v1_4cf0dfd5f870`

For each collection, `.manifest.json` records source/document versions and the ready collection contract, `.evaluation.json` records the dense/sparse/hybrid comparison, and `.run.json` records initial activation. Timestamped `.run-*.json` files are unchanged reruns and must show `created: false` and `points_written: 0`.

The `rollback-tax_education-20261027T224905Z.json` and `rollback-tax_education-20261027T224906Z.json` files are the retained rollback-and-restore transcript. The current Tax run record preserves `tax_education_v1_77e7f3e03d50` as its previous collection. Earlier collection generations and rollback files are retained as development and recovery evidence; they are not the active release candidates.
