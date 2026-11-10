"""Strictly deserializing LangGraph SQLite checkpointer construction."""

import sqlite3

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from ai_finance_assistant.contracts.agents import (
    AgentId,
    AgentResult,
    AgentResultStatus,
    EvidenceReference,
)
from ai_finance_assistant.contracts.errors import ErrorCategory, SafeError
from ai_finance_assistant.persistence.database import SQLiteDatabase
from ai_finance_assistant.workflow.models import WorkflowStatus


def create_sqlite_checkpointer(
    database: SQLiteDatabase,
) -> tuple[SqliteSaver, sqlite3.Connection]:
    connection = database.checkpoint_connection()
    serializer = JsonPlusSerializer(
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
    saver = SqliteSaver(connection, serde=serializer)
    saver.setup()
    return saver, connection


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
