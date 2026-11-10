import json
from pathlib import Path

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings
from ai_finance_assistant.identity.models import (
    IAP_ISSUER,
    LOOPBACK_EMAIL,
    LOOPBACK_ISSUER,
    LOOPBACK_SUBJECT,
)
from ai_finance_assistant.persistence.database import APPLICATION_SCHEMA_VERSION


def test_application_access_manifest_matches_runtime_and_frontend_contracts() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads(
        (root / "contracts/deployment/application-access.v1.json").read_text(encoding="utf-8")
    )
    settings = Settings(mode="test")
    openapi = create_app(settings).openapi()
    vite_config = (root / "frontend/vite.config.ts").read_text(encoding="utf-8")
    session_hook = (root / "frontend/src/hooks/useSession.ts").read_text(encoding="utf-8")

    assert manifest["external_base_path"] == settings.base_path
    assert openapi["servers"] == [{"url": manifest["external_base_path"]}]
    assert 'base: "/finance_assistant/"' in vite_config
    assert "aifa.session.${principalId}" in session_hook
    assert manifest["iap"]["issuer"] == IAP_ISSUER
    assert manifest["iap"]["principal_claims"] == ["iss", "sub"]
    assert manifest["local_development"] == {
        "mode": "loopback_development",
        "allowed_hosts": ["127.0.0.1", "::1", "localhost"],
        "issuer": LOOPBACK_ISSUER,
        "subject": LOOPBACK_SUBJECT,
        "email": LOOPBACK_EMAIL,
        "role": "owner",
        "external_base_path": settings.base_path,
    }
    assert manifest["authoritative_schema_version"] == APPLICATION_SCHEMA_VERSION
    assert manifest["deployed_store_initialization"] == "empty"
