import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.persistence.database import MigrationError, SQLiteDatabase


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
        assert initial.json()["result"]["selected_agent_ids"] == ["finance_qa"]
        initial_execution_id = initial.json()["execution_id"]

    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get(
            f"/api/v1/sessions/{session_id}/runs/{initial_execution_id}/events"
        )
        follow_up = restarted.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "Explain that another way."},
        )

        assert persisted.status_code == 200
        assert persisted.json()["events"]
        assert follow_up.status_code == 201
        assert follow_up.json()["result"]["selected_agent_ids"] == ["finance_qa"]


def test_session_deletion_cascades_resources_and_checkpoint_thread(tmp_path: Path) -> None:
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
        assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 204
        assert client.get(f"/api/v1/sessions/{session_id}/runs/{execution_id}").status_code == 404
        checkpoints = tuple(
            app.state.services.checkpointer.list(
                {"configurable": {"thread_id": f"{session_id}:finance-assistant"}}
            )
        )
        assert checkpoints == ()


def test_newer_storage_schema_blocks_startup(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    database = SQLiteDatabase(path)
    database.migrate()
    database.close()
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (2, 'future', 'now')"
    )
    connection.commit()
    connection.close()

    incompatible = SQLiteDatabase(path, expected_version=1)
    with pytest.raises(MigrationError, match="newer"):
        incompatible.migrate()
    incompatible.close()


def test_expired_session_and_checkpoint_are_purged_on_restart(tmp_path: Path) -> None:
    path = tmp_path / "expired.sqlite3"
    settings = _settings(path)
    app = create_app(settings)

    with TestClient(app) as client:
        session_id = client.post("/api/v1/sessions", json={}).json()["session_id"]
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
                {"configurable": {"thread_id": f"{session_id}:finance-assistant"}}
            )
        )
        assert checkpoints == ()
