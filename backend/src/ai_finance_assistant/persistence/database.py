"""Versioned SQLite schema and transaction boundary for the private local release."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from time import monotonic

from ai_finance_assistant.identity.models import (
    LOOPBACK_EMAIL,
    LOOPBACK_ISSUER,
    LOOPBACK_SUBJECT,
    derive_principal_id,
)
from ai_finance_assistant.observability.ports import NoOpObservability, Observability
from ai_finance_assistant.persistence.ports import DatabaseConnection

APPLICATION_SCHEMA_VERSION = 4
LOCAL_DEVELOPMENT_PRINCIPAL_ID = derive_principal_id(LOOPBACK_ISSUER, LOOPBACK_SUBJECT)

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

_MIGRATION_4 = f"""
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

INSERT INTO application_principals(
    principal_id, issuer, subject, email, role, status, created_at, updated_at
)
SELECT
    '{LOCAL_DEVELOPMENT_PRINCIPAL_ID}',
    '{LOOPBACK_ISSUER}',
    '{LOOPBACK_SUBJECT}',
    '{LOOPBACK_EMAIL}',
    'owner',
    'active',
    strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'),
    strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')
WHERE EXISTS (SELECT 1 FROM sessions);

CREATE TABLE sessions_v4 (
    session_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES application_principals(principal_id),
    label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    archived_at TEXT,
    UNIQUE (principal_id, session_id)
);
INSERT INTO sessions_v4
SELECT session_id, '{LOCAL_DEVELOPMENT_PRINCIPAL_ID}', label, created_at, updated_at,
       expires_at, archived_at
FROM sessions;

CREATE TABLE runs_v4 (
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
        REFERENCES sessions_v4(principal_id, session_id) ON DELETE CASCADE
);
INSERT INTO runs_v4
SELECT runs.execution_id, sessions_v4.principal_id, runs.session_id, runs.workflow_id,
       runs.workflow_version, runs.status, runs.result_json, runs.created_at, runs.updated_at,
       runs.request_message
FROM runs JOIN sessions_v4 ON sessions_v4.session_id = runs.session_id;

CREATE TABLE run_events_v4 (
    principal_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    event_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, execution_id, sequence),
    FOREIGN KEY (principal_id, execution_id)
        REFERENCES runs_v4(principal_id, execution_id) ON DELETE CASCADE,
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions_v4(principal_id, session_id) ON DELETE CASCADE
);
INSERT INTO run_events_v4
SELECT sessions_v4.principal_id, run_events.execution_id, run_events.session_id,
       run_events.sequence, run_events.event_id, run_events.event_json, run_events.created_at
FROM run_events JOIN sessions_v4 ON sessions_v4.session_id = run_events.session_id;

CREATE TABLE portfolios_v4 (
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
        REFERENCES sessions_v4(principal_id, session_id) ON DELETE CASCADE
);
INSERT INTO portfolios_v4
SELECT portfolios.portfolio_id, sessions_v4.principal_id, portfolios.session_id,
       portfolios.portfolio_json, portfolios.created_at, portfolios.updated_at,
       portfolios.expires_at
FROM portfolios JOIN sessions_v4 ON sessions_v4.session_id = portfolios.session_id;

CREATE TABLE portfolio_snapshots_v4 (
    snapshot_id TEXT NOT NULL,
    portfolio_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, snapshot_id),
    FOREIGN KEY (principal_id, session_id, portfolio_id)
        REFERENCES portfolios_v4(principal_id, session_id, portfolio_id) ON DELETE CASCADE
);
INSERT INTO portfolio_snapshots_v4
SELECT portfolio_snapshots.snapshot_id, portfolio_snapshots.portfolio_id,
       sessions_v4.principal_id, portfolio_snapshots.session_id,
       portfolio_snapshots.snapshot_json, portfolio_snapshots.created_at
FROM portfolio_snapshots
JOIN sessions_v4 ON sessions_v4.session_id = portfolio_snapshots.session_id;

CREATE TABLE agent_contexts_v4 (
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, session_id, context_id),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions_v4(principal_id, session_id) ON DELETE CASCADE
);
INSERT INTO agent_contexts_v4
SELECT sessions_v4.principal_id, agent_contexts.session_id, agent_contexts.context_id,
       agent_contexts.kind, agent_contexts.context_json, agent_contexts.created_at
FROM agent_contexts JOIN sessions_v4 ON sessions_v4.session_id = agent_contexts.session_id;

CREATE TABLE idempotency_records_v4 (
    principal_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id, session_id, scope, idempotency_key),
    FOREIGN KEY (principal_id, session_id)
        REFERENCES sessions_v4(principal_id, session_id) ON DELETE CASCADE
);
INSERT INTO idempotency_records_v4
SELECT sessions_v4.principal_id, idempotency_records.session_id, idempotency_records.scope,
       idempotency_records.idempotency_key, idempotency_records.request_hash,
       idempotency_records.resource_id, idempotency_records.created_at
FROM idempotency_records
JOIN sessions_v4 ON sessions_v4.session_id = idempotency_records.session_id;

DROP TABLE run_events;
DROP TABLE portfolio_snapshots;
DROP TABLE agent_contexts;
DROP TABLE idempotency_records;
DROP TABLE runs;
DROP TABLE portfolios;
DROP TABLE sessions;

ALTER TABLE sessions_v4 RENAME TO sessions;
ALTER TABLE runs_v4 RENAME TO runs;
ALTER TABLE run_events_v4 RENAME TO run_events;
ALTER TABLE portfolios_v4 RENAME TO portfolios;
ALTER TABLE portfolio_snapshots_v4 RENAME TO portfolio_snapshots;
ALTER TABLE agent_contexts_v4 RENAME TO agent_contexts;
ALTER TABLE idempotency_records_v4 RENAME TO idempotency_records;

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
"""

MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (1, "m5_initial_application_and_provider_cache", _MIGRATION_1),
    (2, "m5_session_archive_lifecycle", _MIGRATION_2),
    (3, "m5_run_request_message", _MIGRATION_3),
    (4, "principal_owned_application_resources", _MIGRATION_4),
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
    def transaction(self) -> Generator[DatabaseConnection, None, None]:
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
    def read(self) -> Generator[DatabaseConnection, None, None]:
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

    def is_integrity_error(self, error: BaseException) -> bool:
        return isinstance(error, sqlite3.IntegrityError)

    def _record_operation(self, operation: str, result_status: str, started: float) -> None:
        attributes = {"operation": operation, "result_status": result_status}
        self._observability.count("persistence.operations", 1, attributes)
        self._observability.observe(
            "persistence.duration_ms",
            (monotonic() - started) * 1_000,
            attributes,
        )
