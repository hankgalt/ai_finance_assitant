from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.identity.models import PrincipalStatus
from ai_finance_assistant.identity.verification import IAPAssertionVerifier

IAP_ISSUER = "https://cloud.google.com/iap"
IAP_AUDIENCE = "/projects/730340912967/global/backendServices/123456789"
OWNER_EMAIL = "vtalwar.w@comfforts.com"
VIEWER_EMAIL = "finance.viewer@gmail.com"


class SignedIAPFixture:
    def __init__(self) -> None:
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self._private_key.public_key()

    def token(
        self,
        *,
        subject: str,
        email: str,
        audience: str = IAP_AUDIENCE,
        issuer: str = IAP_ISSUER,
        expires_delta: timedelta = timedelta(minutes=5),
    ) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iss": issuer,
                "aud": audience,
                "sub": subject,
                "email": email,
                "iat": now,
                "exp": now + expires_delta,
            },
            self._private_key,
            algorithm="ES256",
            headers={"kid": "test-iap-key"},
        )


def _settings(
    path: Path,
    *,
    identity_mode: str = "iap",
    provider_mode: str = "credential_free",
) -> Settings:
    values: dict[str, Any] = {
        "mode": "test",
        "host": "127.0.0.1",
        "base_path": "/finance_assistant",
        "identity_mode": identity_mode,
        "storage_path": path,
        "provider_mode": provider_mode,
        "model_mode": "credential_free",
        "qdrant_url": None,
        "observability_mode": "in_memory",
        "langsmith_tracing_enabled": False,
    }
    if identity_mode == "iap":
        values.update(
            {
                "iap_audience": IAP_AUDIENCE,
                "iap_owner_email": OWNER_EMAIL,
                "iap_viewer_emails": [VIEWER_EMAIL],
            }
        )
    return Settings(**values)


@contextmanager
def _iap_client(
    path: Path,
    *,
    provider_mode: str = "credential_free",
) -> Iterator[tuple[TestClient, SignedIAPFixture]]:
    signed = SignedIAPFixture()
    verifier = IAPAssertionVerifier(
        expected_audience=IAP_AUDIENCE,
        signing_key_resolver=lambda _token: signed.public_key,
    )
    app = create_app(
        _settings(path, provider_mode=provider_mode),
        iap_assertion_verifier=verifier,
    )
    with TestClient(app) as client:
        yield client, signed


def _headers(token: str) -> dict[str, str]:
    return {"X-Goog-IAP-JWT-Assertion": token}


def _portfolio_payload(portfolio_id: str) -> dict[str, object]:
    return {
        "metadata": {
            "portfolio_id": portfolio_id,
            "label": "Identity fixture",
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
                    "user_price_provenance": "identity test fixture",
                }
            ],
        },
    }


def test_iap_mode_rejects_anonymous_unsigned_and_invalid_assertions(tmp_path: Path) -> None:
    with _iap_client(tmp_path / "iap-rejection.sqlite3") as (client, signed):
        anonymous = client.get("/api/v1/identity")
        unsigned = client.get(
            "/api/v1/identity",
            headers={"X-Goog-Authenticated-User-Email": f"accounts.google.com:{OWNER_EMAIL}"},
        )
        wrong_audience = client.get(
            "/api/v1/identity",
            headers=_headers(
                signed.token(
                    subject="owner-subject",
                    email=OWNER_EMAIL,
                    audience="/projects/wrong/backendServices/wrong",
                )
            ),
        )
        expired = client.get(
            "/api/v1/identity",
            headers=_headers(
                signed.token(
                    subject="owner-subject",
                    email=OWNER_EMAIL,
                    expires_delta=timedelta(minutes=-1),
                )
            ),
        )
        wrong_issuer = client.get(
            "/api/v1/identity",
            headers=_headers(
                signed.token(
                    subject="owner-subject",
                    email=OWNER_EMAIL,
                    issuer="https://example.invalid",
                )
            ),
        )
        other_signer = SignedIAPFixture()
        bad_signature = client.get(
            "/api/v1/identity",
            headers=_headers(other_signer.token(subject="owner-subject", email=OWNER_EMAIL)),
        )

    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "IAP_ASSERTION_REQUIRED"
    assert unsigned.status_code == 401
    assert unsigned.json()["error"]["code"] == "IAP_ASSERTION_REQUIRED"
    assert wrong_audience.status_code == 401
    assert wrong_audience.json()["error"]["code"] == "IAP_ASSERTION_INVALID"
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "IAP_ASSERTION_INVALID"
    assert wrong_issuer.status_code == 401
    assert wrong_issuer.json()["error"]["code"] == "IAP_ASSERTION_INVALID"
    assert bad_signature.status_code == 401
    assert bad_signature.json()["error"]["code"] == "IAP_ASSERTION_INVALID"


