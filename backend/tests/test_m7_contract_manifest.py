import json
from pathlib import Path

from ai_finance_assistant.api.app import create_app
from ai_finance_assistant.core.config import Settings


def test_m7_inspector_manifest_matches_openapi_and_frontend_seam() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads(
        (root / "contracts" / "m7-inspector-contract.v1.json").read_text(encoding="utf-8")
    )
    frontend_types = (root / manifest["frontend_type_file"]).read_text(encoding="utf-8")
    inspector_model = (root / manifest["inspector_model_file"]).read_text(encoding="utf-8")
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

    event_properties = openapi["components"]["schemas"]["RunEvent"]["properties"]
    for field in manifest["required_event_identity_fields"]:
        assert field in event_properties
    assert manifest["graph_edge_evidence"] == [
        "parent_event_id",
        "routing.selected_node_ids",
    ]
    assert manifest["graph_node_sequence_evidence"] == "sequence"
    assert "recordedEvents.map((event) => event.sequence)" in inspector_model
    assert "event.routing?.selected_node_ids" in inspector_model
    assert "event.parent_event_id" in inspector_model
    assert "final response" not in inspector_model.lower()
