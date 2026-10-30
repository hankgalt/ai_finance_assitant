"""Versioned SQLite schema and transaction boundary for the private local release."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import monotonic

from ai_finance_assistant.observability.ports import NoOpObservability, Observability

APPLICATION_SCHEMA_VERSION = 3

_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE runs (
    execution_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX runs_session_created_idx ON runs(session_id, created_at DESC);

CREATE TABLE run_events (
    execution_id TEXT NOT NULL REFERENCES runs(execution_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    event_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (execution_id, sequence)
);
CREATE INDEX run_events_session_idx ON run_events(session_id, execution_id, sequence);

CREATE TABLE portfolios (
    portfolio_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    portfolio_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX portfolios_session_idx ON portfolios(session_id, created_at DESC);

CREATE TABLE portfolio_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX snapshots_portfolio_idx ON portfolio_snapshots(portfolio_id, created_at DESC);

CREATE TABLE agent_contexts (
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, context_id)
);

CREATE TABLE idempotency_records (
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, scope, idempotency_key)
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
CREATE INDEX market_bars_expiry_idx ON market_bars(expires_at);

CREATE TABLE market_coverage (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
CREATE INDEX market_coverage_lookup_idx ON market_coverage(
    provider, instrument, interval, currency, adjustment_basis,
    schema_version, policy_version, start_date, end_date
);
CREATE INDEX market_coverage_expiry_idx ON market_coverage(expires_at);
"""

_MIGRATION_2 = """
ALTER TABLE sessions ADD COLUMN archived_at TEXT;
CREATE INDEX sessions_state_updated_idx ON sessions(archived_at, updated_at DESC);
"""

_MIGRATION_3 = """
ALTER TABLE runs ADD COLUMN request_message TEXT;
"""

MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (1, "m5_initial_application_and_provider_cache", _MIGRATION_1),
    (2, "m5_session_archive_lifecycle", _MIGRATION_2),
    (3, "m5_run_request_message", _MIGRATION_3),
)


class MigrationError(RuntimeError):
    """The database schema is newer, incomplete, or otherwise incompatible."""


class SQLiteDatabase:
    """One locked application connection; LangGraph uses a separate connection."""

    def __init__(
        self,
        path: Path,
        *,
        expected_version: int = APPLICATION_SCHEMA_VERSION,
        observability: Observability | None = None,
    ) -> None:
        self.path = path
        self.expected_version = expected_version
        self._observability = observability or NoOpObservability()
        self._lock = RLock()
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._connection.row_factory = sqlite3.Row
        self._configure(self._connection)

    @staticmethod
    def _configure(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if connection.execute("PRAGMA database_list").fetchone()[2] != "":
            connection.execute("PRAGMA journal_mode = WAL")

    def migrate(self) -> None:
        started = monotonic()
        try:
            with self._lock:
                connection = self._connection
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
                )
                current = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                    ).fetchone()[0]
                )
                if current > self.expected_version:
                    raise MigrationError("Storage schema is newer than this application supports.")
                for version, name, sql in MIGRATIONS:
                    if current < version <= self.expected_version:
                        connection.execute("BEGIN IMMEDIATE")
                        try:
                            for statement in sql.split(";"):
                                if statement.strip():
                                    connection.execute(statement)
                            connection.execute(
                                "INSERT INTO schema_migrations(version, name, applied_at) "
                                "VALUES (?, ?, ?)",
                                (version, name, datetime.now(UTC).isoformat()),
                            )
                        except BaseException:
                            connection.rollback()
                            raise
                        else:
                            connection.commit()
                            current = version
                if current != self.expected_version:
                    raise MigrationError("Storage schema does not match the configured version.")
        except BaseException:
            self._record_operation("migration", "failed", started)
            raise
        self._record_operation("migration", "completed", started)

    def schema_version(self) -> int:
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()
            except sqlite3.Error:
                return 0
        return int(row[0])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        started = monotonic()
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except BaseException:
                self._connection.rollback()
                self._record_operation("write", "failed", started)
                raise
            else:
                self._connection.commit()
                self._record_operation("write", "completed", started)

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        started = monotonic()
        with self._lock:
            try:
                yield self._connection
            except BaseException:
                self._record_operation("read", "failed", started)
                raise
            else:
                self._record_operation("read", "completed", started)

    def checkpoint_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._configure(connection)
        return connection

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _record_operation(self, operation: str, result_status: str, started: float) -> None:
        attributes = {"operation": operation, "result_status": result_status}
        self._observability.count("persistence.operations", 1, attributes)
        self._observability.observe(
            "persistence.duration_ms",
            (monotonic() - started) * 1_000,
            attributes,
        )