def test_iap_identity_binds_owner_and_viewer_but_denies_unknown_identity(tmp_path: Path) -> None:
    with _iap_client(tmp_path / "iap-admission.sqlite3") as (client, signed):
        owner = client.get(
            "/api/v1/identity",
            headers=_headers(signed.token(subject="owner-subject", email=OWNER_EMAIL)),
        )
        viewer = client.get(
            "/api/v1/identity",
            headers=_headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL)),
        )
        unknown = client.get(
            "/api/v1/identity",
            headers=_headers(signed.token(subject="unknown-subject", email="unknown@gmail.com")),
        )

    assert owner.status_code == 200
    assert owner.json()["role"] == "owner"
    assert owner.json()["email"] == OWNER_EMAIL
    assert owner.json()["identity_mode"] == "iap"
    assert owner.json()["principal_id"].startswith("principal-")
    assert viewer.status_code == 200
    assert viewer.json()["role"] == "viewer"
    assert viewer.json()["principal_id"] != owner.json()["principal_id"]
    assert unknown.status_code == 403
    assert unknown.json()["error"]["code"] == "PRINCIPAL_NOT_ADMITTED"


def test_principal_ownership_survives_verified_email_metadata_change(tmp_path: Path) -> None:
    with _iap_client(tmp_path / "iap-email-change.sqlite3") as (client, signed):
        original_headers = _headers(signed.token(subject="stable-owner-subject", email=OWNER_EMAIL))
        original_identity = client.get("/api/v1/identity", headers=original_headers).json()
        session_id = client.post(
            "/api/v1/sessions",
            json={"label": "Before email change"},
            headers=original_headers,
        ).json()["session_id"]

        renamed_headers = _headers(
            signed.token(
                subject="stable-owner-subject",
                email="renamed-owner@comfforts.com",
            )
        )
        renamed_identity = client.get("/api/v1/identity", headers=renamed_headers)
        retained_session = client.get(
            f"/api/v1/sessions/{session_id}",
            headers=renamed_headers,
        )

    assert renamed_identity.status_code == 200
    assert renamed_identity.json()["principal_id"] == original_identity["principal_id"]
    assert renamed_identity.json()["email"] == "renamed-owner@comfforts.com"
    assert retained_session.status_code == 200


