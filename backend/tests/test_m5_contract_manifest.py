import json
from pathlib import Path

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings


def test_frontend_contract_manifest_matches_openapi() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads(
        (root / "contracts" / "m5-api-contract.v1.json").read_text(encoding="utf-8")
    )
    frontend_types = (root / manifest["frontend_type_file"]).read_text(encoding="utf-8")
    openapi = create_app(
        Settings(
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            langsmith_tracing_enabled=False,
        )
    ).openapi()

    for path, methods in manifest["paths"].items():
        assert path in openapi["paths"]
        assert set(methods).issubset(openapi["paths"][path])
    assert set(manifest["paths"]) == {
        path for path in openapi["paths"] if path.startswith("/api/v1/")
    }
    for type_name in manifest["required_frontend_types"]:
        assert f" {type_name} " in frontend_types
