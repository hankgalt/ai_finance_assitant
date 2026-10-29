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
