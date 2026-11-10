import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.persistence.checkpoints import create_sqlite_checkpointer
from ai_finance_assistant.persistence.database import (
    LOCAL_DEVELOPMENT_PRINCIPAL_ID,
    MigrationError,
    SQLiteDatabase,
)


def _settings(path: Path) -> Settings:
    return Settings(
        mode="test",
        storage_path=path,
        provider_mode="credential_free",
        model_mode="credential_free",
        qdrant_url=None,
        observability_mode="in_memory",
        langsmith_tracing_enabled=False,
    )


def test_sessions_runs_events_and_checkpoints_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    settings = _settings(path)

    with TestClient(create_app(settings)) as first:
        session_id = first.post("/api/v1/sessions", json={}).json()["session_id"]
        initial = first.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
        )
        assert initial.status_code == 201
        assert initial.json()["request_message"] == "What is an ETF?"
        assert initial.json()["result"]["selected_agent_ids"] == ["finance_qa"]
        initial_execution_id = initial.json()["execution_id"]

    with TestClient(create_app(settings)) as restarted:
        persisted_run = restarted.get(f"/api/v1/sessions/{session_id}/runs/{initial_execution_id}")
        persisted = restarted.get(
            f"/api/v1/sessions/{session_id}/runs/{initial_execution_id}/events"
        )
        follow_up = restarted.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "Explain that another way."},
        )

        assert persisted_run.status_code == 200
        assert persisted_run.json()["request_message"] == "What is an ETF?"
        assert persisted.status_code == 200
        assert persisted.json()["events"]
        assert follow_up.status_code == 201
        assert follow_up.json()["result"]["selected_agent_ids"] == ["finance_qa"]


def test_session_archive_preserves_history_then_deletion_cascades_resources_and_checkpoint_thread(
    tmp_path: Path,
) -> None:
    path = tmp_path / "delete.sqlite3"
    settings = _settings(path)
    app = create_app(settings)

    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
        created = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
        )
        execution_id = created.json()["execution_id"]
        archived = client.post(f"/api/v1/sessions/{session_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["state"] == "archived"
        assert client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}").status_code == 200
        principal_id = client.get("/api/v1/identity").json()["principal_id"]
        checkpoints = tuple(
            app.state.services.checkpointer.list(
                {
                    "configurable": {
                        "thread_id": f"{principal_id}:{session_id}:{settings.workflow_id}"
                    }
                }
            )
        )
        assert checkpoints

        assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 204
        assert client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}").status_code == 404
        deleted_checkpoints = tuple(
            app.state.services.checkpointer.list(
                {
                    "configurable": {
                        "thread_id": f"{principal_id}:{session_id}:{settings.workflow_id}"
                    }
                }
            )
        )
        assert deleted_checkpoints == ()


def test_newer_storage_schema_blocks_startup(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    database.close()
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (5, 'future', 'now')"
    )
    connection.commit()
    connection.close()

    incompatible = SQLiteDatabase(path, expected_version=4)
    with pytest.raises(MigrationError, match="newer"):
        incompatible.migrate()
    incompatible.close()


def test_schema_one_database_migrates_sessions_and_run_question_contract(tmp_path: Path) -> None:
    path = tmp_path / "schema-one.sqlite3"
    original = SQLiteDatabase(path, expected_version=1)
    original.migrate()
    observed = datetime.now(UTC).isoformat()
    with original.transaction() as connection:
        connection.execute(
            "INSERT INTO sessions(session_id, label, created_at, updated_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("legacy-session", "Legacy", observed, observed, observed),
        )
        connection.execute(
            "INSERT INTO runs(execution_id, session_id, workflow_id, workflow_version, status, "
            "result_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
            (
                "legacy-run",
                "legacy-session",
                "finance-assistant",
                "1",
                "running",
                observed,
                observed,
            ),
        )
    original.close()

    upgraded = SQLiteDatabase(path)
    upgraded.migrate()
    with upgraded.read() as connection:
        columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        run_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        principal_id = connection.execute(
            "SELECT principal_id FROM sessions WHERE session_id = 'legacy-session'"
        ).fetchone()[0]
        run_principal_id = connection.execute(
            "SELECT principal_id FROM runs WHERE execution_id = 'legacy-run'"
        ).fetchone()[0]

    assert upgraded.schema_version() == 4
    assert "archived_at" in columns
    assert "principal_id" in columns
    assert "request_message" in run_columns
    assert principal_id == LOCAL_DEVELOPMENT_PRINCIPAL_ID
    assert run_principal_id == LOCAL_DEVELOPMENT_PRINCIPAL_ID
    upgraded.close()


def test_schema_three_local_checkpoint_is_scoped_to_loopback_principal(tmp_path: Path) -> None:
    path = tmp_path / "schema-three-checkpoint.sqlite3"
    legacy = SQLiteDatabase(path, expected_version=3)
    legacy.migrate()
    observed = datetime.now(UTC)
    with legacy.transaction() as connection:
        connection.execute(
            "INSERT INTO sessions(session_id, label, created_at, updated_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "legacy-session",
                "Legacy",
                observed.isoformat(),
                observed.isoformat(),
                (observed + timedelta(days=1)).isoformat(),
            ),
        )
    _, checkpoint_connection = create_sqlite_checkpointer(legacy)
    checkpoint_connection.execute(
        "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id, type, checkpoint, "
        "metadata) VALUES (?, '', ?, ?, ?, ?)",
        ("legacy-session:finance-assistant-test", "checkpoint-1", "json", b"{}", b"{}"),
    )
    checkpoint_connection.commit()
    checkpoint_connection.close()
    legacy.close()

    app = create_app(_settings(path))
    with TestClient(app):
        rows = app.state.services._checkpoint_connection.execute(
            "SELECT thread_id FROM checkpoints"
        ).fetchall()

    assert [str(row[0]) for row in rows] == [
        f"{LOCAL_DEVELOPMENT_PRINCIPAL_ID}:legacy-session:finance-assistant-test"
    ]


def test_expired_session_and_checkpoint_are_purged_on_restart(tmp_path: Path) -> None:
    path = tmp_path / "expired.sqlite3"
    settings = _settings(path)
    app = create_app(settings)

    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
        principal_id = client.get("/api/v1/identity").json()["principal_id"]
        created = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
        )
        assert created.status_code == 201

    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
        ((datetime.now(UTC) - timedelta(days=1)).isoformat(), session_id),
    )
    connection.commit()
    connection.close()

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as restarted:
        assert restarted.get(f"/api/v1/sessions/{session_id}").status_code == 404
        checkpoints = tuple(
            restarted_app.state.services.checkpointer.list(
                {
                    "configurable": {
                        "thread_id": f"{principal_id}:{session_id}:{settings.workflow_id}"
                    }
                }
            )
        )
        assert checkpoints == ()
