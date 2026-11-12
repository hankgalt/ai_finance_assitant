# Deployed knowledge-release evidence

`make knowledge-release-staging` writes one revision-scoped JSON record here after it transfers
and qualifies the approved Finance and Tax collection snapshots. The record contains collection
names, point counts, temporary snapshot checksums, fixed-qrels results, alias activation and
rollback transitions, runtime read/write permission outcomes, and release-key cleanup status.
It also records the reduced, non-secret Cloud Run readback proving that provider and model modes
remain credential-free and that no live-provider credential or approval environment is present.

Snapshot files and API-key payloads are execution-scoped and must never be committed. A complete
record has `status: qualified`, reports no secret payloads, and confirms that the temporary Qdrant
release key was revoked and its Secret Manager version was destroyed.

The current qualified staging record is
`staging-release-a737f8e9e935f8afc05e16fc7148e3a185b32086.json`. Later releases must create a new
revision-scoped record rather than overwrite this evidence.

`make rotate-qdrant-runtime-key-staging` writes a separate
`staging-runtime-key-rotation-<revision>-v<old>-to-v<new>.json` record. A complete rotation record
has `status: qualified`, proves the new credential reads the exact active collections but receives
HTTP 403 on a non-mutating write probe, limits Terraform to the backend secret-version update,
records private/provider/GitHub readback, and confirms the old Qdrant key was rejected before its
old Secret Manager version was destroyed. It contains numeric version identifiers but no payload.
