"""Managed PostgreSQL application and checkpoint adapter qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pydantic import SecretStr

from ai_finance_assistant.agents.context import GoalAgentContext
from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.identity.models import PrincipalRole, VerifiedIdentity
from ai_finance_assistant.identity.repositories import PrincipalRepository
from ai_finance_assistant.identity.verification import IAPAssertionVerifier
from ai_finance_assistant.persistence.checkpoints import (
    create_postgres_checkpointer,
    verify_postgres_checkpoint_schema,
)
from ai_finance_assistant.persistence.cli import migrate, run_retention, status
from ai_finance_assistant.persistence.config import PersistenceOperatorSettings
from ai_finance_assistant.persistence.postgres import PostgresDatabase, _postgres_placeholders
from ai_finance_assistant.persistence.privileges import (
    apply_database_role_policy,
    database_role_policy_statements,
    migration_default_privilege_statements,
)
from ai_finance_assistant.persistence.qualification import (
    prepare_qualification,
    verify_recovered_state,
    verify_retention_and_cleanup,
)
from ai_finance_assistant.persistence.repositories import ApplicationRepository

IAP_ISSUER = "https://cloud.google.com/iap"
IAP_AUDIENCE = "/projects/730340912967/global/backendServices/123456789"
OWNER_EMAIL = "vtalwar.w@comfforts.com"
VIEWER_EMAIL = "finance.viewer@gmail.com"


def test_persistence_operator_configuration_is_independent_and_redacts_dsn() -> None:
    settings = PersistenceOperatorSettings(
        storage_backend="postgres",
        postgres_dsn="postgresql://runtime:private-value@127.0.0.1:5432/aifa",
    )

    assert settings.storage_backend == "postgres"
    assert settings.postgres_dsn is not None
    assert settings.postgres_dsn.get_secret_value().endswith("/aifa")
    assert "private-value" not in repr(settings)
    assert not hasattr(settings, "qdrant_api_key")
    assert not hasattr(settings, "iap_audience")


def test_database_role_policy_sql_is_reviewable_and_identifier_quoted() -> None:
    statements = database_role_policy_statements(
        database='aifa"db',
        schema="public",
        migration_role="aifa-migration@example.iam",
        runtime_role="aifa-runtime@example.iam",
        retention_role="aifa-retention@example.iam",
    )
    rendered = "\n".join(statements)

    assert 'GRANT CONNECT ON DATABASE "aifa""db"' in rendered
    assert 'GRANT USAGE, CREATE ON SCHEMA "public"' in rendered
    assert "ALTER DEFAULT PRIVILEGES" not in rendered
    assert "PUBLIC" in rendered
    assert "DROP ROLE" not in rendered

    migration_defaults = "\n".join(
        migration_default_privilege_statements(
            schema="public",
            runtime_role="aifa-runtime@example.iam",
            retention_role="aifa-retention@example.iam",
        )
    )
    assert (
        'ALTER DEFAULT PRIVILEGES IN SCHEMA "public" '
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "
        '"aifa-runtime@example.iam"' in migration_defaults
    )
    assert 'GRANT SELECT, DELETE ON TABLES TO "aifa-retention@example.iam"' in migration_defaults
    assert "FOR ROLE" not in migration_defaults


@pytest.mark.postgres
def test_database_role_policy_separates_migration_runtime_and_retention() -> None:
    root_dsn = os.getenv("AIFA_TEST_POSTGRES_DSN")
    if root_dsn is None:
        pytest.skip("AIFA_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    schema = f"aifa_roles_{suffix}"
    migration_role = f"aifa_migration_{suffix}"
    runtime_role = f"aifa_runtime_{suffix}"
    retention_role = f"aifa_retention_{suffix}"
    with psycopg.connect(root_dsn, autocommit=True) as admin:
        database = admin.info.dbname
        assert database is not None
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        for role in (migration_role, runtime_role, retention_role):
            admin.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
        apply_database_role_policy(
            admin,
            database=database,
            schema=schema,
            migration_role=migration_role,
            runtime_role=runtime_role,
            retention_role=retention_role,
        )

    migration_dsn = make_conninfo(root_dsn, user=migration_role)
    runtime_dsn = make_conninfo(root_dsn, user=runtime_role)
    retention_dsn = make_conninfo(root_dsn, user=retention_role)
    try:
        migrate(
            PersistenceOperatorSettings(
                storage_backend="postgres",
                postgres_dsn=migration_dsn,
            ),
            runtime_role=runtime_role,
            retention_role=retention_role,
            schema=schema,
        )
        with psycopg.connect(migration_dsn, autocommit=True) as migration:
            migration.execute("CREATE TABLE privilege_probe(id BIGSERIAL PRIMARY KEY, value TEXT)")

        with psycopg.connect(runtime_dsn, autocommit=True) as runtime:
            inserted = runtime.execute(
                "INSERT INTO privilege_probe(value) VALUES ('runtime') RETURNING id"
            ).fetchone()
            assert inserted is not None
            runtime.execute(
                "UPDATE privilege_probe SET value = 'updated' WHERE id = %s",
                (inserted[0],),
            )
            assert runtime.execute("SELECT value FROM privilege_probe").fetchone() == ("updated",)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute("CREATE TABLE runtime_must_not_create(value INTEGER)")

        with psycopg.connect(retention_dsn, autocommit=True) as retention:
            assert retention.execute("DELETE FROM privilege_probe").rowcount == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                retention.execute("INSERT INTO privilege_probe(value) VALUES ('denied')")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                retention.execute("CREATE TABLE retention_must_not_create(value INTEGER)")
    finally:
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            for role in (migration_role, runtime_role, retention_role):
                admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


class SignedIAPFixture:
    def __init__(self) -> None:
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self._private_key.public_key()

    def token(self, *, subject: str, email: str) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": IAP_ISSUER,
                "aud": IAP_AUDIENCE,
                "sub": subject,
                "email": email,
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            self._private_key,
            algorithm="ES256",
            headers={"kid": "test-iap-key"},
        )


def _managed_settings(dsn: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "mode": "test",
        "host": "127.0.0.1",
        "base_path": "/finance_assistant",
        "identity_mode": "iap",
        "iap_audience": IAP_AUDIENCE,
        "iap_owner_email": OWNER_EMAIL,
        "iap_viewer_emails": [VIEWER_EMAIL],
        "storage_backend": "postgres",
        "postgres_dsn": SecretStr(dsn),
        "storage_migration_mode": "verify_only",
        "retention_execution_mode": "scheduled",
        "response_cache_adapter": "disabled",
        "provider_mode": "credential_free",
        "model_mode": "credential_free",
        "qdrant_url": None,
        "observability_mode": "in_memory",
        "langsmith_tracing_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


@contextmanager
def _managed_client(
    settings: Settings,
    signed: SignedIAPFixture,
) -> Iterator[TestClient]:
    verifier = IAPAssertionVerifier(
        expected_audience=IAP_AUDIENCE,
        signing_key_resolver=lambda _token: signed.public_key,
    )
    with TestClient(create_app(settings, iap_assertion_verifier=verifier)) as client:
        yield client


def _headers(token: str) -> dict[str, str]:
    return {"X-Goog-IAP-JWT-Assertion": token}


def _portfolio_payload(portfolio_id: str) -> dict[str, object]:
    return {
        "metadata": {
            "portfolio_id": portfolio_id,
            "label": "Managed qualification",
            "base_currency": "USD",
            "imported_at": "2026-11-09T12:00:00Z",
        },
        "payload": {
            "kind": "manual",
            "rows": [
                {
                    "account_id": "account-1",
                    "account_type": "taxable",
                    "holding_id": "holding-1",
                    "identifier_type": "ticker",
                    "identifier_value": "DEMO",
                    "quantity": "1",
                    "currency": "USD",
                    "user_price": "10",
                    "user_price_as_of": "2026-11-09T12:00:00Z",
                    "user_price_provenance": "managed qualification fixture",
                }
            ],
        },
    }


def _snapshot_payload(snapshot_id: str, quote_set_id: str) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "security_references": [],
        "quote_set": {"quote_set_id": quote_set_id, "quotes": []},
    }


def _goal_payload(projection_id: str) -> dict[str, object]:
    return {
        "projection_id": projection_id,
        "currency": "USD",
        "starting_amount": "1000",
        "goal_amount": "2000",
        "contribution_amount": "100",
        "contribution_frequency": "monthly",
        "contribution_timing": "end",
        "horizon_months": 12,
        "risk_tolerance": "not_declared",
        "scenarios": [
            {
                "label": "explicit",
                "annual_return_rate": "0.05",
                "annual_inflation_rate": "0.02",
                "annual_fee_rate": "0",
            }
        ],
    }


@pytest.fixture
def managed_postgres_dsn() -> Iterator[str]:
    root_dsn = os.getenv("AIFA_TEST_POSTGRES_DSN")
    if root_dsn is None:
        pytest.skip("AIFA_TEST_POSTGRES_DSN is not configured")

    schema = f"aifa_qualification_{uuid4().hex}"
    with psycopg.connect(root_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield make_conninfo(root_dsn, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_placeholder_translation_preserves_repository_sql() -> None:
    assert _postgres_placeholders("SELECT * FROM sessions WHERE principal_id = ?") == (
        "SELECT * FROM sessions WHERE principal_id = %s"
    )


def test_persistence_operator_commands_preserve_local_sqlite_mode(tmp_path: Path) -> None:
    settings = Settings(mode="test", storage_path=tmp_path / "application.sqlite3")

    migrated = migrate(settings)
    observed = status(settings)

    assert migrated["application_schema_ready"] is True
    assert migrated["checkpoint_schema_ready"] is True
    assert observed == migrated


@pytest.mark.postgres
def test_expired_running_run_becomes_safe_terminal_failure_after_restart(
    managed_postgres_dsn: str,
) -> None:
    settings = _managed_settings(managed_postgres_dsn, api_run_deadline_seconds=5)
    migrate(settings)
    signed = SignedIAPFixture()
    owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))

    with _managed_client(settings, signed) as client:
        identity = client.get("/api/v1/identity", headers=owner_headers).json()
        session_id = client.post(
            "/api/v1/sessions",
            json={"label": "Interrupted"},
            headers=owner_headers,
        ).json()["session_id"]
        execution_id = f"run-{uuid4().hex}"
        cast(FastAPI, client.app).state.services.application_repository.create_run(
            principal_id=identity["principal_id"],
            execution_id=execution_id,
            session_id=session_id,
            workflow_id=settings.workflow_id,
            workflow_version="1",
            request_message="What is an ETF?",
            idempotency_key=None,
            request_hash="fault-injection",
            now=datetime.now(UTC) - timedelta(seconds=6),
        )
        fresh_execution_id = f"run-{uuid4().hex}"
        cast(FastAPI, client.app).state.services.application_repository.create_run(
            principal_id=identity["principal_id"],
            execution_id=fresh_execution_id,
            session_id=session_id,
            workflow_id=settings.workflow_id,
            workflow_version="1",
            request_message="What is a bond?",
            idempotency_key=None,
            request_hash="rollout-overlap",
        )

    with _managed_client(settings, signed) as restarted:
        recovered = restarted.get(
            f"/api/v1/sessions/{session_id}/runs/{execution_id}",
            headers=owner_headers,
        )
        still_running = restarted.get(
            f"/api/v1/sessions/{session_id}/runs/{fresh_execution_id}",
            headers=owner_headers,
        )

    assert recovered.status_code == 200
    assert recovered.json()["status"] == "failed"
    assert recovered.json()["result"]["status"] == "failed"
    assert recovered.json()["result"]["errors"] == [
        {
            "code": "RUN_INTERRUPTED",
            "category": "internal",
            "message": "The Run was interrupted before a terminal result was persisted.",
            "retryable": True,
            "attempt_count": 1,
            "safe_details": {},
        }
    ]
    assert still_running.status_code == 200
    assert still_running.json()["status"] == "running"
    assert still_running.json()["result"] is None


@pytest.mark.postgres
def test_scheduled_retention_expires_session_and_checkpoint_idempotently(
    managed_postgres_dsn: str,
) -> None:
    settings = _managed_settings(managed_postgres_dsn, session_retention_days=1)
    migrate(settings)
    signed = SignedIAPFixture()
    owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))

    with _managed_client(settings, signed) as client:
        identity = client.get("/api/v1/identity", headers=owner_headers).json()
        created = client.post(
            "/api/v1/sessions",
            json={"label": "Expiring"},
            headers=owner_headers,
        ).json()
        session_id = created["session_id"]
        run = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
            headers=owner_headers,
        )
        assert run.status_code == 201

    after_expiry = datetime.fromisoformat(created["expires_at"]) + timedelta(seconds=1)
    first = run_retention(settings, now=after_expiry)
    second = run_retention(settings, now=after_expiry)

    assert first == {
        "backend": "postgres",
        "expired_sessions": 1,
        "expired_provider_rows": 0,
    }
    assert second == {
        "backend": "postgres",
        "expired_sessions": 0,
        "expired_provider_rows": 0,
    }

    checkpointer, checkpoint_resource = create_postgres_checkpointer(
        managed_postgres_dsn,
        pool_min_size=1,
        pool_max_size=2,
        timeout_seconds=10,
        setup=False,
    )
    try:
        checkpoint = checkpointer.get_tuple(
            {
                "configurable": {
                    "thread_id": (f"{identity['principal_id']}:{session_id}:{settings.workflow_id}")
                }
            }
        )
    finally:
        checkpoint_resource.close()

    with _managed_client(settings, signed) as restarted:
        expired = restarted.get(f"/api/v1/sessions/{session_id}", headers=owner_headers)

    assert checkpoint is None
    assert expired.status_code == 404
    assert expired.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.postgres
def test_two_principal_resources_history_and_inspector_survive_restart_in_isolation(
    managed_postgres_dsn: str,
) -> None:
    settings = _managed_settings(managed_postgres_dsn)
    migrate(settings)
    signed = SignedIAPFixture()
    owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))
    viewer_headers = _headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL))

    with _managed_client(settings, signed) as client:
        owner_session = client.post(
            "/api/v1/sessions",
            json={"label": "Owner managed state"},
            headers=owner_headers,
        ).json()["session_id"]
        viewer_session = client.post(
            "/api/v1/sessions",
            json={"label": "Viewer managed state"},
            headers=viewer_headers,
        ).json()["session_id"]

        for session_id, headers, quote_set_id in (
            (owner_session, owner_headers, "owner-quotes"),
            (viewer_session, viewer_headers, "viewer-quotes"),
        ):
            portfolio = client.post(
                f"/api/v1/sessions/{session_id}/portfolios",
                json=_portfolio_payload("portfolio-shared-name"),
                headers={**headers, "Idempotency-Key": "portfolio-shared-key"},
            )
            snapshot = client.post(
                f"/api/v1/sessions/{session_id}/portfolios/portfolio-shared-name/snapshots",
                json=_snapshot_payload("snapshot-shared-name", quote_set_id),
                headers=headers,
            )
            goal = client.post(
                f"/api/v1/sessions/{session_id}/goal-projections",
                json=_goal_payload("goal-shared-name"),
                headers=headers,
            )
            assert portfolio.status_code == 201
            assert snapshot.status_code == 201
            assert goal.status_code == 200

        owner_run = client.post(
            f"/api/v1/sessions/{owner_session}/runs",
            json={"message": "What is an ETF?"},
            headers={**owner_headers, "Idempotency-Key": "run-shared-key"},
        )
        viewer_run = client.post(
            f"/api/v1/sessions/{viewer_session}/runs",
            json={"message": "What is an ETF?"},
            headers={**viewer_headers, "Idempotency-Key": "run-shared-key"},
        )
        assert owner_run.status_code == 201
        assert viewer_run.status_code == 201
        owner_execution_id = owner_run.json()["execution_id"]
        viewer_execution_id = viewer_run.json()["execution_id"]

    with _managed_client(settings, signed) as restarted:
        restarted_services = cast(FastAPI, restarted.app).state.services
        owner_goal_context = restarted_services.context_repository.get(
            owner_session,
            "goal-shared-name",
        )
        viewer_goal_context = restarted_services.context_repository.get(
            viewer_session,
            "goal-shared-name",
        )
        readiness = restarted.get("/api/health/ready", headers=owner_headers)
        owner_sessions = restarted.get("/api/v1/sessions", headers=owner_headers)
        viewer_sessions = restarted.get("/api/v1/sessions", headers=viewer_headers)
        owner_history = restarted.get(
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}",
            headers=owner_headers,
        )
        owner_events = restarted.get(
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}/events",
            headers=owner_headers,
        )
        owner_trace = restarted.get(
            f"/api/v1/sessions/{owner_session}/traces/{owner_execution_id}",
            headers=owner_headers,
        )
        owner_stream = restarted.get(
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}/stream",
            headers=owner_headers,
        )
        owner_portfolio = restarted.get(
            f"/api/v1/sessions/{owner_session}/portfolios/portfolio-shared-name",
            headers=owner_headers,
        )
        owner_snapshot = restarted.get(
            f"/api/v1/sessions/{owner_session}/snapshots/snapshot-shared-name",
            headers=owner_headers,
        )
        repeated_run = restarted.post(
            f"/api/v1/sessions/{owner_session}/runs",
            json={"message": "What is an ETF?"},
            headers={**owner_headers, "Idempotency-Key": "run-shared-key"},
        )

        denied_paths = (
            f"/api/v1/sessions/{owner_session}",
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}",
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}/events",
            f"/api/v1/sessions/{owner_session}/traces/{owner_execution_id}",
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}/stream",
            f"/api/v1/sessions/{owner_session}/portfolios",
            f"/api/v1/sessions/{owner_session}/portfolios/portfolio-shared-name",
            f"/api/v1/sessions/{owner_session}/snapshots/snapshot-shared-name",
        )
        viewer_denials = [restarted.get(path, headers=viewer_headers) for path in denied_paths]
        denied_goal = restarted.post(
            f"/api/v1/sessions/{owner_session}/goal-projections",
            json=_goal_payload("goal-guessed"),
            headers=viewer_headers,
        )
        denied_continue = restarted.post(
            f"/api/v1/sessions/{owner_session}/runs/{owner_execution_id}/continue",
            json={"context_references": ["portfolio-shared-name"]},
            headers=viewer_headers,
        )
        denied_archive = restarted.post(
            f"/api/v1/sessions/{owner_session}/archive",
            headers=viewer_headers,
        )
        denied_delete = restarted.delete(
            f"/api/v1/sessions/{owner_session}",
            headers=viewer_headers,
        )
        viewer_own_run = restarted.get(
            f"/api/v1/sessions/{viewer_session}/runs/{viewer_execution_id}",
            headers=viewer_headers,
        )

    storage_readiness = next(
        check for check in readiness.json()["checks"] if check["name"] == "storage.postgresql"
    )
    assert readiness.status_code == 503
    assert storage_readiness["status"] == "ready"
    assert "compatible" in storage_readiness["detail"]
    assert isinstance(owner_goal_context, GoalAgentContext)
    assert isinstance(viewer_goal_context, GoalAgentContext)
    assert owner_goal_context.projection.projection_id == "goal-shared-name"
    assert viewer_goal_context.projection.projection_id == "goal-shared-name"
    assert [item["session_id"] for item in owner_sessions.json()["items"]] == [owner_session]
    assert [item["session_id"] for item in viewer_sessions.json()["items"]] == [viewer_session]
    assert owner_history.status_code == 200
    assert owner_history.json()["status"] in {"completed", "partial", "failed", "clarification"}
    assert owner_history.json()["result"] is not None
    assert owner_events.status_code == 200
    assert owner_events.json()["events"]
    assert owner_trace.json() == owner_events.json()
    assert owner_stream.status_code == 200
    assert "event: run_event" in owner_stream.text
    assert "event: response_chunk" in owner_stream.text
    assert owner_portfolio.status_code == 200
    assert owner_snapshot.status_code == 200
    assert repeated_run.status_code == 200
    assert repeated_run.json()["execution_id"] == owner_execution_id
    assert all(response.status_code == 404 for response in viewer_denials)
    assert denied_goal.status_code == 404
    assert denied_continue.status_code == 404
    assert denied_archive.status_code == 404
    assert denied_delete.status_code == 404
    assert viewer_own_run.status_code == 200


@pytest.mark.postgres
def test_verify_only_runtime_role_serves_requests_without_ddl_privilege() -> None:
    root_dsn = os.getenv("AIFA_TEST_POSTGRES_DSN")
    if root_dsn is None:
        pytest.skip("AIFA_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    schema = f"aifa_runtime_{suffix}"
    role = f"aifa_runtime_{suffix}"
    with psycopg.connect(root_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))

    migration_dsn = make_conninfo(root_dsn, options=f"-c search_path={schema}")
    runtime_dsn = make_conninfo(
        root_dsn,
        user=role,
        options=f"-c search_path={schema}",
    )
    try:
        migrate(_managed_settings(migration_dsn))
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            admin.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
                ).format(sql.Identifier(schema), sql.Identifier(role))
            )
            admin.execute(
                sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )

        with (
            psycopg.connect(runtime_dsn, autocommit=True) as runtime,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            runtime.execute("CREATE TABLE runtime_must_not_create_schema(value INTEGER)")

        settings = _managed_settings(runtime_dsn)
        signed = SignedIAPFixture()
        owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))
        with _managed_client(settings, signed) as client:
            identity = client.get("/api/v1/identity", headers=owner_headers)
            session = client.post(
                "/api/v1/sessions",
                json={"label": "Least privilege"},
                headers=owner_headers,
            )
            run = client.post(
                f"/api/v1/sessions/{session.json()['session_id']}/runs",
                json={"message": "What is an ETF?"},
                headers=owner_headers,
            )

        assert identity.status_code == 200
        assert session.status_code == 201
        assert run.status_code == 201
    finally:
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.mark.postgres
def test_postgres_application_and_checkpoint_state_survive_adapter_restart() -> None:
    root_dsn = os.getenv("AIFA_TEST_POSTGRES_DSN")
    if root_dsn is None:
        pytest.skip("AIFA_TEST_POSTGRES_DSN is not configured")

    schema = f"aifa_qualification_{uuid4().hex}"
    with psycopg.connect(root_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    scoped_dsn = make_conninfo(root_dsn, options=f"-c search_path={schema}")
    database: PostgresDatabase | None = None
    checkpoint_resource = None
    try:
        database = PostgresDatabase(scoped_dsn, pool_min_size=1, pool_max_size=2)
        database.migrate()
        principal = PrincipalRepository(database).ensure(
            VerifiedIdentity(
                issuer="https://cloud.google.com/iap",
                subject="qualification-owner",
                email="owner@example.invalid",
            ),
            role=PrincipalRole.OWNER,
        )
        repository = ApplicationRepository(
            database,
            session_retention_days=30,
            portfolio_retention_days=365,
            run_event_retention_days=30,
        )
        repository.create_session(principal.principal_id, "managed-session", label="Managed")

        _, checkpoint_resource = create_postgres_checkpointer(
            scoped_dsn,
            pool_min_size=1,
            pool_max_size=2,
            timeout_seconds=10,
            setup=True,
        )
        verify_postgres_checkpoint_schema(database)
        checkpoint_resource.close()
        checkpoint_resource = None
        database.close()
        database = PostgresDatabase(scoped_dsn, pool_min_size=1, pool_max_size=2)

        restored = ApplicationRepository(
            database,
            session_retention_days=30,
            portfolio_retention_days=365,
            run_event_retention_days=30,
        ).get_session(principal.principal_id, "managed-session")
        assert restored is not None
        assert restored.label == "Managed"
        verify_postgres_checkpoint_schema(database)
    finally:
        if checkpoint_resource is not None:
            checkpoint_resource.close()
        if database is not None:
            database.close()
        with psycopg.connect(root_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.mark.postgres
def test_managed_state_qualification_is_synthetic_restart_safe_and_retention_verifiable(
    managed_postgres_dsn: str,
) -> None:
    settings = PersistenceOperatorSettings(
        storage_backend="postgres",
        postgres_dsn=managed_postgres_dsn,
        postgres_pool_max_size=4,
    )
    migrate(settings)
    qualification_id = f"test-{uuid4().hex[:12]}"

    prepared = prepare_qualification(settings, qualification_id=qualification_id)
    prepared_json = prepared.model_dump_json()

    assert prepared.phase == "prepare"
    assert prepared.status == "passed"
    assert prepared.synthetic_data is True
    assert prepared.cleanup_performed is False
    assert {check.check_id for check in prepared.checks} == {
        "schema_ready",
        "concurrent_principal_writes",
        "cross_principal_denial",
        "principal_owned_goal_contexts",
        "checkpoint_state",
        "restart_durability",
        "retention_probe_prepared",
    }
    assert managed_postgres_dsn not in prepared_json
    assert "postgresql://" not in prepared_json

    recovered = verify_recovered_state(settings, qualification_id=qualification_id)

    assert recovered.phase == "verify_recovery"
    assert recovered.status == "passed"
    assert recovered.cleanup_performed is False
    assert {check.check_id for check in recovered.checks} == {
        "recovered_schema_ready",
        "recovered_principal_state",
        "recovered_goal_contexts",
        "recovered_checkpoints",
        "recovered_retention_probe",
    }

    retention = run_retention(settings)
    verified = verify_retention_and_cleanup(settings, qualification_id=qualification_id)

    assert retention["expired_sessions"] == 1
    assert verified.phase == "verify_retention"
    assert verified.status == "passed"
    assert verified.cleanup_performed is True
    assert {check.check_id for check in verified.checks} == {
        "retention_probe_removed",
        "unexpired_state_preserved",
        "synthetic_checkpoints_cleaned",
        "synthetic_state_cleaned",
    }