def test_two_principals_cannot_enumerate_or_reuse_each_others_resources(tmp_path: Path) -> None:
    with _iap_client(tmp_path / "iap-isolation.sqlite3") as (client, signed):
        owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))
        viewer_headers = _headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL))

        owner_session = client.post(
            "/api/v1/sessions", json={"label": "Owner"}, headers=owner_headers
        ).json()["session_id"]
        viewer_session = client.post(
            "/api/v1/sessions", json={"label": "Viewer"}, headers=viewer_headers
        ).json()["session_id"]

        owner_sessions = client.get("/api/v1/sessions", headers=owner_headers)
        viewer_sessions = client.get("/api/v1/sessions", headers=viewer_headers)
        viewer_owner_lookup = client.get(
            f"/api/v1/sessions/{owner_session}", headers=viewer_headers
        )

        owner_portfolio = client.post(
            f"/api/v1/sessions/{owner_session}/portfolios",
            json=_portfolio_payload("portfolio-shared-name"),
            headers={**owner_headers, "Idempotency-Key": "shared-portfolio-key"},
        )
        viewer_portfolio = client.post(
            f"/api/v1/sessions/{viewer_session}/portfolios",
            json=_portfolio_payload("portfolio-shared-name"),
            headers={**viewer_headers, "Idempotency-Key": "shared-portfolio-key"},
        )
        owner_snapshot = client.post(
            f"/api/v1/sessions/{owner_session}/portfolios/portfolio-shared-name/snapshots",
            json={
                "snapshot_id": "snapshot-owner",
                "security_references": [],
                "quote_set": {"quote_set_id": "quotes-owner", "quotes": []},
            },
            headers=owner_headers,
        )
        viewer_snapshot = client.post(
            f"/api/v1/sessions/{viewer_session}/portfolios/portfolio-shared-name/snapshots",
            json={
                "snapshot_id": "snapshot-owner",
                "security_references": [],
                "quote_set": {"quote_set_id": "quotes-viewer", "quotes": []},
            },
            headers=viewer_headers,
        )
        owner_goal = client.post(
            f"/api/v1/sessions/{owner_session}/goal-projections",
            json={
                "projection_id": "goal-owner",
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
            },
            headers=owner_headers,
        )
        owner_run = client.post(
            f"/api/v1/sessions/{owner_session}/runs",
            json={"message": "What is an ETF?"},
            headers={**owner_headers, "Idempotency-Key": "shared-run-key"},
        )
        viewer_run = client.post(
            f"/api/v1/sessions/{viewer_session}/runs",
            json={"message": "What is an ETF?"},
            headers={**viewer_headers, "Idempotency-Key": "shared-run-key"},
        )
        execution_id = owner_run.json()["execution_id"]
        viewer_execution_id = viewer_run.json()["execution_id"]
        denied_run = client.get(
            f"/api/v1/sessions/{owner_session}/runs/{execution_id}",
            headers=viewer_headers,
        )
        denied_own_run_on_foreign_session = client.get(
            f"/api/v1/sessions/{owner_session}/runs/{viewer_execution_id}",
            headers=viewer_headers,
        )
        denied_events = client.get(
            f"/api/v1/sessions/{owner_session}/runs/{execution_id}/events",
            headers=viewer_headers,
        )
        denied_stream = client.get(
            f"/api/v1/sessions/{owner_session}/runs/{execution_id}/stream",
            headers=viewer_headers,
        )
        denied_portfolio_list = client.get(
            f"/api/v1/sessions/{owner_session}/portfolios",
            headers=viewer_headers,
        )
        denied_portfolio = client.get(
            f"/api/v1/sessions/{owner_session}/portfolios/portfolio-shared-name",
            headers=viewer_headers,
        )
        denied_snapshot = client.get(
            f"/api/v1/sessions/{owner_session}/snapshots/snapshot-owner",
            headers=viewer_headers,
        )
        denied_snapshot_list = client.get(
            f"/api/v1/sessions/{owner_session}/portfolios/portfolio-shared-name/snapshots",
            headers=viewer_headers,
        )
        denied_goal = client.post(
            f"/api/v1/sessions/{owner_session}/goal-projections",
            json={
                "projection_id": "goal-guessed",
                "currency": "USD",
                "starting_amount": "1",
                "goal_amount": "2",
                "contribution_amount": "0",
                "contribution_frequency": "monthly",
                "contribution_timing": "end",
                "horizon_months": 1,
                "risk_tolerance": "not_declared",
                "scenarios": [
                    {
                        "label": "guessed",
                        "annual_return_rate": "0",
                        "annual_inflation_rate": "0",
                        "annual_fee_rate": "0",
                    }
                ],
            },
            headers=viewer_headers,
        )
        denied_continue = client.post(
            f"/api/v1/sessions/{owner_session}/runs/{execution_id}/continue",
            json={"context_references": ["portfolio-shared-name"]},
            headers=viewer_headers,
        )
        denied_archive = client.post(
            f"/api/v1/sessions/{owner_session}/archive",
            headers=viewer_headers,
        )
        denied_delete = client.delete(
            f"/api/v1/sessions/{owner_session}",
            headers=viewer_headers,
        )

    assert [item["session_id"] for item in owner_sessions.json()["items"]] == [owner_session]
    assert [item["session_id"] for item in viewer_sessions.json()["items"]] == [viewer_session]
    assert viewer_owner_lookup.status_code == 404
    assert viewer_owner_lookup.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert owner_portfolio.status_code == 201
    assert viewer_portfolio.status_code == 201
    assert owner_snapshot.status_code == 201
    assert viewer_snapshot.status_code == 201
    assert owner_goal.status_code == 200
    assert owner_run.status_code == 201
    assert viewer_run.status_code == 201
    assert denied_run.status_code == 404
    assert denied_own_run_on_foreign_session.status_code == 404
    assert denied_events.status_code == 404
    assert denied_stream.status_code == 404
    assert denied_portfolio_list.status_code == 404
    assert denied_portfolio.status_code == 404
    assert denied_snapshot.status_code == 404
    assert denied_snapshot_list.status_code == 404
    assert denied_goal.status_code == 404
    assert denied_continue.status_code == 404
    assert denied_archive.status_code == 404
    assert denied_delete.status_code == 404


