# M6.1 response-cache dependency and infrastructure record

Status: Implemented private-demo selection | 2026-10-31

## Decision scope

This record supports ADR-028 and M6.1. It approves a loopback-only, non-persistent Redis adapter for the owner-operated private demo. It does not approve a managed/public topology, public multi-user retention, or semantic serving before calibration review.

## Selected components

| Component | Pin | Integrity/identity | Role |
|---|---|---|---|
| Redis Open Source | `8.10.2-alpine3.23` | multi-architecture digest `sha256:9f8d2d789b9a1d1e3f283f979aa9cbf393373806472e1ccd460e2f9c869b833b` | loopback cache and vector-search index |
| RedisVL | `0.28.0` | wheel `sha256:0f013853a54219651355ec3a6c5a3d2c5cdf02935ffc0aa27c9cb80e2023d306` in `uv.lock` | filtered semantic-cache adapter |
| redis-py | resolved by `uv.lock` through RedisVL | locked transitive dependency | Redis protocol client |
| FastEmbed | `0.9.1` from the lock | wheel `sha256:95042ac7f685bda6697861066d49f8b119fbde8b75ed5162bbb7e84e2dad0e1d` | local query vectors; no external embedding request |
| Dense encoder | `BAAI/bge-small-en-v1.5` | revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`; artifact `sha256:51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431` | 384-dimensional semantic comparison shared with M1 |

RedisVL's `SemanticCache` supports TTL, a caller-selected vectorizer, a caller-selected cosine-distance threshold, and filterable fields. The application supplies the pinned local encoder and exact Session/policy/evidence filters instead of accepting library defaults. RedisVL documents cosine distance on `[0, 2]`; the application converts configured minimum cosine similarity `s` to maximum distance `1 - s`.

Primary references:

- [RedisVL `SemanticCache` API](https://docs.redisvl.com/en/latest/api/cache.html)
- [Redis Open Source installation](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/)
- [Redis persistence](https://redis.io/docs/latest/management/persistence/)
- [Redis licensing](https://redis.io/legal/licenses/)
- [RedisVL source and maintenance statement](https://github.com/redis/redis-vl-python)
- [RedisVL package registry record](https://pypi.org/project/redisvl/)

## License review

Redis 8 offers RSALv2, SSPLv1, or AGPLv3; the private demo consumes the unmodified official image and selects the AGPLv3 option. RedisVL and redis-py are MIT licensed according to Redis's license registry. This is an engineering record, not legal advice. Image redistribution, modification, a hosted public service, or a changed commercial posture requires a fresh legal/rights review.

## Local resource and security posture

- Compose publishes only `127.0.0.1:6379`; it is not a public listener.
- RDB snapshots and AOF are disabled (`save ""`, `appendonly no`); no cache volume is mounted.
- Memory is bounded at 256 MiB with `allkeys-lru`; every application record has a TTL no longer than 24 hours.
- Stored Session identity is a one-way opaque scope. Raw Session/Run identifiers, system prompts, context references, portfolio/provider payloads, and citations are excluded.
- Redis is optional. Connection, timeout, corrupt-entry, or incompatible-index failures become visible cache bypasses and do not fail the financial workflow.
- Cached payloads are revalidated against closed Pydantic schemas. Exact metadata filters and a current-evidence fingerprint are checked before reuse.
- Archive, permanent Session deletion, expiry, and a token-protected administrative endpoint purge cache entries.
- The image digest and Python lock hashes prevent silent dependency drift. A vulnerability scanner was not available in this milestone environment; M8 must run the dependency/container scan before release qualification.

## Qualification result

The pinned image started successfully on 2026-10-31. `redis-cli CONFIG GET` confirmed `save` empty, `appendonly no`, `maxmemory 268435456`, and `maxmemory-policy allkeys-lru`. The opt-in real-Redis test passed and verified filtered exact/semantic lookup, Session isolation, and purge. Ordinary tests keep the cache disabled and do not require Docker or credentials.

