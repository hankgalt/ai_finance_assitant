"""Strictly deserializing LangGraph SQLite checkpointer construction."""

import sqlite3
from typing import Any, Protocol, cast

import psycopg
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentResult,
    AgentResultStatus,
    EvidenceReference,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.persistence.database import MigrationError, SQLiteDatabase
from ai_finance_assistant.persistence.ports import ApplicationDatabase
from ai_finance_assistant.workflow.models import WorkflowStatus


class Closeable(Protocol):
    def close(self) -> None: ...


def strict_checkpoint_serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(
        allowed_msgpack_modules=(
            AgentId,
            AgentResult,
            AgentResultStatus,
            EvidenceReference,
            ErrorCategory,
            SafeError,
            WorkflowStatus,
        )
    )


def create_sqlite_checkpointer(
    database: SQLiteDatabase,
) -> tuple[SqliteSaver, sqlite3.Connection]:
    connection = database.checkpoint_connection()
    saver = SqliteSaver(connection, serde=strict_checkpoint_serializer())
    saver.setup()
    return saver, connection


def create_postgres_checkpointer(
    dsn: str,
    *,
    pool_min_size: int,
    pool_max_size: int,
    timeout_seconds: float,
    setup: bool,
) -> tuple[BaseCheckpointSaver[str], Closeable]:
    pool = cast(
        ConnectionPool[psycopg.Connection[dict[str, Any]]],
        ConnectionPool(
            conninfo=dsn,
            min_size=pool_min_size,
            max_size=pool_max_size,
            timeout=timeout_seconds,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            open=True,
        ),
    )
    try:
        pool.wait(timeout=timeout_seconds)
        saver = PostgresSaver(pool, serde=strict_checkpoint_serializer())
        if setup:
            saver.setup()
    except BaseException:
        pool.close()
        raise
    return saver, pool


def verify_postgres_checkpoint_schema(database: ApplicationDatabase) -> None:
    expected = {
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    }
    placeholders = ", ".join("?" for _ in expected)
    with database.read() as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name IN (" + placeholders + ")",
            tuple(sorted(expected)),
        ).fetchall()
    present = {str(row["table_name"]) for row in rows}
    if present != expected:
        raise MigrationError("LangGraph PostgreSQL checkpoint schema is not initialized.")


def scope_legacy_checkpoint_threads(
    database: SQLiteDatabase,
    connection: sqlite3.Connection,
) -> int:
    """Attach schema-v3 checkpoint threads to their migrated local principal."""

    with database.read() as application_connection:
        sessions = tuple(
            (str(row["principal_id"]), str(row["session_id"]))
            for row in application_connection.execute(
                "SELECT principal_id, session_id FROM sessions"
            ).fetchall()
        )
    changed = 0
    with connection:
        for principal_id, session_id in sessions:
            legacy_prefix = f"{session_id}:%"
            scoped_prefix = f"{principal_id}:{session_id}:"
            for table in ("checkpoints", "writes"):
                cursor = connection.execute(
                    f"UPDATE {table} SET thread_id = ? || substr(thread_id, ?) "
                    "WHERE thread_id LIKE ? AND thread_id NOT LIKE ?",
                    (
                        scoped_prefix,
                        len(session_id) + 2,
                        legacy_prefix,
                        f"{scoped_prefix}%",
                    ),
                )
                changed += cursor.rowcount
    return changed