def test_disabled_principal_is_denied_at_the_next_request_boundary(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "iap-revocation.sqlite3")
    signed = SignedIAPFixture()
    verifier = IAPAssertionVerifier(
        expected_audience=IAP_AUDIENCE,
        signing_key_resolver=lambda _token: signed.public_key,
    )
    app = create_app(settings, iap_assertion_verifier=verifier)
    viewer_headers = _headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL))

    with TestClient(app) as client:
        admitted = client.get("/api/v1/identity", headers=viewer_headers)
        principal_id = admitted.json()["principal_id"]
        app.state.services.principal_repository.set_status(
            principal_id,
            PrincipalStatus.DISABLED,
        )
        denied = client.get("/api/v1/identity", headers=viewer_headers)

    assert admitted.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PRINCIPAL_DISABLED"


def test_only_owner_role_can_use_administrative_operations(tmp_path: Path) -> None:
    with _iap_client(tmp_path / "iap-role-matrix.sqlite3") as (client, signed):
        owner_headers = _headers(signed.token(subject="owner-subject", email=OWNER_EMAIL))
        viewer_headers = _headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL))

        owner = client.delete("/api/v1/admin/response-cache", headers=owner_headers)
        viewer = client.delete("/api/v1/admin/response-cache", headers=viewer_headers)

    assert owner.status_code == 200
    assert viewer.status_code == 403
    assert viewer.json()["error"]["code"] == "ADMIN_SCOPE_DENIED"


def test_viewer_live_provider_use_stays_denied_without_approved_rights(tmp_path: Path) -> None:
    with _iap_client(
        tmp_path / "iap-provider-rights.sqlite3",
        provider_mode="live",
    ) as (client, signed):
        viewer_headers = _headers(signed.token(subject="viewer-subject", email=VIEWER_EMAIL))
        session_id = client.post(
            "/api/v1/sessions",
            json={"label": "Viewer"},
            headers=viewer_headers,
        ).json()["session_id"]

        run = client.post(
            f"/api/v1/sessions/{session_id}/runs",
            json={"message": "What is an ETF?"},
            headers=viewer_headers,
        )
        quote = client.post(
            f"/api/v1/sessions/{session_id}/market/quotes",
            json={"symbol": "DEMO", "currency": "USD"},
            headers=viewer_headers,
        )

    assert run.status_code == 403
    assert run.json()["error"]["code"] == "PROVIDER_SCOPE_DENIED"
    assert quote.status_code == 403
    assert quote.json()["error"]["code"] == "PROVIDER_SCOPE_DENIED"


def test_loopback_development_identity_is_explicit_and_stable(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path / "loopback.sqlite3", identity_mode="loopback_development"))

    with TestClient(app) as client:
        first = client.get("/api/v1/identity")
        second = client.get("/api/v1/identity")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["role"] == "owner"
    assert first.json()["email"] == "local-owner@example.invalid"
    assert first.json()["identity_mode"] == "loopback_development"


@pytest.mark.parametrize(
    "values",
    [
        {"mode": "production", "identity_mode": "loopback_development"},
        {"mode": "test", "host": "0.0.0.0", "identity_mode": "loopback_development"},
        {"mode": "test", "identity_mode": "iap"},
    ],
)
def test_unsafe_identity_configuration_is_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        Settings(**values)
