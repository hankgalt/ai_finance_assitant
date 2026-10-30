# M6 contract-version record

- Authority: FastAPI OpenAPI generated from the backend application.
- Manifest: `contracts/m6-frontend-contract.v1.json`.
- Frontend type record: `frontend/src/types/contracts.ts`.
- Schema version: 1.

`backend/tests/test_m6_contract_manifest.py` proves every required path/method exists in OpenAPI and
every required consumer type is present. The M5 manifest remains a subset contract so the M6
telemetry resource can be added without weakening any M5 path assertion.

The M6 manifest requires Session list/get/delete plus
`POST /api/v1/sessions/{session_id}/archive`. The frontend clear action therefore transitions the
authoritative Active Session to Archived instead of clearing only browser state. Archived history
uses Session and Run reads; separately confirmed permanent deletion uses the guarded M5 cascade.

File bytes use `content_base64` only at the JSON transport boundary. The backend immediately
converts them into the existing M2 `PortfolioImportRequest`; parser, size, schema, provenance, and
no-silent-correction rules are unchanged.
