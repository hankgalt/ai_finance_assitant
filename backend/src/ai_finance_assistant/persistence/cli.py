"""Operator commands for application schemas and scheduled retention."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.persistence.checkpoints import (
    Closeable,
    create_postgres_checkpointer,
    create_sqlite_checkpointer,
    verify_postgres_checkpoint_schema,
)
from ai_finance_assistant.persistence.database import MigrationError, SQLiteDatabase
from ai_finance_assistant.persistence.ports import ApplicationDatabase
from ai_finance_assistant.persistence.postgres import PostgresDatabase
from ai_finance_assistant.persistence.repositories import ApplicationRepository
from ai_finance_assistant.providers.durable_cache import HistoricalCacheRepository


def migrate(settings: Settings) -> dict[str, Any]:
    database = _database(settings)
    checkpoint_resource: Closeable | None = None
    try:
        database.migrate()
        if settings.storage_backend == "sqlite":
            assert isinstance(database, SQLiteDatabase)
            _, checkpoint_resource = create_sqlite_checkpointer(database)
        else:
            assert settings.postgres_dsn is not None
            _, checkpoint_resource = create_postgres_checkpointer(
                settings.postgres_dsn.get_secret_value(),
                pool_min_size=settings.postgres_pool_min_size,
                pool_max_size=settings.postgres_pool_max_size,
                timeout_seconds=settings.postgres_connect_timeout_seconds,
                setup=True,
            )
            verify_postgres_checkpoint_schema(database)
        return _status(database, settings, checkpoint_ready=True)
    finally:
        if checkpoint_resource is not None:
            checkpoint_resource.close()
        database.close()


def status(settings: Settings) -> dict[str, Any]:
    database = _database(settings)
    try:
        checkpoint_ready = settings.storage_backend == "sqlite"
        if settings.storage_backend == "postgres":
            try:
                verify_postgres_checkpoint_schema(database)
            except MigrationError:
                checkpoint_ready = False
            else:
                checkpoint_ready = True
        return _status(database, settings, checkpoint_ready=checkpoint_ready)
    finally:
        database.close()


def run_retention(settings: Settings) -> dict[str, Any]:
    if settings.storage_backend != "postgres":
        raise RuntimeError("Scheduled retention is reserved for managed PostgreSQL storage.")
    if settings.response_cache_adapter != "disabled":
        raise RuntimeError("Managed retention requires the approved disabled response cache.")
    database = _database(settings)
    checkpoint_resource: Closeable | None = None
    try:
        if database.schema_version() != database.expected_version:
            raise MigrationError("Application schema is not ready for retention.")
        verify_postgres_checkpoint_schema(database)
        assert settings.postgres_dsn is not None
        checkpointer, checkpoint_resource = create_postgres_checkpointer(
            settings.postgres_dsn.get_secret_value(),
            pool_min_size=settings.postgres_pool_min_size,
            pool_max_size=settings.postgres_pool_max_size,
            timeout_seconds=settings.postgres_connect_timeout_seconds,
            setup=False,
        )
        repository = ApplicationRepository(
            database,
            session_retention_days=settings.session_retention_days,
            portfolio_retention_days=settings.portfolio_retention_days,
            run_event_retention_days=settings.run_event_retention_days,
        )
        expired_sessions = repository.purge_expired()
        for principal_id, session_id in expired_sessions:
            checkpointer.delete_thread(f"{principal_id}:{session_id}:{settings.workflow_id}")
        provider_rows = HistoricalCacheRepository(database).purge_expired(now=datetime.now(UTC))
        return {
            "backend": settings.storage_backend,
            "expired_sessions": len(expired_sessions),
            "expired_provider_rows": provider_rows,
        }
    finally:
        if checkpoint_resource is not None:
            checkpoint_resource.close()
        database.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("migrate", "status", "retention"))
    args = parser.parse_args(argv)
    settings = Settings()
    if args.command == "migrate":
        result = migrate(settings)
    elif args.command == "status":
        result = status(settings)
    else:
        result = run_retention(settings)
    print(json.dumps(result, sort_keys=True))
    return 0


def _database(settings: Settings) -> ApplicationDatabase:
    if settings.storage_backend == "sqlite":
        return SQLiteDatabase(
            settings.storage_path,
            expected_version=settings.storage_expected_schema_version,
        )
    assert settings.postgres_dsn is not None
    return PostgresDatabase(
        settings.postgres_dsn.get_secret_value(),
        expected_version=settings.storage_expected_schema_version,
        pool_min_size=settings.postgres_pool_min_size,
        pool_max_size=settings.postgres_pool_max_size,
        timeout_seconds=settings.postgres_connect_timeout_seconds,
    )


def _status(
    database: ApplicationDatabase,
    settings: Settings,
    *,
    checkpoint_ready: bool,
) -> dict[str, Any]:
    current = database.schema_version()
    return {
        "backend": settings.storage_backend,
        "application_schema_version": current,
        "expected_application_schema_version": database.expected_version,
        "application_schema_ready": current == database.expected_version,
        "checkpoint_schema_ready": checkpoint_ready,
    }


if __name__ == "__main__":
    raise SystemExit(main())
