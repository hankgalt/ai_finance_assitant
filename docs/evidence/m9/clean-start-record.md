# M9 clean-start and command record

Date: 2026-10-31  
Host: macOS 26.6.2 arm64  
Boundary: existing clean-toolchain host, fresh locked dependency synchronization; not a fresh VM

## Reproduction commands

```text
uv sync --frozen
pnpm install --frozen-lockfile
docker compose config --quiet
make knowledge-validate
make m9-check
```

The first four commands validate locked dependency resolution, Compose syntax, and already-active
knowledge contracts. They do not delete local volumes, databases, or caches. A truly blank Qdrant
volume additionally requires the deliberately networked offline `make knowledge-finance` and `make
knowledge-tax` ingestion steps documented in the developer guide; runtime never performs them.

## Actual results

- `uv sync --frozen`: passed; 125 locked packages checked.
- `pnpm install --frozen-lockfile`: passed; lockfile already current under pnpm 11.25.0.
- `docker compose config --quiet`: passed with no diagnostics.
- `make knowledge-validate`: passed; the Finance and Tax aliases resolve to
  `finance_education_v1_755be30b6a2d` and `tax_education_v1_9b31ab2354ea`.
- `make m9-check`: passed. Frontend coverage was 80.25% lines; the full runner reported 274 backend
  tests passed, 1 skipped, 4 opt-in deselected, 35 frontend tests, 9 Chrome journeys, 1 Qdrant and
  1 Redis integration check, zero critical failures/incomplete dimensions, and
  `release_gate_passed: true`. The post-run MCP/release audit passed 7 tests in 2.37 seconds and
  Compose validation passed.

No external provider/model call is required by this record. Live tests remain explicitly marked and
excluded. The final command regenerates the M8 qualification report, runs the MCP/release-bundle
checks, measures frontend coverage, and validates Compose configuration.
