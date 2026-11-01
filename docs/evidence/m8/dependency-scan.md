# M8 dependency scan

Status: completed for locked production dependencies on 2026-10-31.

The frontend command `pnpm audit --prod --json` inspected 165 production/optional dependencies and
reported zero known vulnerabilities at scan time.

The backend lock was exported with exact production pins and audited with `pip-audit` in
`--no-deps --disable-pip` mode. The initial scan found three denial-of-service advisories in
`pypdf 6.21.3`: `CVE-2026-119203`, `CVE-2026-119204`, and `CVE-2026-119205`. All named `6.21.4` as
the fixed version. The existing `>=6.6,<7` constraint allowed the remediation; `uv.lock` and the
test environment were updated to `pypdf 6.21.4`. The repeat scan reported **no known
vulnerabilities**.

Machine summary: `backend/artifacts/m8/dependency-scan.v1.json`. This is a point-in-time advisory
database result, not a guarantee of absence. The first resolver-based pip-audit attempt failed while
creating its temporary environment; that failure was retained as unavailable and followed by the
documented exact-pin no-install mode rather than being misreported as clean.
