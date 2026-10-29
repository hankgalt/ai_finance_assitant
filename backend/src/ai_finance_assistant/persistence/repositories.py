"""SQLite repositories with Session ownership checks and idempotent writes."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from ai_finance_assistant.agents.context import (
    AuthorizedAgentContext,
    GoalAgentContext,
    MarketAgentContext,
    NewsAgentContext,
    PortfolioAgentContext,
)
from ai_finance_assistant.contracts.events import RunEvent
from ai_finance_assistant.finance.models import ImportedPortfolio, PortfolioSnapshot
from ai_finance_assistant.persistence.database import SQLiteDatabase
from ai_finance_assistant.persistence.models import (
    IdempotencyConflict,
    RunRecord,
    SessionRecord,
    StoredRunStatus,
)
from ai_finance_assistant.workflow.models import WorkflowRunResult


class SQLiteApplicationRepository:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        session_retention_days: int,
        portfolio_retention_days: int,
        run_event_retention_days: int,
    ) -> None:
        self._database = database
        self._session_retention = timedelta(days=session_retention_days)
        self._portfolio_retention = timedelta(days=portfolio_retention_days)
        self._run_event_retention = timedelta(days=run_event_retention_days)

    def purge_expired(self, *, now: datetime | None = None) -> tuple[str, ...]:
        observed = now or datetime.now(UTC)
        event_cutoff = observed - self._run_event_retention
        with self._database.transaction() as connection:
            expired_session_ids = tuple(
                str(row["session_id"])
                for row in connection.execute(
                    "SELECT session_id FROM sessions WHERE expires_at <= ?",
                    (observed.isoformat(),),
                ).fetchall()
            )
            connection.execute(
                "DELETE FROM run_events WHERE created_at <= ?",
                (event_cutoff.isoformat(),),
            )
            connection.execute(
                "DELETE FROM portfolios WHERE expires_at <= ?",
                (observed.isoformat(),),
            )
            connection.execute(
                "DELETE FROM idempotency_records WHERE scope = 'portfolio' AND resource_id "
                "NOT IN (SELECT portfolio_id FROM portfolios)"
            )
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (observed.isoformat(),),
            )
        return expired_session_ids

    def create_session(
        self,
        session_id: str,
        *,
        label: str | None,
        now: datetime | None = None,
    ) -> SessionRecord:
        observed = now or datetime.now(UTC)
        expires = observed + self._session_retention
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id, label, created_at, updated_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    label,
                    observed.isoformat(),
                    observed.isoformat(),
                    expires.isoformat(),
                ),
            )
        return SessionRecord(
            session_id=session_id,
            label=label,
            created_at=observed,
            updated_at=observed,
            expires_at=expires,
        )

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return None if row is None else _session_from_row(row)

    def list_sessions(self) -> tuple[SessionRecord, ...]:
        with self._database.read() as connection:
            rows = connection.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return tuple(_session_from_row(row) for row in rows)

    def delete_session(self, session_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0

    def create_run(
        self,
        *,
        execution_id: str,
        session_id: str,
        workflow_id: str,
        workflow_version: str,
        idempotency_key: str | None,
        request_hash: str,
        now: datetime | None = None,
    ) -> tuple[RunRecord, bool]:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            _require_session(connection, session_id)
            if idempotency_key is not None:
                existing = _idempotent_resource(
                    connection,
                    session_id=session_id,
                    scope="run",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    row = connection.execute(
                        "SELECT * FROM runs WHERE execution_id = ?",
                        (existing,),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError("Idempotency record references a missing Run.")
                    return _run_from_row(row), False
            connection.execute(
                "INSERT INTO runs(execution_id, session_id, workflow_id, workflow_version, "
                "status, result_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    execution_id,
                    session_id,
                    workflow_id,
                    workflow_version,
                    StoredRunStatus.RUNNING.value,
                    observed.isoformat(),
                    observed.isoformat(),
                ),
            )
            if idempotency_key is not None:
                _store_idempotency(
                    connection,
                    session_id=session_id,
                    scope="run",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_id=execution_id,
                    now=observed,
                )
        return (
            RunRecord(
                execution_id=execution_id,
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                status=StoredRunStatus.RUNNING,
                created_at=observed,
                updated_at=observed,
            ),
            True,
        )

    def finish_run(
        self,
        result: WorkflowRunResult,
        *,
        now: datetime | None = None,
    ) -> RunRecord:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = ?, result_json = ?, updated_at = ? "
                "WHERE execution_id = ? AND session_id = ?",
                (
                    result.status.value,
                    result.model_dump_json(),
                    observed.isoformat(),
                    result.execution_id,
                    result.session_id,
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("Run does not belong to this Session.")
            row = connection.execute(
                "SELECT * FROM runs WHERE execution_id = ?",
                (result.execution_id,),
            ).fetchone()
        assert row is not None
        return _run_from_row(row)

    def get_run(self, execution_id: str, *, session_id: str) -> RunRecord | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
        if row is None:
            return None
        if row["session_id"] != session_id:
            raise PermissionError("Run does not belong to this Session.")
        return _run_from_row(row)

    def list_runs(self, *, session_id: str) -> tuple[RunRecord, ...]:
        with self._database.read() as connection:
            _require_session(connection, session_id)
            rows = connection.execute(
                "SELECT * FROM runs WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return tuple(_run_from_row(row) for row in rows)

    def save_portfolio(
        self,
        portfolio: ImportedPortfolio,
        *,
        session_id: str,
        idempotency_key: str | None,
        request_hash: str,
        now: datetime | None = None,
    ) -> tuple[ImportedPortfolio, bool]:
        observed = now or datetime.now(UTC)
        expires = observed + self._portfolio_retention
        with self._database.transaction() as connection:
            _require_session(connection, session_id)
            if idempotency_key is not None:
                existing = _idempotent_resource(
                    connection,
                    session_id=session_id,
                    scope="portfolio",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    stored = _owned_portfolio(connection, existing, session_id)
                    if stored is None:
                        raise RuntimeError("Idempotency record references a missing Portfolio.")
                    return stored, False
            try:
                connection.execute(
                    "INSERT INTO portfolios(portfolio_id, session_id, portfolio_json, created_at, "
                    "updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        portfolio.portfolio_id,
                        session_id,
                        portfolio.model_dump_json(),
                        observed.isoformat(),
                        observed.isoformat(),
                        expires.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise IdempotencyConflict("Portfolio identifier already exists.") from exc
            if idempotency_key is not None:
                _store_idempotency(
                    connection,
                    session_id=session_id,
                    scope="portfolio",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_id=portfolio.portfolio_id,
                    now=observed,
                )
        return portfolio, True

    def get_portfolio(self, portfolio_id: str, *, session_id: str) -> ImportedPortfolio | None:
        with self._database.read() as connection:
            return _owned_portfolio(connection, portfolio_id, session_id)

    def list_portfolios(self, *, session_id: str) -> tuple[ImportedPortfolio, ...]:
        with self._database.read() as connection:
            _require_session(connection, session_id)
            rows = connection.execute(
                "SELECT portfolio_json FROM portfolios WHERE session_id = ? "
                "ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return tuple(ImportedPortfolio.model_validate_json(row[0]) for row in rows)

    def delete_portfolio(self, portfolio_id: str, *, session_id: str) -> bool:
        with self._database.transaction() as connection:
            existing = _owned_portfolio(connection, portfolio_id, session_id)
            if existing is None:
                return False
            cursor = connection.execute(
                "DELETE FROM portfolios WHERE portfolio_id = ? AND session_id = ?",
                (portfolio_id, session_id),
            )
            connection.execute(
                "DELETE FROM agent_contexts WHERE session_id = ? AND context_id = ?",
                (session_id, portfolio_id),
            )
        return cursor.rowcount > 0

    def save_snapshot(self, snapshot: PortfolioSnapshot, *, session_id: str) -> None:
        with self._database.transaction() as connection:
            portfolio = _owned_portfolio(connection, snapshot.portfolio_id, session_id)
            if portfolio is None:
                raise LookupError("Portfolio was not found.")
            connection.execute(
                "INSERT INTO portfolio_snapshots(snapshot_id, portfolio_id, session_id, "
                "snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.portfolio_id,
                    session_id,
                    snapshot.model_dump_json(),
                    snapshot.calculated_at.isoformat(),
                ),
            )

    def get_snapshot(self, snapshot_id: str, *, session_id: str) -> PortfolioSnapshot | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT session_id, snapshot_json FROM portfolio_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        if row["session_id"] != session_id:
            raise PermissionError("Portfolio Snapshot does not belong to this Session.")
        return PortfolioSnapshot.model_validate_json(row["snapshot_json"])

    def list_snapshots(
        self,
        portfolio_id: str,
        *,
        session_id: str,
    ) -> tuple[PortfolioSnapshot, ...]:
        with self._database.read() as connection:
            portfolio = _owned_portfolio(connection, portfolio_id, session_id)
            if portfolio is None:
                raise LookupError("Portfolio was not found.")
            rows = connection.execute(
                "SELECT snapshot_json FROM portfolio_snapshots WHERE portfolio_id = ? "
                "AND session_id = ? ORDER BY created_at DESC",
                (portfolio_id, session_id),
            ).fetchall()
        return tuple(PortfolioSnapshot.model_validate_json(row[0]) for row in rows)


class SQLiteRunEventRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def append(self, event: RunEvent) -> None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT session_id FROM runs WHERE execution_id = ?",
                (event.execution_id,),
            ).fetchone()
            if row is None or row["session_id"] != event.session_id:
                raise PermissionError("RunEvent does not belong to a persisted Run and Session.")
            expected = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM run_events WHERE execution_id = ?",
                    (event.execution_id,),
                ).fetchone()[0]
            )
            if event.sequence != expected:
                raise ValueError(f"expected RunEvent sequence {expected}")
            connection.execute(
                "INSERT INTO run_events(execution_id, session_id, sequence, event_id, "
                "event_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.execution_id,
                    event.session_id,
                    event.sequence,
                    event.event_id,
                    event.model_dump_json(),
                    event.started_at.isoformat(),
                ),
            )

    def list_for_run(
        self,
        execution_id: str,
        *,
        session_id: str,
        after_sequence: int = 0,
        limit: int | None = None,
    ) -> tuple[RunEvent, ...]:
        query = (
            "SELECT event_json FROM run_events WHERE execution_id = ? AND session_id = ? "
            "AND sequence > ? ORDER BY sequence"
        )
        params: tuple[object, ...] = (execution_id, session_id, after_sequence)
        if limit is not None:
            query += " LIMIT ?"
            params = (*params, limit)
        with self._database.read() as connection:
            run = connection.execute(
                "SELECT session_id FROM runs WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
            if run is not None and run["session_id"] != session_id:
                raise PermissionError("RunEvents do not belong to this Session.")
            rows = connection.execute(query, params).fetchall()
        return tuple(RunEvent.model_validate_json(row[0]) for row in rows)


class SQLiteAgentContextRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def put(self, session_id: str, context: AuthorizedAgentContext) -> None:
        with self._database.transaction() as connection:
            _require_session(connection, session_id)
            connection.execute(
                "INSERT INTO agent_contexts("
                "session_id, context_id, kind, context_json, created_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(session_id, context_id) DO UPDATE SET "
                "kind = excluded.kind, context_json = excluded.context_json",
                (
                    session_id,
                    context.context_id,
                    context.kind,
                    context.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get(self, session_id: str, context_id: str) -> AuthorizedAgentContext | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT kind, context_json FROM agent_contexts "
                "WHERE session_id = ? AND context_id = ?",
                (session_id, context_id),
            ).fetchone()
        if row is None:
            return None
        if row["kind"] == "portfolio":
            return PortfolioAgentContext.model_validate_json(row["context_json"])
        if row["kind"] == "market":
            return MarketAgentContext.model_validate_json(row["context_json"])
        if row["kind"] == "goal":
            return GoalAgentContext.model_validate_json(row["context_json"])
        if row["kind"] == "news":
            return NewsAgentContext.model_validate_json(row["context_json"])
        raise RuntimeError("Stored agent context has an unsupported kind.")


def _session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        session_id=row["session_id"],
        label=row["label"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
    )


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    result_json = row["result_json"]
    return RunRecord(
        execution_id=row["execution_id"],
        session_id=row["session_id"],
        workflow_id=row["workflow_id"],
        workflow_version=row["workflow_version"],
        status=StoredRunStatus(row["status"]),
        result=(
            None if result_json is None else WorkflowRunResult.model_validate_json(result_json)
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _require_session(connection: sqlite3.Connection, session_id: str) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        is None
    ):
        raise LookupError("Session was not found.")


def _owned_portfolio(
    connection: sqlite3.Connection,
    portfolio_id: str,
    session_id: str,
) -> ImportedPortfolio | None:
    row = connection.execute(
        "SELECT session_id, portfolio_json FROM portfolios WHERE portfolio_id = ?",
        (portfolio_id,),
    ).fetchone()
    if row is None:
        return None
    if row["session_id"] != session_id:
        raise PermissionError("Portfolio does not belong to this Session.")
    return ImportedPortfolio.model_validate_json(row["portfolio_json"])


def _idempotent_resource(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    scope: str,
    idempotency_key: str,
    request_hash: str,
) -> str | None:
    row = connection.execute(
        "SELECT request_hash, resource_id FROM idempotency_records "
        "WHERE session_id = ? AND scope = ? AND idempotency_key = ?",
        (session_id, scope, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise IdempotencyConflict("The idempotency key was already used with a different request.")
    return str(row["resource_id"])


def _store_idempotency(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    scope: str,
    idempotency_key: str,
    request_hash: str,
    resource_id: str,
    now: datetime,
) -> None:
    connection.execute(
        "INSERT INTO idempotency_records(session_id, scope, idempotency_key, request_hash, "
        "resource_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            scope,
            idempotency_key,
            request_hash,
            resource_id,
            now.isoformat(),
        ),
    )
