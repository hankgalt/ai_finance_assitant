"""Persistence for Application Principals and revocation state."""

from __future__ import annotations

from datetime import UTC, datetime

from ai_finance_assistant.identity.models import (
    ApplicationPrincipal,
    PrincipalRole,
    PrincipalStatus,
    VerifiedIdentity,
    derive_principal_id,
)
from ai_finance_assistant.persistence.ports import ApplicationDatabase, DatabaseRow


class PrincipalRepository:
    def __init__(self, database: ApplicationDatabase) -> None:
        self._database = database

    def resolve_or_admit(
        self,
        identity: VerifiedIdentity,
        *,
        owner_email: str,
        viewer_emails: frozenset[str],
        now: datetime | None = None,
    ) -> ApplicationPrincipal | None:
        observed = now or datetime.now(UTC)
        normalized_email = identity.email.strip().lower()
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM application_principals WHERE issuer = ? AND subject = ?",
                (identity.issuer, identity.subject),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE application_principals SET email = ?, updated_at = ? "
                    "WHERE principal_id = ?",
                    (normalized_email, observed.isoformat(), row["principal_id"]),
                )
                refreshed = connection.execute(
                    "SELECT * FROM application_principals WHERE principal_id = ?",
                    (row["principal_id"],),
                ).fetchone()
                assert refreshed is not None
                return _principal_from_row(refreshed)

            role: PrincipalRole | None = None
            if normalized_email == owner_email:
                role = PrincipalRole.OWNER
            elif normalized_email in viewer_emails:
                role = PrincipalRole.VIEWER
            if role is None:
                return None
            principal_id = derive_principal_id(identity.issuer, identity.subject)
            try:
                connection.execute(
                    "INSERT INTO application_principals("
                    "principal_id, issuer, subject, email, role, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        principal_id,
                        identity.issuer,
                        identity.subject,
                        normalized_email,
                        role.value,
                        PrincipalStatus.ACTIVE.value,
                        observed.isoformat(),
                        observed.isoformat(),
                    ),
                )
            except BaseException as exc:
                if self._database.is_integrity_error(exc):
                    raise RuntimeError("Application Principal identity collision.") from exc
                raise
            row = connection.execute(
                "SELECT * FROM application_principals WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        assert row is not None
        return _principal_from_row(row)

    def ensure(
        self,
        identity: VerifiedIdentity,
        *,
        role: PrincipalRole,
        now: datetime | None = None,
    ) -> ApplicationPrincipal:
        observed = now or datetime.now(UTC)
        principal_id = derive_principal_id(identity.issuer, identity.subject)
        normalized_email = identity.email.strip().lower()
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO application_principals("
                "principal_id, issuer, subject, email, role, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(issuer, subject) DO UPDATE SET "
                "email = excluded.email, updated_at = excluded.updated_at",
                (
                    principal_id,
                    identity.issuer,
                    identity.subject,
                    normalized_email,
                    role.value,
                    PrincipalStatus.ACTIVE.value,
                    observed.isoformat(),
                    observed.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM application_principals WHERE issuer = ? AND subject = ?",
                (identity.issuer, identity.subject),
            ).fetchone()
        assert row is not None
        return _principal_from_row(row)

    def get(self, principal_id: str) -> ApplicationPrincipal | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT * FROM application_principals WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        return None if row is None else _principal_from_row(row)

    def set_status(
        self,
        principal_id: str,
        status: PrincipalStatus,
        *,
        now: datetime | None = None,
    ) -> ApplicationPrincipal:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE application_principals SET status = ?, updated_at = ? "
                "WHERE principal_id = ?",
                (status.value, observed.isoformat(), principal_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Application Principal was not found.")
            row = connection.execute(
                "SELECT * FROM application_principals WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        assert row is not None
        return _principal_from_row(row)


def _principal_from_row(row: DatabaseRow) -> ApplicationPrincipal:
    return ApplicationPrincipal(
        principal_id=row["principal_id"],
        issuer=row["issuer"],
        subject=row["subject"],
        email=row["email"],
        role=PrincipalRole(row["role"]),
        status=PrincipalStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
