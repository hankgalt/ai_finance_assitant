"""Application repositories with Principal/Session ownership checks and idempotent writes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai_finance_assistant.agents.context import (
    AuthorizedAgentContext,
    GoalAgentContext,
    MarketAgentContext,
    NewsAgentContext,
    PortfolioAgentContext,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.contracts.events import RunEvent
from ai_finance_assistant.finance.models import ImportedPortfolio, PortfolioSnapshot
from ai_finance_assistant.persistence.models import (
    IdempotencyConflict,
    RunRecord,
    SessionRecord,
    SessionState,
    StoredRunStatus,
)
from ai_finance_assistant.persistence.ports import (
    ApplicationDatabase,
    DatabaseConnection,
    DatabaseRow,
)
from ai_finance_assistant.workflow.models import WorkflowRunResult, WorkflowStatus


class ApplicationRepository:
    def __init__(
        self,
        database: ApplicationDatabase,
        *,
        session_retention_days: int,
        portfolio_retention_days: int,
        run_event_retention_days: int,
    ) -> None:
        self._database = database
        self._session_retention = timedelta(days=session_retention_days)
        self._portfolio_retention = timedelta(days=portfolio_retention_days)
        self._run_event_retention = timedelta(days=run_event_retention_days)

    def purge_expired(self, *, now: datetime | None = None) -> tuple[tuple[str, str], ...]:
        observed = now or datetime.now(UTC)
        event_cutoff = observed - self._run_event_retention
        with self._database.transaction() as connection:
            expired_sessions = tuple(
                (str(row["principal_id"]), str(row["session_id"]))
                for row in connection.execute(
                    "SELECT principal_id, session_id FROM sessions WHERE expires_at <= ?",
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
                "NOT IN (SELECT portfolio_id FROM portfolios "
                "WHERE portfolios.principal_id = idempotency_records.principal_id)"
            )
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (observed.isoformat(),),
            )
        return expired_sessions

    def create_session(
        self,
        principal_id: str,
        session_id: str,
        *,
        label: str | None,
        now: datetime | None = None,
    ) -> SessionRecord:
        observed = now or datetime.now(UTC)
        expires = observed + self._session_retention
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions(principal_id, session_id, label, created_at, updated_at, "
                "expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    principal_id,
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
            state=SessionState.ACTIVE,
            created_at=observed,
            updated_at=observed,
            expires_at=expires,
            archived_at=None,
        )

    def get_session(self, principal_id: str, session_id: str) -> SessionRecord | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE principal_id = ? AND session_id = ?",
                (principal_id, session_id),
            ).fetchone()
        return None if row is None else _session_from_row(row)

    def list_sessions(
        self,
        principal_id: str,
        *,
        state: SessionState | None = None,
    ) -> tuple[SessionRecord, ...]:
        clauses = ["principal_id = ?"]
        if state == SessionState.ACTIVE:
            clauses.append("archived_at IS NULL")
        elif state == SessionState.ARCHIVED:
            clauses.append("archived_at IS NOT NULL")
        query = "SELECT * FROM sessions WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        with self._database.read() as connection:
            rows = connection.execute(query, (principal_id,)).fetchall()
        return tuple(_session_from_row(row) for row in rows)

    def archive_session(
        self,
        principal_id: str,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SessionRecord | None:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM sessions WHERE principal_id = ? AND session_id = ?",
                (principal_id, session_id),
            ).fetchone()
            if existing is None:
                return None
            if existing["archived_at"] is None:
                connection.execute(
                    "UPDATE sessions SET archived_at = ?, updated_at = ? "
                    "WHERE principal_id = ? AND session_id = ? AND archived_at IS NULL",
                    (observed.isoformat(), observed.isoformat(), principal_id, session_id),
                )
            row = connection.execute(
                "SELECT * FROM sessions WHERE principal_id = ? AND session_id = ?",
                (principal_id, session_id),
            ).fetchone()
        assert row is not None
        return _session_from_row(row)

    def delete_archived_session(self, principal_id: str, session_id: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE principal_id = ? AND session_id = ? "
                "AND archived_at IS NOT NULL",
                (principal_id, session_id),
            )
        return cursor.rowcount > 0

    def create_run(
        self,
        *,
        principal_id: str,
        execution_id: str,
        session_id: str,
        workflow_id: str,
        workflow_version: str,
        request_message: str,
        idempotency_key: str | None,
        request_hash: str,
        now: datetime | None = None,
    ) -> tuple[RunRecord, bool]:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            _require_active_session(connection, principal_id, session_id)
            if idempotency_key is not None:
                existing = _idempotent_resource(
                    connection,
                    principal_id=principal_id,
                    session_id=session_id,
                    scope="run",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    row = connection.execute(
                        "SELECT * FROM runs WHERE principal_id = ? AND execution_id = ?",
                        (principal_id, existing),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError("Idempotency record references a missing Run.")
                    return _run_from_row(row), False
            connection.execute(
                "INSERT INTO runs(principal_id, execution_id, session_id, workflow_id, "
                "workflow_version, status, request_message, result_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    principal_id,
                    execution_id,
                    session_id,
                    workflow_id,
                    workflow_version,
                    StoredRunStatus.RUNNING.value,
                    request_message,
                    observed.isoformat(),
                    observed.isoformat(),
                ),
            )
            if idempotency_key is not None:
                _store_idempotency(
                    connection,
                    principal_id=principal_id,
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
                request_message=request_message,
                created_at=observed,
                updated_at=observed,
            ),
            True,
        )

    def reconcile_interrupted_runs(
        self,
        *,
        deadline_before: datetime,
        observed_at: datetime | None = None,
    ) -> int:
        """Terminalize Runs that outlived their request deadline without a persisted result."""

        observed = observed_at or datetime.now(UTC)
        with self._database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM runs WHERE status = ? AND updated_at <= ? ORDER BY created_at",
                (StoredRunStatus.RUNNING.value, deadline_before.isoformat()),
            ).fetchall()
            reconciled = 0
            for row in rows:
                result = WorkflowRunResult(
                    execution_id=row["execution_id"],
                    session_id=row["session_id"],
                    workflow_id=row["workflow_id"],
                    workflow_version=row["workflow_version"],
                    status=WorkflowStatus.FAILED,
                    selected_agent_ids=(),
                    agent_results=(),
                    summary="The Run was interrupted before completion.",
                    errors=(
                        SafeError(
                            code="RUN_INTERRUPTED",
                            category=ErrorCategory.INTERNAL,
                            message=(
                                "The Run was interrupted before a terminal result was persisted."
                            ),
                            retryable=True,
                        ),
                    ),
                    trace_unavailable_reason=(
                        "The process ended before terminal trace correlation was persisted."
                    ),
                )
                cursor = connection.execute(
                    "UPDATE runs SET status = ?, result_json = ?, updated_at = ? "
                    "WHERE principal_id = ? AND execution_id = ? AND status = ?",
                    (
                        StoredRunStatus.FAILED.value,
                        result.model_dump_json(),
                        observed.isoformat(),
                        row["principal_id"],
                        row["execution_id"],
                        StoredRunStatus.RUNNING.value,
                    ),
                )
                reconciled += cursor.rowcount
        return reconciled

    def finish_run(
        self,
        result: WorkflowRunResult,
        *,
        principal_id: str,
        now: datetime | None = None,
    ) -> RunRecord:
        observed = now or datetime.now(UTC)
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, result_json = ?, updated_at = ? "
                "WHERE principal_id = ? AND execution_id = ? AND session_id = ? AND status = ?",
                (
                    result.status.value,
                    result.model_dump_json(),
                    observed.isoformat(),
                    principal_id,
                    result.execution_id,
                    result.session_id,
                    StoredRunStatus.RUNNING.value,
                ),
            )
            row = connection.execute(
                "SELECT * FROM runs WHERE principal_id = ? AND execution_id = ?",
                (principal_id, result.execution_id),
            ).fetchone()
            if row is None or row["session_id"] != result.session_id:
                raise PermissionError("Run does not belong to this Session.")
        return _run_from_row(row)

    def get_run(
        self,
        principal_id: str,
        execution_id: str,
        *,
        session_id: str,
    ) -> RunRecord | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE principal_id = ? AND execution_id = ?",
                (principal_id, execution_id),
            ).fetchone()
        if row is None:
            return None
        if row["session_id"] != session_id:
            raise PermissionError("Run does not belong to this Session.")
        return _run_from_row(row)

    def list_runs(self, principal_id: str, *, session_id: str) -> tuple[RunRecord, ...]:
        with self._database.read() as connection:
            _require_session(connection, principal_id, session_id)
            rows = connection.execute(
                "SELECT * FROM runs WHERE principal_id = ? AND session_id = ? "
                "ORDER BY created_at DESC",
                (principal_id, session_id),
            ).fetchall()
        return tuple(_run_from_row(row) for row in rows)

    def save_portfolio(
        self,
        portfolio: ImportedPortfolio,
        *,
        principal_id: str,
        session_id: str,
        idempotency_key: str | None,
        request_hash: str,
        now: datetime | None = None,
    ) -> tuple[ImportedPortfolio, bool]:
        observed = now or datetime.now(UTC)
        expires = observed + self._portfolio_retention
        with self._database.transaction() as connection:
            _require_active_session(connection, principal_id, session_id)
            if idempotency_key is not None:
                existing = _idempotent_resource(
                    connection,
                    principal_id=principal_id,
                    session_id=session_id,
                    scope="portfolio",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
                if existing is not None:
                    stored = _owned_portfolio(connection, principal_id, existing, session_id)
                    if stored is None:
                        raise RuntimeError("Idempotency record references a missing Portfolio.")
                    return stored, False
            try:
                connection.execute(
                    "INSERT INTO portfolios(principal_id, portfolio_id, session_id, "
                    "portfolio_json, created_at, updated_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        principal_id,
                        portfolio.portfolio_id,
                        session_id,
                        portfolio.model_dump_json(),
                        observed.isoformat(),
                        observed.isoformat(),
                        expires.isoformat(),
                    ),
                )
            except BaseException as exc:
                if self._database.is_integrity_error(exc):
                    raise IdempotencyConflict("Portfolio identifier already exists.") from exc
                raise
            if idempotency_key is not None:
                _store_idempotency(
                    connection,
                    principal_id=principal_id,
                    session_id=session_id,
                    scope="portfolio",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_id=portfolio.portfolio_id,
                    now=observed,
                )
        return portfolio, True

    def get_portfolio(
        self,
        principal_id: str,
        portfolio_id: str,
        *,
        session_id: str,
    ) -> ImportedPortfolio | None:
        with self._database.read() as connection:
            return _owned_portfolio(connection, principal_id, portfolio_id, session_id)

    def list_portfolios(
        self,
        principal_id: str,
        *,
        session_id: str,
    ) -> tuple[ImportedPortfolio, ...]:
        with self._database.read() as connection:
            _require_session(connection, principal_id, session_id)
            rows = connection.execute(
                "SELECT portfolio_json AS value_json FROM portfolios "
                "WHERE principal_id = ? AND session_id = ? "
                "ORDER BY created_at DESC",
                (principal_id, session_id),
            ).fetchall()
        return tuple(ImportedPortfolio.model_validate_json(row["value_json"]) for row in rows)

    def delete_portfolio(
        self,
        principal_id: str,
        portfolio_id: str,
        *,
        session_id: str,
    ) -> bool:
        with self._database.transaction() as connection:
            _require_active_session(connection, principal_id, session_id)
            existing = _owned_portfolio(connection, principal_id, portfolio_id, session_id)
            if existing is None:
                return False
            cursor = connection.execute(
                "DELETE FROM portfolios WHERE principal_id = ? AND portfolio_id = ? "
                "AND session_id = ?",
                (principal_id, portfolio_id, session_id),
            )
            connection.execute(
                "DELETE FROM agent_contexts WHERE principal_id = ? AND session_id = ? "
                "AND context_id = ?",
                (principal_id, session_id, portfolio_id),
            )
            connection.execute(
                "DELETE FROM idempotency_records WHERE principal_id = ? AND session_id = ? "
                "AND scope = ? "
                "AND resource_id = ?",
                (principal_id, session_id, "portfolio", portfolio_id),
            )
        return cursor.rowcount > 0

    def save_snapshot(
        self,
        principal_id: str,
        snapshot: PortfolioSnapshot,
        *,
        session_id: str,
    ) -> None:
        with self._database.transaction() as connection:
            _require_active_session(connection, principal_id, session_id)
            portfolio = _owned_portfolio(
                connection, principal_id, snapshot.portfolio_id, session_id
            )
            if portfolio is None:
                raise LookupError("Portfolio was not found.")
            connection.execute(
                "INSERT INTO portfolio_snapshots(principal_id, snapshot_id, portfolio_id, "
                "session_id, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    principal_id,
                    snapshot.snapshot_id,
                    snapshot.portfolio_id,
                    session_id,
                    snapshot.model_dump_json(),
                    snapshot.calculated_at.isoformat(),
                ),
            )

    def get_snapshot(
        self,
        principal_id: str,
        snapshot_id: str,
        *,
        session_id: str,
    ) -> PortfolioSnapshot | None:
        with self._database.read() as connection:
            row = connection.execute(
                "SELECT session_id, snapshot_json FROM portfolio_snapshots WHERE principal_id = ? "
                "AND snapshot_id = ?",
                (principal_id, snapshot_id),
            ).fetchone()
        if row is None:
            return None
        if row["session_id"] != session_id:
            raise PermissionError("Portfolio Snapshot does not belong to this Session.")
        return PortfolioSnapshot.model_validate_json(row["snapshot_json"])

    def list_snapshots(
        self,
        principal_id: str,
        portfolio_id: str,
        *,
        session_id: str,
    ) -> tuple[PortfolioSnapshot, ...]:
        with self._database.read() as connection:
            portfolio = _owned_portfolio(connection, principal_id, portfolio_id, session_id)
            if portfolio is None:
                raise LookupError("Portfolio was not found.")
            rows = connection.execute(
                "SELECT snapshot_json AS value_json FROM portfolio_snapshots "
                "WHERE principal_id = ? "
                "AND portfolio_id = ? AND session_id = ? ORDER BY created_at DESC",
                (principal_id, portfolio_id, session_id),
            ).fetchall()
        return tuple(PortfolioSnapshot.model_validate_json(row["value_json"]) for row in rows)


class RunEventRepository:
    def __init__(self, database: ApplicationDatabase) -> None:
        self._database = database

    def append(self, event: RunEvent) -> None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT principal_id, session_id FROM runs WHERE execution_id = ?",
                (event.execution_id,),
            ).fetchone()
            if row is None or row["session_id"] != event.session_id:
                raise PermissionError("RunEvent does not belong to a persisted Run and Session.")
            expected_row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence "
                "FROM run_events WHERE execution_id = ?",
                (event.execution_id,),
            ).fetchone()
            assert expected_row is not None
            expected = int(expected_row["next_sequence"])
            if event.sequence != expected:
                raise ValueError(f"expected RunEvent sequence {expected}")
            connection.execute(
                "INSERT INTO run_events(principal_id, execution_id, session_id, sequence, "
                "event_id, event_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["principal_id"],
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
        principal_id: str,
        execution_id: str,
        *,
        session_id: str,
        after_sequence: int = 0,
        limit: int | None = None,
    ) -> tuple[RunEvent, ...]:
        query = (
            "SELECT event_json AS value_json FROM run_events "
            "WHERE principal_id = ? AND execution_id = ? "
            "AND session_id = ? AND sequence > ? ORDER BY sequence"
        )
        params: tuple[object, ...] = (
            principal_id,
            execution_id,
            session_id,
            after_sequence,
        )
        if limit is not None:
            query += " LIMIT ?"
            params = (*params, limit)
        with self._database.read() as connection:
            run = connection.execute(
                "SELECT session_id FROM runs WHERE principal_id = ? AND execution_id = ?",
                (principal_id, execution_id),
            ).fetchone()
            if run is not None and run["session_id"] != session_id:
                raise PermissionError("RunEvents do not belong to this Session.")
            rows = connection.execute(query, params).fetchall()
        return tuple(RunEvent.model_validate_json(row["value_json"]) for row in rows)


class AgentContextRepository:
    def __init__(self, database: ApplicationDatabase) -> None:
        self._database = database

    def put(self, session_id: str, context: AuthorizedAgentContext) -> None:
        with self._database.transaction() as connection:
            principal_row = connection.execute(
                "SELECT principal_id FROM sessions WHERE session_id = ? AND archived_at IS NULL",
                (session_id,),
            ).fetchone()
            if principal_row is None:
                raise LookupError("An active Session was not found.")
            connection.execute(
                "INSERT INTO agent_contexts("
                "principal_id, session_id, context_id, kind, context_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(principal_id, session_id, context_id) DO UPDATE SET "
                "kind = excluded.kind, context_json = excluded.context_json",
                (
                    principal_row["principal_id"],
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

    def list_portfolios(self, session_id: str) -> tuple[PortfolioAgentContext, ...]:
        with self._database.read() as connection:
            rows = connection.execute(
                "SELECT context_json FROM agent_contexts "
                "WHERE session_id = ? AND kind = 'portfolio' "
                "ORDER BY created_at, context_id",
                (session_id,),
            ).fetchall()
        return tuple(PortfolioAgentContext.model_validate_json(row["context_json"]) for row in rows)


def _session_from_row(row: DatabaseRow) -> SessionRecord:
    archived_at = row["archived_at"]
    return SessionRecord(
        session_id=row["session_id"],
        label=row["label"],
        state=(SessionState.ARCHIVED if archived_at is not None else SessionState.ACTIVE),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        archived_at=(datetime.fromisoformat(archived_at) if archived_at is not None else None),
    )


def _run_from_row(row: DatabaseRow) -> RunRecord:
    result_json = row["result_json"]
    return RunRecord(
        execution_id=row["execution_id"],
        session_id=row["session_id"],
        workflow_id=row["workflow_id"],
        workflow_version=row["workflow_version"],
        status=StoredRunStatus(row["status"]),
        request_message=row["request_message"],
        result=(
            None if result_json is None else WorkflowRunResult.model_validate_json(result_json)
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _require_session(
    connection: DatabaseConnection,
    principal_id: str,
    session_id: str,
) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM sessions WHERE principal_id = ? AND session_id = ?",
            (principal_id, session_id),
        ).fetchone()
        is None
    ):
        raise LookupError("Session was not found.")


def _require_active_session(
    connection: DatabaseConnection,
    principal_id: str,
    session_id: str,
) -> None:
    row = connection.execute(
        "SELECT archived_at FROM sessions WHERE principal_id = ? AND session_id = ?",
        (principal_id, session_id),
    ).fetchone()
    if row is None:
        raise LookupError("Session was not found.")
    if row["archived_at"] is not None:
        raise PermissionError("Archived Sessions are read-only.")


def _owned_portfolio(
    connection: DatabaseConnection,
    principal_id: str,
    portfolio_id: str,
    session_id: str,
) -> ImportedPortfolio | None:
    row = connection.execute(
        "SELECT session_id, portfolio_json FROM portfolios WHERE principal_id = ? "
        "AND portfolio_id = ?",
        (principal_id, portfolio_id),
    ).fetchone()
    if row is None:
        return None
    if row["session_id"] != session_id:
        raise PermissionError("Portfolio does not belong to this Session.")
    return ImportedPortfolio.model_validate_json(row["portfolio_json"])


def _idempotent_resource(
    connection: DatabaseConnection,
    *,
    principal_id: str,
    session_id: str,
    scope: str,
    idempotency_key: str,
    request_hash: str,
) -> str | None:
    row = connection.execute(
        "SELECT request_hash, resource_id FROM idempotency_records "
        "WHERE principal_id = ? AND session_id = ? AND scope = ? AND idempotency_key = ?",
        (principal_id, session_id, scope, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise IdempotencyConflict("The idempotency key was already used with a different request.")
    return str(row["resource_id"])


def _store_idempotency(
    connection: DatabaseConnection,
    *,
    principal_id: str,
    session_id: str,
    scope: str,
    idempotency_key: str,
    request_hash: str,
    resource_id: str,
    now: datetime,
) -> None:
    connection.execute(
        "INSERT INTO idempotency_records(principal_id, session_id, scope, idempotency_key, "
        "request_hash, resource_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            principal_id,
            session_id,
            scope,
            idempotency_key,
            request_hash,
            resource_id,
            now.isoformat(),
        ),
    )
