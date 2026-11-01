# M8 signal and attribute inventory

| Surface | Signals | Allowed dimensions or payload | Explicitly excluded |
|---|---|---|---|
| HTTP | request count, error count, duration | route template, method, status class | URL, query, Session/Run ID, body |
| Persistence | operation count/duration | operation, result status | records, identifiers, SQL |
| Provider/tool | count/duration/failure | provider, operation, result/failure category, cache status | credentials, raw payload, symbol from user context |
| Retrieval | count/duration | strategy, collection version, result status, source count | query text and chunk text |
| Model | lifecycle RunEvents and spans | model ID, prompt version, result status; usage/cost with availability and method | prompt, response, hidden reasoning |
| Response cache | lookup/store count/duration and tool RunEvents | operation, outcome, match kind, policy/semantic mode; bounded age/similarity buckets | raw query, Session/Run ID, reason strings, cached answer |
| Frontend | navigation, web vital, API count/duration | allow-listed page, metric, rating, route, method, status class | content, labels, identifiers, URL |
| Inspector | persisted RunEvents | event identity/order, safe routing/tool/retrieval/usage metadata, safe errors | chain of thought, credentials, raw financial/provider payloads |

Metric series cardinality is bounded by enums, route templates, versions, and provider identifiers.
The M8 suite submits many unique synthetic Session identifiers and requires one metric dimension set.
Unknown attributes are dropped rather than dynamically promoted.
