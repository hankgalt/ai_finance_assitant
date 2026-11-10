"""Managed PostgreSQL application and checkpoint adapter qualification."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.identity.models import PrincipalRole, VerifiedIdentity
from ai_finance_assistant.identity.repositories import PrincipalRepository
from ai_finance_assistant.persistence.checkpoints import (
    create_postgres_checkpointer,
    verify_postgres_checkpoint_schema,
)
from ai_finance_assistant.persistence.cli import migrate, status
from ai_finance_assistant.persistence.postgres import PostgresDatabase, _postgres_placeholders
from ai_finance_assistant.persistence.repositories import ApplicationRepository


def test_postgres_placeholder_translation_preserves_repository_sql() -> None:
    assert _postgres_placeholders("SELECT * FROM sessions WHERE principal_id = ?") == (
        "SELECT * FROM sessions WHERE principal_id = %s"
    )


def test_persistence_operator_commands_preserve_local_sqlite_mode(tmp_path: Path) -> None:
    settings = Settings(mode="test", storage_path=tmp_path / "application.sqlite3")

    migrated = migrate(settings)
    observed = status(settings)

    assert migrated["application_schema_ready"] is True
    assert migrated["checkpoint_schema_ready"] is True
    assert observed == migrated


@pytest.mark.postgres
def test_postgres_application_and_checkpoint_state_survive_adapter_restart() -> None:
    root_dsn = os.getenv("AIFA_TEST_POSTGRES_DSN")
    if root_dsn is None:
        pytest.skip("AIFA_TEST_POSTGRES_DSN is not configured")

    schema = f"aifa_qualification_{uuid4().hex}"
    with psycopg.connect(root_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    scoped_dsn = make_conninfo(root_dsn, options=f"-c search_path={schema}")
    database: PostgresDatabase | None = None
    checkpoint_resource = None
    try:
        database = PostgresDatabase(scoped_dsn, pool_min_size=1, pool_max_size=2)
        database.migrate()
        principal = PrincipalRepository(database).ensure(
            VerifiedIdentity(
                issuer="https://cloud.google.com/iap",
                subject="qualification-owner",
                email="owner@example.invalid",
            ),
            role=PrincipalRole.OWNER,
        )
        repository = ApplicationRepository(
            database,
            session_retention_days=30,
            portfolio_retention_days=365,
            run_event_retention_days=30,
        )
        repository.create_session(principal.principal_id, "managed-session", label="Managed")

        _, checkpoint_resource = create_postgres_checkpointer(
            scoped_dsn,
            pool_min_size=1,
            pool_max_size=2,
            timeout_seconds=10,
            setup=True,
        )
        verify_postgres_checkpoint_schema(database)
        checkpoint_resource.close()
        checkpoint_resource = None
        database.close()
        database = PostgresDatabase(scoped_dsn, pool_min_size=1, pool_max_size=2)

        restored = ApplicationRepository(
            database,
            session_retention_days=30,
            portfolio_retention_days=365,
            run_event_retention_days=30,
        ).get_session(principal.principal_id, "managed-session")
        assert restored is not None
        assert restored.label == "Managed"
        verify_postgres_checkpoint_schema(database)
    finally:
        if checkpoint_resource is not None:
            checkpoint_resource.close()
        if database is not None:
            database.close()
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
