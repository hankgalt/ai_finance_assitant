# Release version register

Release ID: `private-demo-2026-10-31`

| Component | Qualified version / identifier |
|---|---|
| Application package | `0.1.0` |
| Workflow | `finance-assistant @ 1` |
| OpenAI model | `gpt-6.1-sol` when live mode is explicitly enabled |
| Agent/routing prompt | `openai-agent-system-v3` / `openai-routing-system-v3` |
| Multi-agent synthesis prompt | `openai-multi-agent-synthesis-v1` |
| MCP adapter | `read-only-mcp-v1`, stdio |
| SQLite application schema | `3` |
| Qdrant image | `qdrant/qdrant:v1.20.0` |
| Finance collection | `finance_education_v1_755be30b6a2d`, version `v1-755be30b6a2d`, 18 documents / 106 points |
| Tax collection | `tax_education_v1_9b31ab2354ea`, version `v1-9b31ab2354ea`, 31 documents / 6,295 points |
| Dense embedding | `BAAI/bge-small-en-v1.5`, revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`, 384 dimensions |
| Sparse embedding | `Qdrant/bm25`, revision `22b8d2af71a76161e18dd432d2cee0eefa66e412` |
| Chunking / payload schema | `structural-v1` / `1` |
| Portfolio import / calculation | `portfolio-import-v1` / `finance-calculation-v1` |
| Goal / diversification | `goal-projection-v1` / `diversification-hhi-v1` |
| Historical provider cache | schema `1`, policy `historical-daily-v1` |
| Public-RAG response cache | schema `1`, policy `public-rag-evidence-bound-v2`, cutoff `0.92` |
| Redis image | `redis:8.10.2-alpine3.23` with pinned digest in Compose |
| Qualification dataset | `private-demo-release-qualification-v1` |

The exact Python and JavaScript dependency versions are in the lockfiles. The current host
environment and container digests are captured in
[`environment-manifest.v1.json`](../../backend/artifacts/release/environment-manifest.v1.json). A model,
prompt, collection, encoder, policy, schema, or rights change invalidates only the evidence that
declares that dependency and must be requalified before release.
