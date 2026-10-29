import json
from pathlib import Path

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings


def test_m6_frontend_manifest_matches_openapi() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads(
        (root / "contracts" / "m6-frontend-contract.v1.json").read_text(encoding="utf-8")
    )
    frontend_types = (root / manifest["frontend_type_file"]).read_text(encoding="utf-8")
    openapi = create_app(
        Settings(
            mode="test",
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            observability_mode="disabled",
            langsmith_tracing_enabled=False,
        )
    ).openapi()

    for path, methods in manifest["required_paths"].items():
        assert path in openapi["paths"]
        assert set(methods).issubset(openapi["paths"][path])
    for type_name in manifest["required_frontend_types"]:
        assert f" {type_name} " in frontend_types
