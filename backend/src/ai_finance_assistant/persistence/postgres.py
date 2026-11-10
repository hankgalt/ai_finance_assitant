"""PostgreSQL application database for the managed deployment."""

from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ai_finance_assistant.observability.ports import NoOpObservability, Observability
from ai_finance_assistant.persistence.database import (
    APPLICATION_SCHEMA_VERSION,
    MigrationError,
)
from ai_finance_assistant.persistence.ports import DatabaseConnection, DatabaseCursor

_MANAGED_SCHEMA = """
CREATE TABLE application_principals (
    principal_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (issuer, subject)
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES application_principals(principal_id),
    label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    archived_at TEXT,
    UNIQUE (principal_id, session_id)
);

CREATE TABLE runs (
    execution_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    request_message TEXT,
    UNIQUE (principal_id, execution_id),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions(principal_id, session_id) ON DELETE CASCADE
);

CREATE TABLE run_events (
    principal_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    event_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, execution_id, sequence),
    FOREIGN KEY (principal_id, execution_id)
        REFERENCES runs(principal_id, execution_id) ON DELETE CASCADE,
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions(principal_id, session_id) ON DELETE CASCADE
);

CREATE TABLE portfolios (
    portfolio_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    portfolio_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, portfolio_id),
    UNIQUE (principal_id, session_id, portfolio_id),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions(principal_id, session_id) ON DELETE CASCADE
);

CREATE TABLE portfolio_snapshots (
    snapshot_id TEXT NOT NULL,
    portfolio_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, snapshot_id),
    FOREIGN KEY (principal_id, session_id, portfolio_id)
        REFERENCES portfolios(principal_id, session_id, portfolio_id) ON DELETE CASCADE
);

CREATE TABLE agent_contexts (
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, session_id, context_id),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions(principal_id, session_id) ON DELETE CASCADE
);

CREATE TABLE idempotency_records (
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, session_id, scope, idempotency_key),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions(principal_id, session_id) ON DELETE CASCADE
);

CREATE TABLE market_bars (
    provider TEXT NOT NULL,
    instrument TEXT NOT NULL,
    interval TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    adjustment_basis TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    open_value TEXT NOT NULL,
    high_value TEXT NOT NULL,
    low_value TEXT NOT NULL,
    close_value TEXT NOT NULL,
    volume_value TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    entitlement TEXT NOT NULL,
    retention_label TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (
        provider, instrument, interval, trading_date, currency,
        adjustment_basis, schema_version, policy_version
    )
);

CREATE TABLE market_coverage (
    coverage_id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    instrument TEXT NOT NULL,
    interval TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    adjustment_basis TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    entitlement TEXT NOT NULL,
    retention_label TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    UNIQUE (
        provider, instrument, interval, start_date, end_date, currency,
        adjustment_basis, schema_version, policy_version
    )
);

CREATE INDEX sessions_state_updated_idx
    ON sessions(principal_id, archived_at, updated_at DESC);
CREATE INDEX runs_session_created_idx
    ON runs(principal_id, session_id, created_at DESC);
CREATE INDEX run_events_session_idx
    ON run_events(principal_id, session_id, execution_id, sequence);
CREATE INDEX portfolios_session_idx
    ON portfolios(principal_id, session_id, created_at DESC);
CREATE INDEX snapshots_portfolio_idx
    ON portfolio_snapshots(principal_id, portfolio_id, created_at DESC);
CREATE INDEX market_bars_expiry_idx ON market_bars(expires_at);
CREATE INDEX market_coverage_lookup_idx ON market_coverage(
    provider, instrument, interval, currency, adjustment_basis,
    schema_version, policy_version, start_date, end_date
);
CREATE INDEX market_coverage_expiry_idx ON market_coverage(expires_at);
"""


class _PostgresConnection:
    def __init__(self, connection: psycopg.Connection[dict[str, Any]]) -> None:
        self._connection = connection

    def execute(
        self,
        query: str,
        parameters: Sequence[object] = (),
    ) -> DatabaseCursor:
        cursor = self._connection.execute(_postgres_placeholders(query), parameters)
        return cast(DatabaseCursor, cursor)


class PostgresDatabase:
    """Small bounded pool for authoritative application transactions."""

    def __init__(
        self,
        dsn: str,
        *,
        expected_version: int = APPLICATION_SCHEMA_VERSION,
        pool_min_size: int = 1,
        pool_max_size: int = 5,
        timeout_seconds: float = 10.0,
        observability: Observability | None = None,
    ) -> None:
        self.expected_version = expected_version
        self._observability = observability or NoOpObservability()
        self._pool = cast(
            ConnectionPool[psycopg.Connection[dict[str, Any]]],
            ConnectionPool(
                conninfo=dsn,
                min_size=pool_min_size,
                max_size=pool_max_size,
                timeout=timeout_seconds,
                kwargs={
                    "autocommit": False,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
                open=True,
            ),
        )
        self._pool.wait(timeout=timeout_seconds)

    def migrate(self) -> None:
        started = monotonic()
        try:
            with self._pool.connection() as connection, connection.transaction():
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
                )
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) AS schema_version FROM schema_migrations"
                ).fetchone()
                current = int(row["schema_version"] if row is not None else 0)
                if current > self.expected_version:
                    raise MigrationError("Storage schema is newer than this application supports.")
                if current not in {0, self.expected_version}:
                    raise MigrationError(
                        "PostgreSQL schema requires an explicit versioned migration path."
                    )
                if current == 0:
                    for statement in _MANAGED_SCHEMA.split(";"):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, name, applied_at) "
                        "VALUES (%s, %s, %s)",
                        (
                            self.expected_version,
                            "principal_owned_managed_application_state",
                            datetime.now(UTC).isoformat(),
                        ),
                    )
        except BaseException:
            self._record_operation("migration", "failed", started)
            raise
        self._record_operation("migration", "completed", started)

    def schema_version(self) -> int:
        try:
            with self.read() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) AS schema_version FROM schema_migrations"
                ).fetchone()
        except psycopg.Error:
            return 0
        return int(row["schema_version"] if row is not None else 0)

    @contextmanager
    def transaction(self) -> Generator[DatabaseConnection, None, None]:
        started = monotonic()
        try:
            with self._pool.connection() as connection, connection.transaction():
                yield _PostgresConnection(connection)
        except BaseException:
            self._record_operation("write", "failed", started)
            raise
        self._record_operation("write", "completed", started)

    @contextmanager
    def read(self) -> Generator[DatabaseConnection, None, None]:
        started = monotonic()
        try:
            with self._pool.connection() as connection, connection.transaction():
                yield _PostgresConnection(connection)
        except BaseException:
            self._record_operation("read", "failed", started)
            raise
        self._record_operation("read", "completed", started)

    def is_integrity_error(self, error: BaseException) -> bool:
        return isinstance(error, psycopg.IntegrityError)

    def close(self) -> None:
        self._pool.close()

    def _record_operation(self, operation: str, result_status: str, started: float) -> None:
        attributes = {"operation": operation, "result_status": result_status}
        self._observability.count("persistence.operations", 1, attributes)
        self._observability.observe(
            "persistence.duration_ms",
            (monotonic() - started) * 1_000,
            attributes,
        )


def _postgres_placeholders(query: str) -> str:
    """Translate the repository's backend-neutral positional placeholders."""

    return query.replace("?", "%s")
