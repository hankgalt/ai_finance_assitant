import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND_ROOT = Path(__file__).parents[1]
_TEST_ENV_FILE = Path(
    os.environ.get(
        "AIFA_TEST_ENV_FILE",
        str(_BACKEND_ROOT / ".test.env"),
    )
)
os.environ["AIFA_ENV_FILE"] = os.environ.get(
    "AIFA_TEST_ENV_FILE",
    str(_TEST_ENV_FILE),
)


def _load_required_identity_settings(path: Path) -> None:
    configured = {
        key.strip(): value.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
        for key, value in (line.split("=", 1),)
    }
    for name in (
        "AIFA_WORKFLOW_ID",
        "AIFA_OTEL_SERVICE_NAME",
        "AIFA_LANGSMITH_PROJECT",
    ):
        value = configured.get(name)
        if value is None:
            raise RuntimeError(f"{name} must be configured in {path}")
        os.environ.setdefault(name, value)


_load_required_identity_settings(_TEST_ENV_FILE)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from ai_finance_assistant.api.app import create_app
    from ai_finance_assistant.core.config import Settings

    app = create_app(
        Settings(
            mode="test",
            log_level="WARNING",
            storage_path=tmp_path / "application.sqlite3",
            provider_mode="credential_free",
            model_mode="credential_free",
            qdrant_url=None,
            langsmith_tracing_enabled=False,
        )
    )
    with TestClient(app) as test_client:
        yield test_client
